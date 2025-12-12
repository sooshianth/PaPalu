from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from decimal import Decimal
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.AllocationFolder.AllocationModel import Allocation
from core.TransportFolder.TransportModel import Transport
from core.SettlementFolder.SettlementModel import Settlement
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from sales.forms.settlement_transaction_form import SettlementTransactionForm
from sales.tables.tables_settlement import PendingSettlementOrderTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def settlement_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تسویه»
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تسویه")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SALES_SETTLEMENT.value):
        audit_logger.activity("تلاش برای مشاهده لیست تسویه بدون دسترسی")
        messages.error(request, 'شما دسترسی به تسویه سفارش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های در انتظار تسویه
    from core.AllocationFolder.AllocationModel import Allocation
    from core.TransportFolder.TransportModel import Transport
    
    orders_qs = Order.objects.filter(
        status='pending_settlement'
    ).select_related('customer').prefetch_related(
        'order_items',
        'allocations',
        'order_items__product'
    ).order_by('-created_at')

    # دریافت تمام تخصیص‌ها و حمل‌ها به صورت bulk
    all_allocations = Allocation.objects.filter(order__in=orders_qs).select_related('order')
    allocation_dict = {}
    for alloc in all_allocations:
        if alloc.order_id not in allocation_dict:
            allocation_dict[alloc.order_id] = []
        allocation_dict[alloc.order_id].append(alloc.allocation_number)
    
    all_allocations = Allocation.objects.filter(allocation_number__in=[num for nums in allocation_dict.values() for num in nums])
    all_transports = Transport.objects.filter(allocation__in=all_allocations).select_related('allocation')
    
    # ایجاد دیکشنری برای حمل‌ها بر اساس allocation
    transport_dict = {}
    for transport in all_transports:
        if transport.allocation:
            allocation_number = transport.allocation.allocation_number
            if allocation_number not in transport_dict:
                transport_dict[allocation_number] = []
            transport_dict[allocation_number].append(transport)

    # Annotate کردن وزن سفارش، وزن تحویلی و مبلغ اختلاف
    for order in orders_qs:
        # محاسبه وزن سفارش
        order_weight = Decimal('0')
        for item in order.order_items.all():
            weight_kg = item.get_weight_in_kg()
            order_weight += Decimal(str(weight_kg))
        order._order_weight = order_weight
        
        # محاسبه وزن تحویلی
        allocation_numbers = allocation_dict.get(order.pk, [])
        delivered_weight = Decimal('0')
        for alloc_num in allocation_numbers:
            transports = transport_dict.get(alloc_num, [])
            for transport in transports:
                if transport.net_weight:
                    delivered_weight += Decimal(str(transport.net_weight))
        order._delivered_weight = delivered_weight
        
        # محاسبه میانگین وزن‌دار فی فروش
        total_price = Decimal('0')
        total_weight_for_avg = Decimal('0')
        
        for item in order.order_items.all():
            if item.unit_price and item.quantity:
                item_weight = Decimal(str(item.get_weight_in_kg()))
                item_price = Decimal(str(item.unit_price))
                total_price += item_weight * item_price
                total_weight_for_avg += item_weight
        
        if total_weight_for_avg > 0:
            weighted_avg_price = total_price / total_weight_for_avg
        else:
            weighted_avg_price = Decimal('0')
        
        # محاسبه مبلغ اختلاف
        weight_difference = delivered_weight - order_weight
        difference_amount = weight_difference * weighted_avg_price
        order._difference_amount = difference_amount

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار تسویه لود شد")

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = {
        'order_number': True,
        'customer_name': True,
        'order_weight': True,
        'delivered_weight': True,
        'difference_amount': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2
    table = PendingSettlementOrderTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'سفارش‌های در انتظار تسویه',
    }
    return render(request, 'settlement/settlement_list.html', context)


@login_required
def settlement_detail_view(request, order_number):
    """
    جزئیات تسویه سفارش و ثبت تراکنش‌ها
    """
    audit_logger.info(f"درخواست تسویه برای سفارش {order_number}")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SALES_SETTLEMENT.value):
        audit_logger.activity(f"تلاش برای تسویه سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تسویه سفارش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if order.status != 'pending_settlement':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_settlement می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تسویه نیست.')
        return redirect('sales:settlement_list')

    # محاسبه وزن سفارش
    order_weight = Decimal('0')
    for item in order.order_items.all():
        weight_kg = item.get_weight_in_kg()
        order_weight += Decimal(str(weight_kg))
    
    # محاسبه وزن تحویلی
    allocations = Allocation.objects.filter(order=order)
    transports = Transport.objects.filter(allocation__in=allocations)
    delivered_weight = sum(
        Decimal(str(t.net_weight or 0)) for t in transports
    )
    
    # محاسبه اختلاف وزن
    weight_difference = delivered_weight - order_weight
    
    # محاسبه میانگین وزن‌دار فی فروش
    total_price = Decimal('0')
    total_weight_for_avg = Decimal('0')
    
    for item in order.order_items.all():
        if item.unit_price and item.quantity:
            item_weight = Decimal(str(item.get_weight_in_kg()))
            item_price = Decimal(str(item.unit_price))
            total_price += item_weight * item_price
            total_weight_for_avg += item_weight
    
    # محاسبه میانگین فی
    if total_weight_for_avg > 0:
        weighted_avg_price = total_price / total_weight_for_avg
    else:
        weighted_avg_price = Decimal('0')
    
    # محاسبه مبلغ اختلاف
    difference_amount = weight_difference * weighted_avg_price
    
    # دریافت یا ایجاد Settlement با نوع کسری و سرک
    settlement, created = Settlement.objects.get_or_create(
        order=order,
        settlement_type='weight_discrepancy',
        defaults={
            'debtor_person': order.customer,
            'original_document_amount': difference_amount,
            'settled_amount': Decimal('0'),
            'settlement_status': 'pending',
        }
    )
    
    # دریافت تراکنش‌های ثبت شده
    transactions = TransactionDocument.objects.filter(settlement=settlement).order_by('-id')
    
    # محاسبه مجموع مبلغ تراکنش‌های ثبت شده
    settled_amount = transactions.aggregate(total=Sum('document_amount'))['total'] or Decimal('0')
    
    # محاسبه مانده
    remaining_amount = abs(difference_amount) - settled_amount
    
    # بررسی اتمام تسویه
    settlement_completed = remaining_amount <= 0
    
    # بررسی اینکه آیا مبلغ اختلاف صفر است (با توجه به خطای محاسباتی)
    has_no_difference = abs(difference_amount) < Decimal('0.01')
    
    # لاگ برای دیباگ
    bug_logger.debug(f"سفارش {order_number}: difference_amount={difference_amount}, has_no_difference={has_no_difference}, settlement_completed={settlement_completed}")
    
    # دریافت اطلاعات مشتری
    customer = order.customer
    customer_info = None
    if customer:
        from core.PersonFolder.FinancialBankingModel import FinancialBanking
        from core.PersonFolder.BankAccountModel import BankAccount
        
        # دریافت حساب‌های بانکی
        financial_banking = FinancialBanking.objects.filter(person=customer).first()
        bank_accounts = []
        if financial_banking:
            bank_accounts = BankAccount.objects.filter(financial_banking=financial_banking)
        
        customer_info = {
            'name': customer.name,
            'national_id': customer.national_id,
            'type': customer.get_type_display() if customer.type else '-',
            'nature': customer.get_nature_display() if customer.nature else '-',
            'accounting_code': customer.accounting_code or '-',
            'registration_number': customer.registration_number or '-',
            'bank_accounts': bank_accounts,
        }
    
    if request.method == 'POST':
        form = SettlementTransactionForm(
            request.POST, 
            request.FILES,
            difference_amount=difference_amount,
            customer=customer,
            settled_amount=settled_amount
        )
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ایجاد تراکنش جدید
                    transaction_doc = form.save(commit=False)
                    transaction_doc.settlement = settlement
                    
                    # تنظیم discrepancy_type بر اساس difference_amount
                    if difference_amount > 0:
                        transaction_doc.discrepancy_type = 'surplus'  # سرک
                    elif difference_amount < 0:
                        transaction_doc.discrepancy_type = 'shortage'  # کسری
                    
                    # تولید شماره سند حسابداری
                    if not transaction_doc.accounting_document_number:
                        transaction_doc.generate_accounting_document_number()
                    
                    transaction_doc.save()
                    
                    # به‌روزرسانی مبلغ تسویه شده
                    new_settled_amount = settled_amount + transaction_doc.document_amount
                    settlement.settled_amount = new_settled_amount
                    
                    # بررسی اتمام تسویه
                    new_remaining = abs(difference_amount) - new_settled_amount
                    if new_remaining <= 0:
                        settlement.settlement_status = 'completed'
                        order.status = 'pending_settlement_approval'
                        order.save(update_fields=['status'])
                        messages.success(request, f'تراکنش با موفقیت ثبت شد. تسویه سفارش {order_number} کامل شد و به وضعیت "در انتظار تایید تسویه کامل" منتقل شد.')
                    else:
                        settlement.settlement_status = 'partial'
                        messages.success(request, f'تراکنش با موفقیت ثبت شد. مانده تسویه: {new_remaining:,.0f} ریال')
                    
                    settlement.save(update_fields=['settled_amount', 'settlement_status'])
                    
                    bug_logger.info(f"تراکنش جدید برای سفارش {order_number} ثبت شد")
                    audit_logger.activity(f"تراکنش جدید برای سفارش {order_number} ثبت شد توسط کاربر {request.user.username}")
                    
                    # اگر تسویه کامل شد، به لیست برگرد
                    if new_remaining <= 0:
                        return redirect('sales:settlement_list')
                    else:
                        # وگرنه صفحه را reload کن
                        return redirect('sales:settlement_detail', order_number=order_number)
                    
            except Exception as e:
                bug_logger.error(f"خطا در ثبت تراکنش: {str(e)}")
                messages.error(request, f'خطا در ثبت تراکنش: {str(e)}')
        else:
            # نمایش خطاهای فرم
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SettlementTransactionForm(
            difference_amount=difference_amount,
            customer=customer,
            settled_amount=settled_amount
        )
    
    context = {
        'form': form,
        'order': order,
        'order_weight': order_weight,
        'delivered_weight': delivered_weight,
        'weight_difference': weight_difference,
        'weighted_avg_price': weighted_avg_price,
        'difference_amount': difference_amount,
        'settled_amount': settled_amount,
        'remaining_amount': remaining_amount,
        'settlement_completed': settlement_completed,
        'has_no_difference': has_no_difference,
        'transactions': transactions,
        'customer_info': customer_info,
        'page_title': f'تسویه سفارش - {order.order_number}',
    }
    return render(request, 'settlement/settlement_detail.html', context)


@login_required
def skip_settlement_view(request, order_number):
    """
    رد کردن تسویه و انتقال مستقیم به مرحله تایید تسویه کامل
    زمانی که مبلغ اختلاف صفر است
    """
    audit_logger.info(f"درخواست رد کردن تسویه برای سفارش {order_number}")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SALES_SETTLEMENT.value):
        audit_logger.activity(f"تلاش برای رد کردن تسویه سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تسویه سفارش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    order = get_object_or_404(Order, order_number=order_number)
    
    if order.status != 'pending_settlement':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_settlement می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای رد کردن تسویه نیست.')
        return redirect('sales:settlement_list')
    
    try:
        with transaction.atomic():
            # محاسبه مبلغ اختلاف برای بررسی
            order_weight = Decimal('0')
            for item in order.order_items.all():
                weight_kg = item.get_weight_in_kg()
                order_weight += Decimal(str(weight_kg))
            
            allocations = Allocation.objects.filter(order=order)
            transports = Transport.objects.filter(allocation__in=allocations)
            delivered_weight = sum(
                Decimal(str(t.net_weight or 0)) for t in transports
            )
            
            weight_difference = delivered_weight - order_weight
            
            # محاسبه میانگین وزن‌دار فی فروش
            total_price = Decimal('0')
            total_weight_for_avg = Decimal('0')
            
            for item in order.order_items.all():
                if item.unit_price and item.quantity:
                    item_weight = Decimal(str(item.get_weight_in_kg()))
                    item_price = Decimal(str(item.unit_price))
                    total_price += item_weight * item_price
                    total_weight_for_avg += item_weight
            
            if total_weight_for_avg > 0:
                weighted_avg_price = total_price / total_weight_for_avg
            else:
                weighted_avg_price = Decimal('0')
            
            difference_amount = weight_difference * weighted_avg_price
            
            # بررسی اینکه مبلغ اختلاف صفر است
            if abs(difference_amount) > Decimal('0.01'):  # با توجه به خطای محاسباتی
                messages.error(request, 'امکان رد کردن تسویه فقط زمانی وجود دارد که مبلغ اختلاف صفر باشد.')
                return redirect('sales:settlement_detail', order_number=order_number)
            
            # تغییر وضعیت سفارش به pending_settlement_approval
            order.status = 'pending_settlement_approval'
            order.save(update_fields=['status'])
            
            # به‌روزرسانی Settlement (اگر وجود دارد)
            settlement, created = Settlement.objects.get_or_create(
                order=order,
                settlement_type='weight_discrepancy',
                defaults={
                    'debtor_person': order.customer,
                    'original_document_amount': Decimal('0'),
                    'settled_amount': Decimal('0'),
                    'settlement_status': 'completed',
                }
            )
            
            if not created:
                settlement.settlement_status = 'completed'
                settlement.original_document_amount = Decimal('0')
                settlement.settled_amount = Decimal('0')
                settlement.save(update_fields=['settlement_status', 'original_document_amount', 'settled_amount'])
            
            bug_logger.info(f"تسویه سفارش {order_number} رد شد و به وضعیت 'در انتظار تایید تسویه کامل' منتقل شد")
            audit_logger.activity(f"تسویه سفارش {order_number} رد شد و به وضعیت 'در انتظار تایید تسویه کامل' منتقل شد توسط کاربر {request.user.username}")
            messages.success(request, f'سفارش {order_number} به وضعیت "در انتظار تایید تسویه کامل" منتقل شد.')
            
            return redirect('sales:settlement_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در رد کردن تسویه: {str(e)}")
        messages.error(request, f'خطا در رد کردن تسویه: {str(e)}')
        return redirect('sales:settlement_detail', order_number=order_number)

