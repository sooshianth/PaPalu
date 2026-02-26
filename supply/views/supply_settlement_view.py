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
from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
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
    ).select_related('allocation').prefetch_related('raw_material_infos__order_item')
    
    # ایجاد دیکشنری برای حمل‌ها بر اساس allocation
    transport_dict = {}
    for transport in all_transports:
        if transport.allocation:
            allocation_number = transport.allocation.allocation_number
            if allocation_number not in transport_dict:
                transport_dict[allocation_number] = []
            transport_dict[allocation_number].append(transport)

    # Annotate کردن وزن سفارش، وزن تحویلی و مبلغ اختلاف (فی به ازای واحد هر قلم است)
    for order in orders_qs:
        order_weight = Decimal('0')
        for item in order.order_items.all():
            order_weight += Decimal(str(item.get_weight_in_kg()))
        
        allocation_numbers = allocation_dict.get(order.pk, [])
        transports_for_order = [t for alloc_num in allocation_numbers for t in transport_dict.get(alloc_num, [])]
        delivered_weight = Decimal('0')
        for transport in transports_for_order:
            w = getattr(transport, 'waybill_weight', None) or transport.net_weight
            if w:
                delivered_weight += Decimal(str(w))
        
        # توزیع وزن تحویلی به هر قلم سفارش (مثل جزئیات)
        order_item_ids = list(order.order_items.values_list('id', flat=True))
        delivered_per_order_item = {}
        for transport in transports_for_order:
            w = getattr(transport, 'waybill_weight', None) or transport.net_weight
            if not w:
                continue
            w = Decimal(str(w))
            infos = list(transport.raw_material_infos.select_related('order_item').all())
            total_alloc = sum(Decimal(str(rmi.allocated_quantity)) for rmi in infos if rmi.allocated_quantity)
            if total_alloc and total_alloc > 0:
                for rmi in infos:
                    if rmi.order_item_id and rmi.allocated_quantity:
                        part = w * (Decimal(str(rmi.allocated_quantity)) / total_alloc)
                        delivered_per_order_item[rmi.order_item_id] = delivered_per_order_item.get(rmi.order_item_id, Decimal('0')) + part
            elif len(order_item_ids) == 1:
                delivered_per_order_item[order_item_ids[0]] = delivered_per_order_item.get(order_item_ids[0], Decimal('0')) + w
        
        # مبلغ اختلاف = جمع اختلاف هر قلم (فی هر قلم به ازای واحد خودش: کیلو یا لیتر و ...)
        difference_amount = Decimal('0')
        for order_item in order.order_items.all():
            if not order_item.raw_material or not order_item.unit_price:
                continue
            allocated_weight = Decimal(str(order_item.get_weight_in_kg()))
            item_delivered = delivered_per_order_item.get(order_item.id, Decimal('0'))
            unit_price = Decimal(str(order_item.unit_price))
            if order_item.is_purchased_in_secondary_unit():
                allocated_sec = order_item.kg_to_order_unit(allocated_weight)
                delivered_sec = order_item.kg_to_order_unit(item_delivered)
                difference_amount += (delivered_sec - allocated_sec) * unit_price
            else:
                difference_amount += (item_delivered - allocated_weight) * unit_price
        
        order._order_weight = order_weight
        order._delivered_weight = delivered_weight
        order._difference_amount = difference_amount

    # لیست آبجکت‌ها را به جدول بده (نه QuerySet) تا با صفحه‌بندی، slice همان instanceهای دارای
    # _order_weight و ... باشد؛ وگرنه django-tables2 روی QuerySet slice میزند و instanceهای جدید
    # از دیتابیس می‌آید که این attributeها را ندارند و خطای 500 می‌دهد.
    orders_list = list(orders_qs)
    bug_logger.debug(f"تعداد {len(orders_list)} سفارش خرید در انتظار تسویه لود شد")

    # جمع کل‌ها برای نمایش بالای جدول
    total_order_weight = sum((o._order_weight for o in orders_list), Decimal('0'))
    total_delivered_weight = sum((o._delivered_weight for o in orders_list), Decimal('0'))
    total_difference_amount = sum((o._difference_amount for o in orders_list), Decimal('0'))

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
        'total_order_weight': total_order_weight,
        'total_delivered_weight': total_delivered_weight,
        'total_difference_amount': total_difference_amount,
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
    # در خرید، وزن تحویلی برای پرداخت سرک/کسری = مجموع وزن بارنامه (waybill_weight)، نه باسکول
    order_weight = Decimal('0')
    delivered_weight = Decimal('0')
    
    # محاسبه وزن سفارش
    for order_item in order.order_items.all():
        weight_kg = order_item.get_weight_in_kg()
        order_weight += Decimal(str(weight_kg))
    
    # محاسبه وزن تحویلی از وزن بارنامه‌ها
    for transport in transports:
        w = getattr(transport, 'waybill_weight', None) or transport.net_weight
        if w:
            delivered_weight += Decimal(str(w))
    
    # وزن تحویلی به تفکیک هر ماده اولیه: توزیع وزن بارنامه هر حمل بر اساس نسبت تخصیص (allocated_quantity)
    delivered_per_order_item = {}
    order_item_ids = list(order.order_items.values_list('id', flat=True))
    for transport in transports:
        w = getattr(transport, 'waybill_weight', None) or transport.net_weight
        if not w:
            continue
        w = Decimal(str(w))
        infos = list(transport.raw_material_infos.select_related('order_item').all())
        total_alloc = sum(Decimal(str(rmi.allocated_quantity)) for rmi in infos if rmi.allocated_quantity)
        if total_alloc and total_alloc > 0:
            for rmi in infos:
                if rmi.order_item_id and rmi.allocated_quantity:
                    part = w * (Decimal(str(rmi.allocated_quantity)) / total_alloc)
                    delivered_per_order_item[rmi.order_item_id] = delivered_per_order_item.get(rmi.order_item_id, Decimal('0')) + part
        elif len(order_item_ids) == 1:
            # حمل بدون RawMaterialInfo ولی سفارش فقط یک ماده دارد → کل وزن به همان ماده
            delivered_per_order_item[order_item_ids[0]] = delivered_per_order_item.get(order_item_ids[0], Decimal('0')) + w
    
    # محاسبه اختلاف برای هر ماده اولیه (برای نمایش جزئیات)
    # فی (unit_price) در سفارش خرید به ازای همان واحد انتخابی است (ریال/کیلوگرم یا ریال/لیتر و ...)
    material_discrepancies = []
    total_difference_amount = Decimal('0')
    
    for order_item in order.order_items.all():
        raw_material = order_item.raw_material
        if not raw_material:
            continue
        
        allocated_weight = Decimal(str(order_item.get_weight_in_kg()))
        item_delivered = delivered_per_order_item.get(order_item.id, Decimal('0'))
        item_weight_diff = item_delivered - allocated_weight
        
        unit_price = Decimal(str(order_item.unit_price)) if order_item.unit_price else Decimal('0')
        # مبلغ اختلاف این ماده: اگر خرید با واحد ثانویه (مثلاً لیتر) بوده، فی به ازای همان واحد است
        if order_item.is_purchased_in_secondary_unit():
            allocated_secondary = order_item.kg_to_order_unit(allocated_weight)
            delivered_secondary = order_item.kg_to_order_unit(item_delivered)
            diff_secondary = delivered_secondary - allocated_secondary
            item_difference_amount = diff_secondary * unit_price
            secondary_unit_display = order_item.get_weight_unit_display()
            allocated_secondary_val = allocated_secondary
            delivered_secondary_val = delivered_secondary
        else:
            item_difference_amount = item_weight_diff * unit_price
            secondary_unit_display = ''
            allocated_secondary_val = None
            delivered_secondary_val = None
        
        total_difference_amount += item_difference_amount
        
        # برچسب فی برای نمایش (ریال/کیلوگرم یا ریال/لیتر و ...)
        unit_price_label = f"ریال/{order_item.get_weight_unit_display()}" if order_item.weight_unit else "ریال"
        
        material_discrepancies.append({
            'material_name': raw_material.name if raw_material.name else 'نامشخص',
            'allocated_weight': allocated_weight,
            'delivered_weight': item_delivered,
            'weight_difference': item_weight_diff,
            'unit_price': unit_price,
            'unit_price_label': unit_price_label,
            'difference_amount': item_difference_amount,
            'allocated_secondary': allocated_secondary_val,
            'delivered_secondary': delivered_secondary_val,
            'secondary_unit_display': secondary_unit_display,
        })
    
    weight_difference = delivered_weight - order_weight
    
    # مبلغ اختلاف کل = جمع مبالغ اختلاف هر ماده (بر اساس فی هر ماده در واحد خودش)
    difference_amount = total_difference_amount
    
    # میانگین وزن‌دار فی فقط برای نمایش در صورت نیاز (محاسبه کل دیگر از آن استفاده نمی‌کند)
    total_price = Decimal('0')
    total_weight_for_avg = Decimal('0')
    for item in order.order_items.all():
        if item.unit_price and item.quantity:
            qty = Decimal(str(item.quantity))
            item_price = Decimal(str(item.unit_price))
            total_price += qty * item_price
            total_weight_for_avg += Decimal(str(item.get_weight_in_kg()))
    weighted_avg_price = (total_price / total_weight_for_avg) if total_weight_for_avg > 0 else Decimal('0')
    
    # وزن به واحد ثانویه - وقتی خرید با واحد ثانویه بوده (برای نمایش در سطر جدا)
    order_weight_secondary = None
    delivered_weight_secondary = None
    secondary_unit_display_summary = ''
    order_items_list = list(order.order_items.select_related('raw_material').filter(raw_material__isnull=False))
    if len(order_items_list) == 1 and order_items_list[0].is_purchased_in_secondary_unit():
        oi = order_items_list[0]
        secondary_unit_display_summary = oi.get_weight_unit_display()
        order_weight_secondary = oi.quantity
        delivered_weight_secondary = oi.kg_to_order_unit(delivered_per_order_item.get(oi.id, Decimal('0')))
    
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
    
    # برای نوار پیشرفت: درصد تسویه شده (مبلغ اختلاف ممکن است منفی باشد)
    difference_amount_abs = abs(difference_amount)
    if settlement_completed or difference_amount_abs < Decimal('0.01'):
        progress_percent = 100
    else:
        progress_percent = min(100, float(settled_amount / difference_amount_abs * 100))
    
    # بررسی اینکه آیا مبلغ اختلاف صفر است (با توجه به خطای محاسباتی)
    has_no_difference = difference_amount_abs < Decimal('0.01')
    
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
        'difference_amount_abs': difference_amount_abs,
        'progress_percent': progress_percent,
        'settled_amount': settled_amount,
        'remaining_amount': remaining_amount,
        'settlement_completed': settlement_completed,
        'has_no_difference': has_no_difference,
        'transactions': transactions,
        'supplier_info': supplier_info,
        'material_discrepancies': material_discrepancies,
        'order_weight_secondary': order_weight_secondary,
        'delivered_weight_secondary': delivered_weight_secondary,
        'secondary_unit_display_summary': secondary_unit_display_summary,
        'has_any_secondary_in_discrepancies': any(d.get('secondary_unit_display') for d in material_discrepancies),
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
            allocations = Allocation.objects.filter(order=order)
            transports = Transport.objects.filter(
                allocation__in=allocations,
                direction='inbound'
            ).prefetch_related('raw_material_infos__order_item')
            
            order_weight = Decimal('0')
            for item in order.order_items.all():
                order_weight += Decimal(str(item.get_weight_in_kg()))
            
            delivered_weight = Decimal('0')
            for transport in transports:
                w = getattr(transport, 'waybill_weight', None) or transport.net_weight
                if w:
                    delivered_weight += Decimal(str(w))
            
            order_item_ids = list(order.order_items.values_list('id', flat=True))
            delivered_per_order_item = {}
            for transport in transports:
                w = getattr(transport, 'waybill_weight', None) or transport.net_weight
                if not w:
                    continue
                w = Decimal(str(w))
                infos = list(transport.raw_material_infos.select_related('order_item').all())
                total_alloc = sum(Decimal(str(rmi.allocated_quantity)) for rmi in infos if rmi.allocated_quantity)
                if total_alloc and total_alloc > 0:
                    for rmi in infos:
                        if rmi.order_item_id and rmi.allocated_quantity:
                            part = w * (Decimal(str(rmi.allocated_quantity)) / total_alloc)
                            delivered_per_order_item[rmi.order_item_id] = delivered_per_order_item.get(rmi.order_item_id, Decimal('0')) + part
                elif len(order_item_ids) == 1:
                    delivered_per_order_item[order_item_ids[0]] = delivered_per_order_item.get(order_item_ids[0], Decimal('0')) + w
            
            difference_amount = Decimal('0')
            for order_item in order.order_items.all():
                if not order_item.raw_material or not order_item.unit_price:
                    continue
                allocated_weight = Decimal(str(order_item.get_weight_in_kg()))
                item_delivered = delivered_per_order_item.get(order_item.id, Decimal('0'))
                unit_price = Decimal(str(order_item.unit_price))
                if order_item.is_purchased_in_secondary_unit():
                    allocated_sec = order_item.kg_to_order_unit(allocated_weight)
                    delivered_sec = order_item.kg_to_order_unit(item_delivered)
                    difference_amount += (delivered_sec - allocated_sec) * unit_price
                else:
                    difference_amount += (item_delivered - allocated_weight) * unit_price
            
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
