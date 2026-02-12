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
from supply.tables import PendingSupplySettlementApprovalOrderTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def supply_settlement_approval_list_view(request):
    """
    لیست سفارش‌های خرید در وضعیت «در انتظار تایید تسویه کامل»
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های خرید در انتظار تایید تسویه کامل")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SUPPLY_APPROVE_SETTLEMENT.value):
        audit_logger.activity("تلاش برای مشاهده لیست تایید تسویه کامل خرید بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید تسویه کامل را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های خرید در انتظار تایید تسویه کامل
    orders_qs = Order.objects.filter(
        order_type='purchase',
        status='pending_supply_settlement_approval'
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
        direction='inbound'
    ).select_related('allocation')
    
    # ایجاد دیکشنری برای حمل‌ها بر اساس allocation
    transport_dict = {}
    for transport in all_transports:
        if transport.allocation:
            allocation_number = transport.allocation.allocation_number
            if allocation_number not in transport_dict:
                transport_dict[allocation_number] = []
            transport_dict[allocation_number].append(transport)

    # تبدیل QuerySet به list برای اضافه کردن فیلدهای محاسبه شده
    orders_list = list(orders_qs)
    
    # Annotate کردن وزن سفارش، وزن تحویلی و مبلغ اختلاف
    for order in orders_list:
        # محاسبه وزن سفارش
        order_weight = Decimal('0')
        for item in order.order_items.all():
            weight_kg = item.get_weight_in_kg()
            order_weight += Decimal(str(weight_kg))
        order._order_weight = order_weight
        
        # محاسبه وزن تحویلی (برای پرداخت سرک/کسری بر اساس وزن بارنامه)
        allocation_numbers = allocation_dict.get(order.pk, [])
        delivered_weight = Decimal('0')
        for alloc_num in allocation_numbers:
            transports = transport_dict.get(alloc_num, [])
            for transport in transports:
                w = getattr(transport, 'waybill_weight', None) or transport.net_weight
                if w:
                    delivered_weight += Decimal(str(w))
        order._delivered_weight = delivered_weight
        
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
        
        # محاسبه مبلغ اختلاف
        weight_difference = delivered_weight - order_weight
        difference_amount = weight_difference * weighted_avg_price
        order._difference_amount = difference_amount
        
        # محاسبه مبلغ تسویه شده
        settlement = Settlement.objects.filter(
            order=order,
            settlement_type='weight_discrepancy'
        ).first()
        
        if settlement:
            settled_amount = settlement.transaction_documents.aggregate(
                total=Sum('document_amount')
            )['total'] or Decimal('0')
        else:
            settled_amount = Decimal('0')
        
        order._settled_amount = settled_amount

    bug_logger.debug(f"تعداد {len(orders_list)} سفارش خرید در انتظار تایید تسویه کامل لود شد")

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = {
        'order_number': True,
        'supplier_name': True,
        'order_weight': True,
        'delivered_weight': True,
        'difference_amount': True,
        'settled_amount': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2
    table = PendingSupplySettlementApprovalOrderTable(orders_list, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'سفارش‌های خرید در انتظار تایید تسویه کامل',
    }
    return render(request, 'supply_settlement/supply_settlement_approval_list.html', context)


@login_required
def supply_settlement_approval_detail_view(request, order_number):
    """
    جزئیات تایید تسویه کامل سفارش خرید
    """
    audit_logger.info(f"درخواست تایید تسویه کامل برای سفارش خرید {order_number}")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SUPPLY_APPROVE_SETTLEMENT.value):
        audit_logger.activity(f"تلاش برای تایید تسویه کامل سفارش خرید {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید تسویه کامل را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number, order_type='purchase')

    if order.status != 'pending_supply_settlement_approval':
        bug_logger.warning(f"سفارش خرید {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_supply_settlement_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تایید تسویه کامل نیست.')
        return redirect('supply:supply_settlement_approval_list')

    # محاسبه وزن سفارش
    order_weight = Decimal('0')
    for item in order.order_items.all():
        weight_kg = item.get_weight_in_kg()
        order_weight += Decimal(str(weight_kg))
    
    # محاسبه وزن تحویلی (برای پرداخت سرک/کسری بر اساس وزن بارنامه)
    allocations = Allocation.objects.filter(order=order)
    transports = Transport.objects.filter(
        allocation__in=allocations,
        direction='inbound'
    )
    delivered_weight = sum(
        Decimal(str(getattr(t, 'waybill_weight', None) or t.net_weight or 0)) for t in transports
    )
    
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
    
    # محاسبه میانگین فی
    if total_weight_for_avg > 0:
        weighted_avg_price = total_price / total_weight_for_avg
    else:
        weighted_avg_price = Decimal('0')
    
    # محاسبه مبلغ اختلاف
    difference_amount = weight_difference * weighted_avg_price
    
    # دریافت Settlement مربوط به کسری و سرک
    weight_discrepancy_settlement = Settlement.objects.filter(
        order=order,
        settlement_type='weight_discrepancy'
    ).first()
    
    # دریافت تراکنش‌های کسری و سرک
    weight_discrepancy_transactions = []
    if weight_discrepancy_settlement:
        weight_discrepancy_transactions = TransactionDocument.objects.filter(
            settlement=weight_discrepancy_settlement
        ).order_by('-id')
    
    # محاسبه مجموع مبلغ تراکنش‌های کسری و سرک
    settled_weight_discrepancy = weight_discrepancy_transactions.aggregate(
        total=Sum('document_amount')
    )['total'] or Decimal('0')
    
    # بررسی اتمام تسویه کسری و سرک
    weight_discrepancy_completed = abs(difference_amount) - settled_weight_discrepancy <= 0
    
    # دریافت اطلاعات تأمین‌کننده
    supplier = order.customer
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
    
    # دریافت اطلاعات تخصیص‌ها و حمل‌ها
    allocations_with_transports = []
    for allocation in allocations:
        alloc_transports = transports.filter(allocation=allocation)
        allocations_with_transports.append({
            'allocation': allocation,
            'transports': alloc_transports,
        })
    
    if request.method == 'POST':
        # تایید تسویه کامل
        try:
            with transaction.atomic():
                # تغییر وضعیت سفارش به completed (تکمیل شده)
                order.status = 'completed'
                order.save(update_fields=['status'])
                
                # به‌روزرسانی وضعیت Settlement به completed
                if weight_discrepancy_settlement:
                    weight_discrepancy_settlement.settlement_status = 'completed'
                    weight_discrepancy_settlement.save(update_fields=['settlement_status'])
                
                bug_logger.info(f"تایید تسویه کامل برای سفارش خرید {order_number} ثبت شد و به وضعیت 'تکمیل شده' تغییر کرد")
                messages.success(request, f'تایید تسویه کامل برای سفارش خرید {order_number} با موفقیت ثبت شد. سفارش در حال حاضر در وضعیت «تکمیل شده» قرار دارد.')
                audit_logger.activity(f"تایید تسویه کامل برای سفارش خرید {order_number} ثبت شد و به وضعیت 'تکمیل شده' تغییر کرد توسط کاربر {request.user.username}")
                
                return redirect('supply:supply_settlement_approval_list')
                
        except Exception as e:
            bug_logger.error(f"خطا در تایید تسویه کامل: {str(e)}")
            messages.error(request, f'خطا در تایید تسویه کامل: {str(e)}')
    
    context = {
        'order': order,
        'order_weight': order_weight,
        'delivered_weight': delivered_weight,
        'weight_difference': weight_difference,
        'weighted_avg_price': weighted_avg_price,
        'difference_amount': difference_amount,
        'settled_weight_discrepancy': settled_weight_discrepancy,
        'weight_discrepancy_completed': weight_discrepancy_completed,
        'weight_discrepancy_transactions': weight_discrepancy_transactions,
        'supplier_info': supplier_info,
        'allocations_with_transports': allocations_with_transports,
        'page_title': f'تایید تسویه کامل - سفارش خرید {order.order_number}',
    }
    return render(request, 'supply_settlement/supply_settlement_approval_detail.html', context)
