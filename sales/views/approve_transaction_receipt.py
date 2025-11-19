from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.SettlementFolder.SettlementModel import Settlement
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from sales.forms.approve_transaction_receipt import TransactionApprovalForm

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def approve_transaction_receipt_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تأیید حسابداری»
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تأیید حسابداری")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity("تلاش برای دسترسی به لیست تأیید تراکنش فروش بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_accounting_approval').order_by('-created_at')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار تأیید حسابداری لود شد")

    context = {
        'orders': orders_qs.select_related('registered_by', 'customer'),
        'page_title': 'سفارش‌های در انتظار تأیید حسابداری',
    }
    return render(request, 'transaction/approve_transaction_receipt_list.html', context)


@login_required
def approve_transaction_receipt_detail_view(request, order_number):
    """
    صفحه جزئیات تأیید تراکنش برای یک سفارش
    - نمایش همه اسناد تراکنش آپلود شده
    - نمایش لیست تأییدهای ثبت شده
    - فرم ثبت تأیید جدید
    - بعد از اینکه مجموع مبالغ استعلام = مبلغ کل، سفارش به "در انتظار تخصیص" می‌رود
    """
    audit_logger.info(f"درخواست مشاهده جزئیات تأیید تراکنش سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity(f"تلاش برای دسترسی به جزئیات تأیید تراکنش سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_accounting_approval':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_accounting_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تأیید حسابداری نیست.')
        return redirect('sales:approve_transaction_receipt_list')

    # محاسبه مبلغ کل سفارش از اقلام
    order_total_amount = order.get_total_amount()
    
    # گرفتن یا ساختن Settlement مرتبط با این سفارش
    settlement, created = Settlement.objects.get_or_create(
        order=order,
        defaults={
            'settlement_type': 'sale',
            'settlement_status': 'pending',
            'original_document_amount': order_total_amount,
            'debtor_person': order.customer,  # برای فروش، مشتری بدهکار است
            'creditor_person': None,  # می‌تواند از تنظیمات شرکت گرفته شود
        },
    )
    
    # اگر settlement از قبل وجود داشت، مبلغ اصلی را به‌روزرسانی کن
    if not created and settlement.original_document_amount != order_total_amount:
        settlement.original_document_amount = order_total_amount
        settlement.save(update_fields=['original_document_amount'])
    
    # لیست اسناد تراکنش
    documents = settlement.transaction_documents.all().select_related('source_account', 'destination_account').order_by('-id')
    
    # محاسبه مجموع مبالغ استعلام از اسناد تأیید شده
    approved_documents = documents.filter(inquiry_amount__isnull=False)
    total_inquiry_amount = approved_documents.aggregate(total=Sum('inquiry_amount'))['total'] or 0
    
    # بررسی اینکه آیا مجموع مبالغ استعلام با مبلغ کل تسویه برابر است
    can_approve = False
    if settlement.original_document_amount and total_inquiry_amount >= settlement.original_document_amount:
        can_approve = True

    # دریافت document_id از query string (اگر برای تأیید یک سند خاص باشد)
    document_id = request.GET.get('document_id')
    document = None
    if document_id:
        try:
            document = documents.get(id=document_id)
        except TransactionDocument.DoesNotExist:
            bug_logger.warning(f"سند تراکنش {document_id} برای سفارش {order_number} یافت نشد")
            messages.error(request, 'سند تراکنش یافت نشد.')
            return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)

    if request.method == 'POST':
        # اگر document_id در POST هم باشد، از آن استفاده کن
        if not document and 'document_id' in request.POST:
            try:
                document = documents.get(id=request.POST['document_id'])
            except (TransactionDocument.DoesNotExist, ValueError):
                bug_logger.warning(f"سند تراکنش {request.POST.get('document_id')} برای سفارش {order_number} یافت نشد")
                messages.error(request, 'سند تراکنش یافت نشد.')
                return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
        
        if not document:
            bug_logger.warning(f"درخواست POST تأیید تراکنش بدون document_id برای سفارش {order_number}")
            messages.error(request, 'لطفاً یک سند تراکنش را برای تأیید انتخاب کنید.')
            return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
        
        form = TransactionApprovalForm(request.POST, settlement=settlement, document=document)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ثبت تأیید (override فیلدهای سند)
                    form.save()
                    bug_logger.info(f"تأیید تراکنش سند {document.id} برای سفارش {order_number} ثبت شد")
                    messages.success(request, 'تأیید تراکنش با موفقیت ثبت شد.')
                    
                    # Refresh settlement از دیتابیس
                    settlement.refresh_from_db()
                    
                    # محاسبه مجدد مجموع مبالغ استعلام
                    approved_documents_qs = settlement.transaction_documents.filter(inquiry_amount__isnull=False)
                    total_inquiry_amount = approved_documents_qs.aggregate(total=Sum('inquiry_amount'))['total'] or 0
                    
                    # اگر مجموع مبالغ استعلام >= مبلغ کل تسویه شد، وضعیت سفارش را تغییر بده
                    if settlement.original_document_amount:
                        # تبدیل به float برای مقایسه دقیق
                        total_inquiry_float = float(total_inquiry_amount) if total_inquiry_amount else 0
                        original_amount_float = float(settlement.original_document_amount)
                        
                        # Debug: نمایش مقادیر
                        bug_logger.debug(f"مقایسه مبالغ برای سفارش {order_number}: total_inquiry={total_inquiry_float}, original_amount={original_amount_float}")
                        
                        if total_inquiry_float >= original_amount_float:
                            # Refresh order از دیتابیس
                            order.refresh_from_db()
                            # بررسی مجدد وضعیت قبل از تغییر
                            if order.status == 'pending_accounting_approval':
                                order.status = 'pending_allocation'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"وضعیت سفارش {order_number} به pending_allocation تغییر یافت")
                                messages.success(request, 'مجموع مبالغ استعلام با مبلغ کل تسویه برابر شد. سفارش به مرحله "در انتظار تخصیص" منتقل شد.')
                                # Redirect به لیست چون وضعیت تغییر کرده
                                return redirect('sales:approve_transaction_receipt_list')

                return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
            except Exception as e:
                bug_logger.error(f"خطا در ثبت تأیید تراکنش سفارش {order_number}: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ثبت تأیید تراکنش: {str(e)}')
        else:
            bug_logger.warning(f"فرم تأیید تراکنش سفارش {order_number} معتبر نیست")
            messages.error(request, 'اطلاعات فرم معتبر نیست. لطفاً خطاها را بررسی کنید.')
    else:
        # اگر document_id در query string باشد، فرم را با آن سند پر کن
        if document:
            # اگر سند قبلاً تأیید شده، مقادیر موجود را نمایش بده
            initial_data = {}
            if document.accounting_document_number:
                initial_data['accounting_document_number'] = document.accounting_document_number
            if document.inquiry_amount:
                initial_data['inquiry_amount'] = document.inquiry_amount
            if document.tracking_number:
                initial_data['tracking_number'] = document.tracking_number
            if document.source_bank:
                initial_data['source_bank'] = document.source_bank
            if document.approval_account_number:
                initial_data['approval_account_number'] = document.approval_account_number
            if document.shaba_number:
                initial_data['shaba_number'] = document.shaba_number
            if document.inquiry_name:
                initial_data['inquiry_name'] = document.inquiry_name
            if document.transfer_time:
                initial_data['transfer_time'] = document.transfer_time
            
            form = TransactionApprovalForm(settlement=settlement, document=document, instance=document, initial=initial_data)
        else:
            # فرم خالی برای انتخاب سند
            form = None

    # محاسبه باقیمانده
    remaining_amount = 0
    if settlement.original_document_amount:
        remaining_amount = float(settlement.original_document_amount) - float(total_inquiry_amount)

    bug_logger.debug(f"نمایش صفحه جزئیات تأیید تراکنش سفارش {order_number}: {len(documents)} سند، {len(approved_documents)} تأیید شده")

    context = {
        'order': order,
        'settlement': settlement,
        'documents': documents,
        'approved_documents': approved_documents,
        'total_inquiry_amount': total_inquiry_amount,
        'remaining_amount': remaining_amount,
        'can_approve': can_approve,
        'form': form,
        'selected_document': document,
        'page_title': f'تأیید تراکنش - سفارش {order.order_number}',
    }
    return render(request, 'transaction/approve_transaction_receipt_detail.html', context)

