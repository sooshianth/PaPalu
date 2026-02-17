from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
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
from sales.tables.tables_settlement import PendingSettlementApprovalOrderTable
from sales.forms.settlement_approval_transaction_edit_form import SettlementApprovalTransactionEditForm

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def settlement_approval_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تایید تسویه کامل»
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تایید تسویه کامل")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_SETTLEMENT.value):
        audit_logger.activity("تلاش برای مشاهده لیست تایید تسویه کامل بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید تسویه کامل را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های در انتظار تایید تسویه کامل؛ ارجاع‌شده فقط برای سوپرادمین در لیست دیده می‌شود
    orders_qs = Order.objects.filter(
        status='pending_settlement_approval'
    ).select_related('customer').prefetch_related(
        'order_items',
        'allocations',
        'order_items__product'
    ).order_by('-created_at')
    if not request.user.is_superuser:
        orders_qs = orders_qs.exclude(settlement_approval_referred_to_manager=True)

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

    bug_logger.debug(f"تعداد {len(orders_list)} سفارش در انتظار تایید تسویه کامل لود شد")

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = {
        'order_number': True,
        'customer_name': True,
        'order_weight': True,
        'delivered_weight': True,
        'difference_amount': True,
        'settled_amount': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2
    table = PendingSettlementApprovalOrderTable(orders_list, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'سفارش‌های در انتظار تایید تسویه کامل',
    }
    return render(request, 'settlement_approval/settlement_approval_list.html', context)


@login_required
def settlement_approval_detail_view(request, order_number):
    """
    جزئیات تایید تسویه کامل سفارش
    """
    audit_logger.info(f"درخواست تایید تسویه کامل برای سفارش {order_number}")
    
    # بررسی دسترسی
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_SETTLEMENT.value):
        audit_logger.activity(f"تلاش برای تایید تسویه کامل سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید تسویه کامل را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    # اگر به مدیر ارجاع شده فقط سوپرادمین دسترسی دارد
    if getattr(order, 'settlement_approval_referred_to_manager', False) and not request.user.is_superuser:
        audit_logger.activity(f"تلاش برای دسترسی به تایید تسویه ارجاع‌شده به مدیر - سفارش {order_number}")
        messages.error(request, 'این سفارش به مدیر ارجاع شده و فقط مدیر می‌تواند آن را مشاهده و تایید کند.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_settlement_approval':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_settlement_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تایید تسویه کامل نیست.')
        return redirect('sales:settlement_approval_list')

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
    
    # دریافت Settlement مربوط به کسری و سرک
    weight_discrepancy_settlement = Settlement.objects.filter(
        order=order,
        settlement_type='weight_discrepancy'
    ).first()
    
    # دریافت Settlement مربوط به فروش
    sale_settlement = Settlement.objects.filter(
        order=order,
        settlement_type='sale'
    ).first()
    
    # دریافت Settlement مربوط به کرایه
    freight_settlements = Settlement.objects.filter(
        order=order,
        settlement_type='rent'
    )
    
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
    
    # دریافت تراکنش‌های فروش
    sale_transactions = []
    if sale_settlement:
        sale_transactions = TransactionDocument.objects.filter(
            settlement=sale_settlement
        ).order_by('-id')
    
    # محاسبه مجموع مبلغ تراکنش‌های فروش
    settled_sale = sale_transactions.aggregate(
        total=Sum('document_amount')
    )['total'] or Decimal('0')
    
    # دریافت تراکنش‌های کرایه
    freight_transactions = []
    freight_settled_amount = Decimal('0')
    for freight_settlement in freight_settlements:
        freight_trans = TransactionDocument.objects.filter(
            settlement=freight_settlement
        ).order_by('-id')
        freight_transactions.extend(freight_trans)
        freight_settled = freight_trans.aggregate(
            total=Sum('document_amount')
        )['total'] or Decimal('0')
        freight_settled_amount += freight_settled
    
    # بررسی اتمام تسویه کسری و سرک
    weight_discrepancy_completed = abs(difference_amount) - settled_weight_discrepancy <= 0
    
    # بررسی اتمام تسویه فروش
    sale_completed = False
    if sale_settlement and sale_settlement.original_document_amount:
        sale_completed = settled_sale >= sale_settlement.original_document_amount
    
    # بررسی اتمام تسویه کرایه
    freight_completed = True
    for freight_settlement in freight_settlements:
        if freight_settlement.original_document_amount:
            freight_settled = TransactionDocument.objects.filter(
                settlement=freight_settlement
            ).aggregate(total=Sum('document_amount'))['total'] or Decimal('0')
            if freight_settled < freight_settlement.original_document_amount:
                freight_completed = False
                break
    
    # بررسی اینکه همه تسویه‌ها کامل شده‌اند
    all_settlements_completed = (
        weight_discrepancy_completed and 
        sale_completed and 
        freight_completed
    )
    
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
    
    # دریافت اطلاعات تخصیص‌ها و حمل‌ها
    allocations_with_transports = []
    for allocation in allocations:
        alloc_transports = transports.filter(allocation=allocation)
        allocations_with_transports.append({
            'allocation': allocation,
            'transports': alloc_transports,
        })
    
    is_refer_to_manager = False
    referral_reason = ''
    invalid_edit_form = None
    invalid_edit_document_id = None
    if request.method == 'POST':
        # ذخیره ویرایش تراکنش (مدیر - در همان صفحه، بدون رفتن به صفحه جدا)
        edit_doc_id = request.POST.get('edit_transaction_document_id')
        if edit_doc_id and getattr(order, 'settlement_approval_referred_to_manager', False) and request.user.is_superuser:
            try:
                doc_id = int(edit_doc_id)
                document = TransactionDocument.objects.filter(
                    id=doc_id,
                    settlement__order=order,
                ).select_related('settlement').first()
                if document:
                    settlement = document.settlement
                    form = SettlementApprovalTransactionEditForm(
                        request.POST,
                        instance=document,
                        settlement=settlement,
                    )
                    if form.is_valid():
                        with transaction.atomic():
                            form.save()
                            new_total = TransactionDocument.objects.filter(
                                settlement=settlement
                            ).aggregate(total=Sum('document_amount'))['total'] or Decimal('0')
                            settlement.settled_amount = new_total
                            settlement.save(update_fields=['settled_amount'])
                        messages.success(request, 'تراکنش با موفقیت ذخیره شد.')
                        audit_logger.activity(
                            f"مدیر تراکنش {document.id} سفارش {order_number} را در صفحه تایید تسویه ویرایش کرد."
                        )
                        return redirect('sales:settlement_approval_detail', order_number=order_number)
                    invalid_edit_form = form
                    invalid_edit_document_id = doc_id
            except (ValueError, TypeError):
                pass

        is_refer_to_manager = request.POST.get('refer_to_manager') == '1'
        referral_reason = (request.POST.get('settlement_approval_referral_reason') or '').strip()

        # ارجاع به مدیر با دلیل اجباری
        if is_refer_to_manager:
            if not referral_reason:
                messages.error(request, 'لطفاً دلیل ارجاع به مدیر را وارد کنید.')
            else:
                try:
                    order.settlement_approval_referred_to_manager = True
                    order.settlement_approval_referred_at = timezone.now()
                    order.settlement_approval_referral_reason = referral_reason
                    order.save(update_fields=['settlement_approval_referred_to_manager', 'settlement_approval_referred_at', 'settlement_approval_referral_reason'])
                    bug_logger.info(f"سفارش {order_number} به مدیر ارجاع داده شد - تایید تسویه کامل فروش")
                    audit_logger.activity(f"تایید تسویه کامل فروش برای سفارش {order_number} به مدیر ارجاع داده شد توسط {request.user.username} - دلیل: {referral_reason[:100]}")
                    messages.warning(request, 'این سفارش به مدیر ارجاع داده شد. فقط مدیر می‌تواند آن را از همان لیست تایید تسویه باز کرده، در صورت نیاز تراکنش‌ها را ویرایش کند و در پایان «تایید مدیر» را بزند.')
                    return redirect('sales:settlement_approval_list')
                except Exception as e:
                    bug_logger.error(f"خطا در ارجاع به مدیر برای سفارش {order_number}: {e}", exc_info=True)
                    messages.error(request, f'خطا در ارجاع به مدیر: {str(e)}')
        else:
            # تایید تسویه کامل
            if not all_settlements_completed:
                messages.error(request, 'برخی از تسویه‌ها هنوز کامل نشده‌اند. امکان تایید وجود ندارد.')
            else:
                try:
                    with transaction.atomic():
                        order.status = 'archived'
                        # در صورت تایید توسط مدیر پس از ارجاع، پرچم ارجاع را پاک کن
                        if getattr(order, 'settlement_approval_referred_to_manager', False):
                            order.settlement_approval_referred_to_manager = False
                            order.settlement_approval_referred_at = None
                            order.settlement_approval_referral_reason = ''
                            order.save(update_fields=['status', 'settlement_approval_referred_to_manager', 'settlement_approval_referred_at', 'settlement_approval_referral_reason'])
                        else:
                            order.save(update_fields=['status'])

                        if weight_discrepancy_settlement:
                            weight_discrepancy_settlement.settlement_status = 'completed'
                            weight_discrepancy_settlement.save(update_fields=['settlement_status'])
                        if sale_settlement:
                            sale_settlement.settlement_status = 'completed'
                            sale_settlement.save(update_fields=['settlement_status'])
                        for freight_settlement in freight_settlements:
                            freight_settlement.settlement_status = 'completed'
                            freight_settlement.save(update_fields=['settlement_status'])

                        bug_logger.info(f"تایید تسویه کامل برای سفارش {order_number} ثبت شد و به وضعیت 'بایگانی شده' تغییر کرد")
                        messages.success(request, f'تایید تسویه کامل برای سفارش {order_number} با موفقیت ثبت شد. سفارش در حال حاضر در وضعیت «بایگانی شده» قرار دارد.')
                        audit_logger.activity(f"تایید تسویه کامل برای سفارش {order_number} ثبت شد و به وضعیت 'بایگانی شده' تغییر کرد توسط کاربر {request.user.username}")
                        return redirect('sales:settlement_approval_list')
                except Exception as e:
                    bug_logger.error(f"خطا در تایید تسویه کامل: {str(e)}")
                    messages.error(request, f'خطا در تایید تسویه کامل: {str(e)}')

    is_settlement_approval_referred = getattr(order, 'settlement_approval_referred_to_manager', False)
    show_refer_button = not is_settlement_approval_referred and not request.user.is_superuser
    settlement_approval_referral_reason = getattr(order, 'settlement_approval_referral_reason', '') or ''
    can_edit_transactions = is_settlement_approval_referred and request.user.is_superuser

    # لیست تراکنش‌های قابل ویرایش برای مدیر (کسری و سرک، فروش، کرایه) و فرم ویرایش درون‌صفحه
    editable_transactions = []
    edit_transaction_form = None
    edit_document_id = None
    if request.method == 'GET':
        raw_edit = request.GET.get('edit')
        if raw_edit:
            try:
                edit_document_id = int(raw_edit)
            except (ValueError, TypeError):
                pass
    if invalid_edit_document_id is not None:
        edit_document_id = invalid_edit_document_id
    if can_edit_transactions:
        for doc in weight_discrepancy_transactions:
            label = f"کسری و سرک - سند {doc.accounting_document_number or doc.id}"
            editable_transactions.append((doc, label))
        for doc in sale_transactions:
            label = f"فروش - سند {doc.accounting_document_number or doc.id}"
            editable_transactions.append((doc, label))
        for doc in freight_transactions:
            label = f"کرایه - سند {doc.accounting_document_number or doc.id}"
            editable_transactions.append((doc, label))
        if invalid_edit_form is not None and invalid_edit_document_id is not None:
            edit_transaction_form = invalid_edit_form
            edit_document_id = invalid_edit_document_id
        elif edit_document_id:
            doc_to_edit = TransactionDocument.objects.filter(
                id=edit_document_id,
                settlement__order=order,
            ).select_related('settlement').first()
            if doc_to_edit:
                edit_transaction_form = SettlementApprovalTransactionEditForm(
                    instance=doc_to_edit,
                    settlement=doc_to_edit.settlement,
                )
            else:
                edit_document_id = None

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
        'sale_settlement': sale_settlement,
        'settled_sale': settled_sale,
        'sale_completed': sale_completed,
        'sale_transactions': sale_transactions,
        'freight_settlements': freight_settlements,
        'freight_settled_amount': freight_settled_amount,
        'freight_completed': freight_completed,
        'freight_transactions': freight_transactions,
        'all_settlements_completed': all_settlements_completed,
        'customer_info': customer_info,
        'allocations_with_transports': allocations_with_transports,
        'page_title': f'تایید تسویه کامل - سفارش {order.order_number}',
        'is_settlement_approval_referred': is_settlement_approval_referred,
        'show_refer_button': show_refer_button,
        'settlement_approval_referral_reason': settlement_approval_referral_reason,
        'refer_modal_open': request.method == 'POST' and is_refer_to_manager and not referral_reason,
        'can_edit_transactions': can_edit_transactions,
        'editable_transactions': editable_transactions,
        'edit_transaction_form': edit_transaction_form,
        'edit_document_id': edit_document_id,
    }
    return render(request, 'settlement_approval/settlement_approval_detail.html', context)


@login_required
def settlement_approval_edit_transaction_view(request, order_number, document_id):
    """
    ویرایش یک سند تراکنش در صفحه تایید تسویه کامل.
    فقط وقتی سفارش به مدیر ارجاع شده و کاربر سوپرادمین است.
    """
    if not request.user.is_superuser:
        messages.error(request, 'فقط مدیر می‌تواند تراکنش را ویرایش کند.')
        return HttpResponseForbidden('دسترسی غیرمجاز.')

    order = get_object_or_404(Order, order_number=order_number)
    if order.status != 'pending_settlement_approval':
        messages.error(request, 'این سفارش در وضعیت مناسب برای ویرایش تراکنش نیست.')
        return redirect('sales:settlement_approval_list')

    if not getattr(order, 'settlement_approval_referred_to_manager', False):
        messages.error(request, 'ویرایش تراکنش فقط برای سفارش‌های ارجاع‌شده به مدیر امکان‌پذیر است.')
        return redirect('sales:settlement_approval_detail', order_number=order_number)

    document = get_object_or_404(
        TransactionDocument,
        id=document_id,
        settlement__order=order,
    )
    settlement = document.settlement

    settlement_type_label = settlement.get_settlement_type_display() if settlement.settlement_type else 'تراکنش'

    if request.method == 'POST':
        form = SettlementApprovalTransactionEditForm(
            request.POST,
            instance=document,
            settlement=settlement,
        )
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    new_total = TransactionDocument.objects.filter(
                        settlement=settlement
                    ).aggregate(total=Sum('document_amount'))['total'] or Decimal('0')
                    settlement.settled_amount = new_total
                    settlement.save(update_fields=['settled_amount'])
                messages.success(request, 'تراکنش با موفقیت ذخیره شد.')
                audit_logger.activity(
                    f"مدیر تراکنش {document_id} سفارش {order_number} را در صفحه تایید تسویه ویرایش کرد."
                )
                return redirect('sales:settlement_approval_detail', order_number=order_number)
            except Exception as e:
                bug_logger.error(f"خطا در ذخیره تراکنش: {e}", exc_info=True)
                messages.error(request, f'خطا در ذخیره: {str(e)}')
        else:
            for _field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, err)
    else:
        form = SettlementApprovalTransactionEditForm(
            instance=document,
            settlement=settlement,
        )

    context = {
        'form': form,
        'order': order,
        'document': document,
        'settlement': settlement,
        'page_title': f'ویرایش تراکنش - سفارش {order_number}',
        'settlement_type_label': settlement_type_label,
    }
    return render(request, 'settlement_approval/settlement_approval_edit_transaction.html', context)

