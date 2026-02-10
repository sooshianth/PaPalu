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
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument, TransactionDocumentAttachment
from supply.forms.supply_settlement_transaction_form import SupplySettlementTransactionForm
from supply.tables import PendingSupplySettlementOrderTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def supply_settlement_list_view(request):
    """
    لیست سفارش‌های خرید در وضعیت «در انتظار تسویه»
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های خرید در انتظار تسویه")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SUPPLY_SETTLEMENT.value):
        audit_logger.activity("تلاش برای مشاهده لیست تسویه خرید بدون دسترسی")
        messages.error(request, 'شما دسترسی به تسویه سفارش خرید را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های خرید در انتظار تسویه
    orders_qs = Order.objects.filter(
        order_type='purchase',
        status='awaiting_final_settlement'
    ).select_related('customer').prefetch_related(
        'order_items',
        'allocations',
        'order_items__raw_material'
    ).order_by('-created_at')

    # دریافت تمام تخصیص‌ها و حمل‌ها به صورت bulk
    all_allocations = Allocation.objects.filter(order__in=orders_qs).select_related('order')
    allocation_dict = {}
    for alloc in all_allocations:
        if alloc.order_id not in allocation_dict:
            allocation_dict[alloc.order_id] = []
        allocation_dict[alloc.order_id].append(alloc.allocation_number)
    
    all_allocations = Allocation.objects.filter(allocation_number__in=[num for nums in allocation_dict.values() for num in nums])
    all_transports = Transport.objects.filter(
        allocation__in=all_allocations,
        direction='inbound'  # فقط حمل‌های ورودی
    ).select_related('allocation')
    
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
        
        # محاسبه وزن تحویلی از بارنامه‌ها
        allocation_numbers = allocation_dict.get(order.pk, [])
        transports_for_order = [t for alloc_num in allocation_numbers for t in transport_dict.get(alloc_num, [])]
        delivered_weight = Decimal('0')
        for transport in transports_for_order:
            if transport.net_weight:
                delivered_weight += Decimal(str(transport.net_weight))
        
        # محاسبه اختلاف وزن
        weight_difference = delivered_weight - order_weight
        
        # محاسبه میانگین وزن‌دار فی خرید
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
        
        # مبلغ اختلاف
        difference_amount = weight_difference * weighted_avg_price
        
        order._order_weight = order_weight
        order._delivered_weight = delivered_weight
        order._difference_amount = difference_amount

    # لیست آبجکت‌ها را به جدول بده (نه QuerySet) تا با صفحه‌بندی، slice همان instanceهای دارای
    # _order_weight و ... باشد؛ وگرنه django-tables2 روی QuerySet slice میزند و instanceهای جدید
    # از دیتابیس می‌آید که این attributeها را ندارند و خطای 500 می‌دهد.
    orders_list = list(orders_qs)
    bug_logger.debug(f"تعداد {len(orders_list)} سفارش خرید در انتظار تسویه لود شد")

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = {
        'order_number': True,
        'supplier_name': True,
        'order_weight': True,
        'delivered_weight': True,
        'difference_amount': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2 (با list تا pagination روی همان آبجکت‌های annotate‌شده باشد)
    table = PendingSupplySettlementOrderTable(orders_list, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'سفارش‌های خرید در انتظار تسویه',
    }
    return render(request, 'supply_settlement/supply_settlement_list.html', context)


@login_required
def supply_settlement_detail_view(request, order_number):
    """
    جزئیات تسویه سفارش خرید و ثبت تراکنش‌ها
    """
    audit_logger.info(f"درخواست تسویه برای سفارش خرید {order_number}")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SUPPLY_SETTLEMENT.value):
        audit_logger.activity(f"تلاش برای تسویه سفارش خرید {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تسویه سفارش خرید را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number, order_type='purchase')

    if order.status != 'awaiting_final_settlement':
        bug_logger.warning(f"سفارش خرید {order_number} در وضعیت {order.status} است، در حالی که انتظار awaiting_final_settlement می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تسویه نیست.')
        return redirect('supply:supply_settlement_list')

    # دریافت حمل‌های مربوط به سفارش (فقط ورودی)
    allocations = Allocation.objects.filter(order=order)
    transports = Transport.objects.filter(
        allocation__in=allocations,
        direction='inbound'
    ).prefetch_related('raw_material_infos')
    
    # محاسبه اختلاف
    # در خرید، وزن تحویلی = مجموع net_weight بارنامه‌های ورودی
    order_weight = Decimal('0')
    delivered_weight = Decimal('0')
    
    # محاسبه وزن سفارش
    for order_item in order.order_items.all():
        weight_kg = order_item.get_weight_in_kg()
        order_weight += Decimal(str(weight_kg))
    
    # محاسبه وزن تحویلی از بارنامه‌ها
    for transport in transports:
        if transport.net_weight:
            delivered_weight += Decimal(str(transport.net_weight))
    
    # محاسبه اختلاف برای هر ماده اولیه (برای نمایش جزئیات)
    material_discrepancies = []
    total_difference_amount = Decimal('0')
    
    # برای هر ماده اولیه در سفارش
    for order_item in order.order_items.all():
        raw_material = order_item.raw_material
        if not raw_material:
            continue
        
        # وزن تخصیص یافته (وزن سفارش برای این ماده اولیه)
        allocated_weight = Decimal(str(order_item.get_weight_in_kg()))
        
        # فی ماده اولیه
        unit_price = Decimal(str(order_item.unit_price)) if order_item.unit_price else Decimal('0')
        
        # ذخیره جزئیات برای نمایش
        material_discrepancies.append({
            'material_name': raw_material.name if raw_material.name else 'نامشخص',
            'allocated_weight': allocated_weight,
            'unit_price': unit_price,
        })
    
    # محاسبه مبلغ اختلاف کل بر اساس میانگین وزن‌دار فی
    weight_difference = delivered_weight - order_weight
    
    # محاسبه میانگین وزن‌دار فی خرید
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
    
    # مبلغ اختلاف کل
    total_difference_amount = weight_difference * weighted_avg_price
    
    # به‌روزرسانی material_discrepancies با وزن تحویلی و اختلاف
    # (در خرید، وزن بارنامه به طور کلی است و نمی‌توان برای هر ماده اولیه جداگانه محاسبه کرد)
    # پس فقط اطلاعات سفارش را نمایش می‌دهیم
    for discrepancy in material_discrepancies:
        discrepancy['delivered_weight'] = Decimal('0')  # نمی‌توان محاسبه کرد
        discrepancy['weight_difference'] = Decimal('0')  # نمی‌توان محاسبه کرد
        discrepancy['difference_amount'] = Decimal('0')  # نمی‌توان محاسبه کرد
    
    # مبلغ کل اختلاف
    difference_amount = total_difference_amount
    
    # دریافت یا ایجاد Settlement با نوع کسری و سرک
    # در تأمین (خرید): ما خریدار هستیم و تأمین‌کننده فروشنده است
    # اگر سرک باشد (مثبت = بیشتر تحویل شده): ما باید مابه‌التفاوت را بزنیم -> debtor: company (ما بدهکار)
    # اگر کسری باشد (منفی = کمتر تحویل شده): تأمین‌کننده باید مابه‌التفاوت را برگرداند -> debtor: supplier (تأمین‌کننده بدهکار)
    supplier = order.customer  # در سفارش خرید، customer همان تأمین‌کننده است
    
    settlement, created = Settlement.objects.get_or_create(
        order=order,
        settlement_type='weight_discrepancy',
        defaults={
            'debtor_person': None if difference_amount > 0 else supplier,  # اگر کسری: تأمین‌کننده بدهکار (کمتر تحویل داده)
            'creditor_person': supplier if difference_amount > 0 else None,  # اگر سرک: تأمین‌کننده بستانکار (بیشتر تحویل داده)
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
    bug_logger.debug(f"سفارش خرید {order_number}: difference_amount={difference_amount}, has_no_difference={has_no_difference}, settlement_completed={settlement_completed}")
    
    # دریافت اطلاعات تأمین‌کننده
    supplier_info = None
    if supplier:
        from core.PersonFolder.FinancialBankingModel import FinancialBanking
        from core.PersonFolder.BankAccountModel import BankAccount
        
        # دریافت حساب‌های بانکی
        financial_banking = FinancialBanking.objects.filter(person=supplier).first()
        bank_accounts = []
        if financial_banking:
            bank_accounts = BankAccount.objects.filter(financial_banking=financial_banking)
        
        supplier_info = {
            'name': supplier.name,
            'national_id': supplier.national_id,
            'type': supplier.get_type_display() if supplier.type else '-',
            'nature': supplier.get_nature_display() if supplier.nature else '-',
            'accounting_code': supplier.accounting_code or '-',
            'registration_number': supplier.registration_number or '-',
            'bank_accounts': bank_accounts,
        }
    
    if request.method == 'POST':
        form = SupplySettlementTransactionForm(
            request.POST, 
            request.FILES,
            difference_amount=difference_amount,
            supplier=supplier,
            settled_amount=settled_amount
        )
        
        if form.is_valid():
            doc_files = request.FILES.getlist('document_attachments')
            if not doc_files:
                messages.error(request, 'حداقل یک پیوست سند الزامی است.')
            else:
                try:
                    with transaction.atomic():
                        # ایجاد تراکنش جدید
                        transaction_doc = form.save(commit=False)
                        transaction_doc.settlement = settlement

                        # اولین فایل به عنوان پیوست اصلی
                        transaction_doc.document_attachment = doc_files[0]

                        # تنظیم discrepancy_type بر اساس difference_amount
                        if difference_amount > 0:
                            transaction_doc.discrepancy_type = 'surplus'
                        elif difference_amount < 0:
                            transaction_doc.discrepancy_type = 'shortage'

                        if not transaction_doc.accounting_document_number:
                            transaction_doc.generate_accounting_document_number()

                        transaction_doc.save()

                        # بقیه فایل‌ها به عنوان پیوست اضافی
                        for f in doc_files[1:]:
                            if f:
                                TransactionDocumentAttachment.objects.create(
                                    transaction_document=transaction_doc,
                                    file=f
                                )

                        # به‌روزرسانی مبلغ تسویه شده
                        new_settled_amount = settled_amount + transaction_doc.document_amount
                        settlement.settled_amount = new_settled_amount

                        new_remaining = abs(difference_amount) - new_settled_amount
                        if new_remaining <= 0:
                            settlement.settlement_status = 'completed'
                            order.status = 'pending_supply_settlement_approval'
                            order.save(update_fields=['status'])
                            messages.success(request, f'تراکنش با موفقیت ثبت شد. تسویه سفارش خرید {order_number} کامل شد و به وضعیت "در انتظار تایید تسویه کامل" منتقل شد.')
                        else:
                            settlement.settlement_status = 'partial'
                            messages.success(request, f'تراکنش با موفقیت ثبت شد. مانده تسویه: {new_remaining:,.0f} ریال')

                        settlement.save(update_fields=['settled_amount', 'settlement_status'])

                        bug_logger.info(f"تراکنش جدید برای سفارش خرید {order_number} ثبت شد")
                        audit_logger.activity(f"تراکنش جدید برای سفارش خرید {order_number} ثبت شد توسط کاربر {request.user.username}")

                        if new_remaining <= 0:
                            return redirect('supply:supply_settlement_list')
                        return redirect('supply:supply_settlement_detail', order_number=order_number)

                except Exception as e:
                    bug_logger.error(f"خطا در ثبت تراکنش: {str(e)}")
                    messages.error(request, f'خطا در ثبت تراکنش: {str(e)}')
        else:
            # نمایش خطاهای فرم
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = SupplySettlementTransactionForm(
            difference_amount=difference_amount,
            supplier=supplier,
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
        'supplier_info': supplier_info,
        'material_discrepancies': material_discrepancies,  # جزئیات اختلاف هر ماده اولیه
        'page_title': f'تسویه سفارش خرید - {order.order_number}',
    }
    return render(request, 'supply_settlement/supply_settlement_detail.html', context)


@login_required
def skip_supply_settlement_view(request, order_number):
    """
    رد کردن تسویه و انتقال مستقیم به مرحله تایید تسویه کامل
    زمانی که مبلغ اختلاف صفر است
    """
    audit_logger.info(f"درخواست رد کردن تسویه برای سفارش خرید {order_number}")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SUPPLY_SETTLEMENT.value):
        audit_logger.activity(f"تلاش برای رد کردن تسویه سفارش خرید {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تسویه سفارش خرید را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    order = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    
    if order.status != 'awaiting_final_settlement':
        bug_logger.warning(f"سفارش خرید {order_number} در وضعیت {order.status} است، در حالی که انتظار awaiting_final_settlement می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای رد کردن تسویه نیست.')
        return redirect('supply:supply_settlement_list')
    
    try:
        with transaction.atomic():
            # محاسبه مبلغ اختلاف برای بررسی
            allocations = Allocation.objects.filter(order=order)
            transports = Transport.objects.filter(
                allocation__in=allocations,
                direction='inbound'
            ).prefetch_related('raw_material_infos')
            
            # محاسبه وزن سفارش
            order_weight = Decimal('0')
            for item in order.order_items.all():
                weight_kg = item.get_weight_in_kg()
                order_weight += Decimal(str(weight_kg))
            
            # محاسبه وزن تحویلی از بارنامه‌ها
            delivered_weight = Decimal('0')
            for transport in transports:
                if transport.net_weight:
                    delivered_weight += Decimal(str(transport.net_weight))
            
            # محاسبه اختلاف وزن
            weight_difference = delivered_weight - order_weight
            
            # محاسبه میانگین وزن‌دار فی خرید
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
            
            # مبلغ اختلاف
            difference_amount = weight_difference * weighted_avg_price
            
            # بررسی اینکه مبلغ اختلاف صفر است
            if abs(difference_amount) > Decimal('0.01'):  # با توجه به خطای محاسباتی
                messages.error(request, 'امکان رد کردن تسویه فقط زمانی وجود دارد که مبلغ اختلاف صفر باشد.')
                return redirect('supply:supply_settlement_detail', order_number=order_number)
            
            # تغییر وضعیت سفارش به pending_supply_settlement_approval
            order.status = 'pending_supply_settlement_approval'
            order.save(update_fields=['status'])
            
            # به‌روزرسانی Settlement (اگر وجود دارد)
            # در skip اختلاف صفر است پس بدهکار/بستانکار معنا ندارد
            supplier = order.customer
            settlement, created = Settlement.objects.get_or_create(
                order=order,
                settlement_type='weight_discrepancy',
                defaults={
                    'debtor_person': None,  # اختلاف صفر - بدهکاری وجود ندارد
                    'creditor_person': None,  # اختلاف صفر - بستانکاری وجود ندارد
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
            
            bug_logger.info(f"تسویه سفارش خرید {order_number} رد شد و به وضعیت 'در انتظار تایید تسویه کامل' منتقل شد")
            audit_logger.activity(f"تسویه سفارش خرید {order_number} رد شد و به وضعیت 'در انتظار تایید تسویه کامل' منتقل شد توسط کاربر {request.user.username}")
            messages.success(request, f'سفارش خرید {order_number} به وضعیت "در انتظار تایید تسویه کامل" منتقل شد.')
            
            return redirect('supply:supply_settlement_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در رد کردن تسویه: {str(e)}")
        messages.error(request, f'خطا در رد کردن تسویه: {str(e)}')
        return redirect('supply:supply_settlement_detail', order_number=order_number)
