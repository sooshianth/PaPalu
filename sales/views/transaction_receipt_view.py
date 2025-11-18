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
from sales.forms.transaction_document_form import TransactionDocumentForm

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def transaction_receipt_order_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار بارگذاری رسید تراکنش»
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار بارگذاری رسید تراکنش")
    
    if not user_has_task(request.user, TaskChoices.SALES_TRANSACTION_RECEIPT.value):
        audit_logger.activity("تلاش برای مشاهده لیست رسیدهای تراکنش فروش بدون دسترسی")
        messages.error(request, 'شما دسترسی به مدیریت رسیدهای تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_transaction_receipt_upload').order_by('-created_at')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار بارگذاری رسید تراکنش لود شد")

    # برای هر سفارش اگر Settlement وجود نداشته باشد، به صورت lazy در ویو جزئیات ساخته می‌شود
    context = {
        'orders': orders_qs.select_related('registered_by'),
        'page_title': 'سفارش‌های در انتظار بارگذاری رسید تراکنش',
    }
    return render(request, 'sales/transaction_receipt_order_list.html', context)


@login_required
def transaction_receipt_upload_view(request, order_number):
    """
    ثبت و بارگذاری چندین سند تراکنش برای یک سفارش
    - بعد از اینکه مجموع مبالغ اسناد به مبلغ کل سند مبدا برسد،
      وضعیت سفارش به «در انتظار تایید تراکنش فروش» تغییر می‌کند.
    """
    audit_logger.info(f"درخواست ثبت رسید تراکنش برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_TRANSACTION_RECEIPT.value):
        audit_logger.activity(f"تلاش برای ثبت رسید تراکنش سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به ثبت رسیدهای تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_transaction_receipt_upload':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_transaction_receipt_upload می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای ثبت رسید تراکنش نیست.')
        return redirect('sales:transaction_receipt_order_list')

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

    # لیست اسناد تراکنش موجود
    documents = settlement.transaction_documents.all().select_related('source_account', 'destination_account')
    total_document_amount = documents.aggregate(total=Sum('document_amount'))['total'] or 0

    if request.method == 'POST':
        form = TransactionDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    doc: TransactionDocument = form.save(commit=False)
                    doc.settlement = settlement
                    # تولید خودکار شماره سند حسابداری
                    doc.generate_accounting_document_number()
                    doc.save()

                    # به‌روزرسانی مبالغ تسویه
                    documents_qs = settlement.transaction_documents.all()
                    total_document_amount = documents_qs.aggregate(total=Sum('document_amount'))['total'] or 0
                    settlement.settled_amount = total_document_amount

                    # اگر مبلغ کل سند مبدا تعریف شده و مجموع اسناد >= آن شد
                    if settlement.original_document_amount and total_document_amount >= settlement.original_document_amount:
                        settlement.settlement_status = 'completed'
                        order.status = 'pending_accounting_approval'
                        order.save(update_fields=['status'])
                    else:
                        settlement.settlement_status = 'partial'

                    settlement.save(update_fields=['settled_amount', 'settlement_status'])
                    
                    if order.status == 'pending_accounting_approval':
                        bug_logger.info(f"وضعیت سفارش {order_number} به pending_accounting_approval تغییر یافت")

                bug_logger.info(f"سند تراکنش جدید برای سفارش {order_number} ثبت شد")
                messages.success(request, 'سند تراکنش با موفقیت ثبت شد.')
                return redirect('sales:transaction_receipt_upload', order_number=order_number)
            except Exception as e:
                bug_logger.error(f"خطا در ثبت سند تراکنش سفارش {order_number}: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ثبت سند تراکنش: {str(e)}')
        else:
            bug_logger.warning(f"فرم ثبت سند تراکنش سفارش {order_number} معتبر نیست")
            messages.error(request, 'اطلاعات فرم معتبر نیست. لطفاً خطاها را بررسی کنید.')
    else:
        form = TransactionDocumentForm()

    # محاسبه باقیمانده
    remaining_amount = 0
    if settlement.original_document_amount:
        remaining_amount = float(settlement.original_document_amount) - float(settlement.settled_amount or 0)
    
    bug_logger.debug(f"نمایش صفحه ثبت رسید تراکنش سفارش {order_number}: {len(documents)} سند")
    
    context = {
        # داده دیدنی
        'order': order,
        'settlement': settlement,
        'documents': documents,
        'total_document_amount': total_document_amount,
        'remaining_amount': remaining_amount,
        # فرم برای داده‌های پرکردنی
        'form': form,
        'page_title': f'ثبت رسید تراکنش - سفارش {order.order_number}',
    }
    return render(request, 'sales/transaction_receipt_upload.html', context)


