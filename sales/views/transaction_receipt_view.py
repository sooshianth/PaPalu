from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.SettlementFolder.SettlementModel import Settlement
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from sales.forms.transaction_document_form import TransactionDocumentForm
from sales.tables.tables_transaction_receipt import TransactionReceiptOrderTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def to_persian_digits(text):
    """تبدیل اعداد انگلیسی به فارسی بدون کاما"""
    if text is None:
        return ''
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


def persian_number_with_comma(value):
    """فرمت کردن عدد با کاما و تبدیل به فارسی (برای مبالغ)"""
    if value is None:
        return '-'
    try:
        num_float = float(value)
        formatted = f"{num_float:,.0f}"
        return to_persian_digits(formatted)
    except (ValueError, TypeError):
        return str(value)


@login_required
def transaction_receipt_order_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار بارگذاری رسید تراکنش»
    با استفاده از django-tables2
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

    # محاسبه فیلدهای قابل دسترسی (در حال حاضر همه فیلدها قابل دسترسی هستند)
    accessible_fields = {
        'order_number': True,
        'order_type': True,
        'status': True,
        'registered_by': True,
        'original_document_amount': True,
        'remaining_amount': True,
        'customer_name': True,
        'customer_national_id': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    # استفاده از select_related و prefetch_related برای بهینه‌سازی query
    table = TransactionReceiptOrderTable(
        orders_qs.select_related('registered_by', 'customer').prefetch_related('settlements', 'settlements__transaction_documents'),
        user=request.user,
        accessible_fields=accessible_fields
    )
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'سفارش‌های در انتظار بارگذاری رسید تراکنش',
    }
    return render(request, 'transaction/transaction_receipt_order_list.html', context)


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
        form = TransactionDocumentForm(request.POST, request.FILES, customer=order.customer)
        if form.is_valid():
            # محاسبه باقیمانده قبل از ذخیره
            new_document_amount = form.cleaned_data.get('document_amount', 0)
            if settlement.original_document_amount:
                # محاسبه مجموع همه تراکنش‌های موجود (چه تایید شده و چه نشده)
                # باید دوباره query کنیم چون ممکن است در همین request تغییر کرده باشد
                all_documents = settlement.transaction_documents.all()
                all_documents_amount = all_documents.aggregate(total=Sum('document_amount'))['total'] or 0
                remaining_amount = float(settlement.original_document_amount) - float(all_documents_amount)
                
                # چک کردن اینکه مبلغ جدید از باقیمانده بیشتر نباشد
                if float(new_document_amount) > remaining_amount:
                    form.add_error(
                        'document_amount',
                        f'مبلغ تراکنش ({new_document_amount:,.0f}) نمی‌تواند از مبلغ باقیمانده ({remaining_amount:,.0f}) بیشتر باشد.'
                    )
                    bug_logger.warning(
                        f"تلاش برای ثبت تراکنش با مبلغ {new_document_amount} که از باقیمانده {remaining_amount} بیشتر است برای سفارش {order_number}"
                    )
                else:
                    try:
                        with transaction.atomic():
                            doc: TransactionDocument = form.save(commit=False)
                            doc.settlement = settlement
                            # تولید خودکار شماره سند حسابداری
                            doc.generate_accounting_document_number()
                            doc.save()

                            # به‌روزرسانی مبالغ تسویه
                            documents_qs = settlement.transaction_documents.all()
                            # فقط تراکنش‌هایی که approval_status='approved' دارند را برای settled_amount در نظر می‌گیریم
                            approved_documents_qs = documents_qs.filter(approval_status='approved')
                            total_document_amount = approved_documents_qs.aggregate(total=Sum('document_amount'))['total'] or 0
                            settlement.settled_amount = total_document_amount

                            # بررسی اینکه آیا همه تراکنش‌ها تایید شده‌اند
                            all_approved = documents_qs.exclude(approval_status='approved').count() == 0
                            all_documents_exist = documents_qs.count() > 0

                            # اگر مبلغ کل سند مبدا تعریف شده و مجموع اسناد >= آن شد
                            if settlement.original_document_amount and total_document_amount >= settlement.original_document_amount:
                                if all_approved and all_documents_exist:
                                    # همه تراکنش‌ها تایید شده‌اند و مبلغ برابر است
                                    settlement.settlement_status = 'completed'
                                    # فقط اگر سفارش هنوز در وضعیت pending_transaction_receipt_upload است، وضعیت را تغییر بده
                                    if order.status == 'pending_transaction_receipt_upload':
                                        order.status = 'pending_accounting_approval'
                                        order.save(update_fields=['status'])
                                        bug_logger.info(f"وضعیت سفارش {order_number} به pending_accounting_approval تغییر یافت")
                                else:
                                    # مبلغ برابر است اما هنوز همه تراکنش‌ها تایید نشده‌اند
                                    settlement.settlement_status = 'partial'
                            else:
                                settlement.settlement_status = 'partial'

                            settlement.save(update_fields=['settled_amount', 'settlement_status'])

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
        form = TransactionDocumentForm(customer=order.customer)

    # محاسبه باقیمانده - باید از مجموع همه تراکنش‌ها (چه تایید شده و چه نشده) محاسبه شود
    remaining_amount = 0
    if settlement.original_document_amount:
        # محاسبه مجموع همه تراکنش‌های موجود (چه تایید شده و چه نشده)
        all_documents_total = documents.aggregate(total=Sum('document_amount'))['total'] or 0
        remaining_amount = float(settlement.original_document_amount) - float(all_documents_total)
    
    bug_logger.debug(f"نمایش صفحه ثبت رسید تراکنش سفارش {order_number}: {len(documents)} سند")
    
    # بررسی اینکه آیا همه تراکنش‌ها تایید شده‌اند
    all_approved = documents.exclude(approval_status='approved').count() == 0
    all_documents_exist = documents.count() > 0
    # برای can_proceed باید از settled_amount استفاده کنیم (فقط تراکنش‌های تایید شده)
    approved_documents_total = documents.filter(approval_status='approved').aggregate(total=Sum('document_amount'))['total'] or 0
    can_proceed = False
    if settlement.original_document_amount and approved_documents_total >= settlement.original_document_amount:
        if all_approved and all_documents_exist:
            can_proceed = True
    
    # فارسی کردن اعداد برای نمایش در template
    order_number_persian = to_persian_digits(order.order_number)
    original_document_amount_persian = persian_number_with_comma(settlement.original_document_amount) if settlement.original_document_amount else '-'
    settled_amount_persian = persian_number_with_comma(settlement.settled_amount) if settlement.settled_amount else '۰'
    remaining_amount_persian = persian_number_with_comma(remaining_amount) if settlement.original_document_amount else '-'
    total_document_amount_persian = persian_number_with_comma(total_document_amount) if total_document_amount else '۰'
    
    # فارسی کردن اعداد برای هر سند
    documents_with_persian = []
    for doc in documents:
        doc_dict = {
            'doc': doc,
            'document_amount_persian': persian_number_with_comma(doc.document_amount) if doc.document_amount else '-',
        }
        documents_with_persian.append(doc_dict)
    
    context = {
        # داده دیدنی
        'order': order,
        'settlement': settlement,
        'documents': documents,
        'documents_with_persian': documents_with_persian,
        'total_document_amount': total_document_amount,
        'remaining_amount': remaining_amount,
        'all_approved': all_approved,
        'can_proceed': can_proceed,
        # اعداد فارسی شده
        'order_number_persian': order_number_persian,
        'original_document_amount_persian': original_document_amount_persian,
        'settled_amount_persian': settled_amount_persian,
        'remaining_amount_persian': remaining_amount_persian,
        'total_document_amount_persian': total_document_amount_persian,
        # فرم برای داده‌های پرکردنی
        'form': form,
        'page_title': f'ثبت رسید تراکنش - سفارش {order.order_number}',
    }
    return render(request, 'transaction/transaction_receipt_upload.html', context)


@login_required
def transaction_receipt_edit_view(request, order_number, document_id):
    """
    ویرایش یک سند تراکنش (فقط اگر تایید نشده باشد)
    """
    audit_logger.info(f"درخواست ویرایش سند تراکنش {document_id} برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_TRANSACTION_RECEIPT.value):
        audit_logger.activity(f"تلاش برای ویرایش سند تراکنش {document_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به ویرایش رسیدهای تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)
    document = get_object_or_404(TransactionDocument, id=document_id, settlement__order=order)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # بررسی اینکه آیا تراکنش تایید شده است یا نه
    if document.approval_status == 'approved':
        messages.error(request, 'تراکنش تایید شده را نمی‌توان ویرایش کرد.')
        return redirect('sales:transaction_receipt_upload', order_number=order_number)

    if request.method == 'POST':
        form = TransactionDocumentForm(request.POST, request.FILES, instance=document, customer=order.customer)
        if form.is_valid():
            # محاسبه باقیمانده قبل از ذخیره
            new_document_amount = form.cleaned_data.get('document_amount', 0)
            old_document_amount = document.document_amount or 0
            settlement = document.settlement
            
            if settlement.original_document_amount:
                # محاسبه مجموع همه تراکنش‌های موجود (چه تایید شده و چه نشده)
                # باید مبلغ قبلی را کم کنیم و مبلغ جدید را اضافه کنیم
                all_documents_amount = settlement.transaction_documents.aggregate(total=Sum('document_amount'))['total'] or 0
                # کم کردن مبلغ قبلی و اضافه کردن مبلغ جدید
                remaining_amount = float(settlement.original_document_amount) - float(all_documents_amount) + float(old_document_amount)
                
                # چک کردن اینکه مبلغ جدید از باقیمانده بیشتر نباشد
                if float(new_document_amount) > remaining_amount:
                    form.add_error(
                        'document_amount',
                        f'مبلغ تراکنش ({new_document_amount:,.0f}) نمی‌تواند از مبلغ باقیمانده ({remaining_amount:,.0f}) بیشتر باشد.'
                    )
                    bug_logger.warning(
                        f"تلاش برای ویرایش تراکنش با مبلغ {new_document_amount} که از باقیمانده {remaining_amount} بیشتر است برای سفارش {order_number}"
                    )
                else:
                    try:
                        with transaction.atomic():
                            doc: TransactionDocument = form.save(commit=False)
                            # اگر شماره سند حسابداری وجود نداشته باشد، تولید کن
                            if not doc.accounting_document_number:
                                doc.generate_accounting_document_number()
                            # اگر تراکنش رد شده بود، بعد از ویرایش به حالت در انتظار برگردان
                            if doc.approval_status == 'rejected':
                                doc.approval_status = 'pending'
                                doc.rejection_reason = None
                            doc.save()

                            # به‌روزرسانی مبالغ تسویه
                            documents_qs = settlement.transaction_documents.all()
                            # فقط تراکنش‌هایی که approval_status='approved' دارند را برای settled_amount در نظر می‌گیریم
                            approved_documents_qs = documents_qs.filter(approval_status='approved')
                            total_document_amount = approved_documents_qs.aggregate(total=Sum('document_amount'))['total'] or 0
                            settlement.settled_amount = total_document_amount

                            # بررسی اینکه آیا همه تراکنش‌ها تایید شده‌اند
                            all_approved = documents_qs.exclude(approval_status='approved').count() == 0
                            all_documents_exist = documents_qs.count() > 0

                            # اگر مبلغ کل سند مبدا تعریف شده و مجموع اسناد >= آن شد
                            if settlement.original_document_amount and total_document_amount >= settlement.original_document_amount:
                                if all_approved and all_documents_exist:
                                    settlement.settlement_status = 'completed'
                                    # فقط اگر سفارش هنوز در وضعیت pending_transaction_receipt_upload است، وضعیت را تغییر بده
                                    if order.status == 'pending_transaction_receipt_upload':
                                        order.status = 'pending_accounting_approval'
                                        order.save(update_fields=['status'])
                                        bug_logger.info(f"وضعیت سفارش {order_number} به pending_accounting_approval تغییر یافت")
                                else:
                                    settlement.settlement_status = 'partial'
                            else:
                                settlement.settlement_status = 'partial'

                            settlement.save(update_fields=['settled_amount', 'settlement_status'])

                        bug_logger.info(f"سند تراکنش {document_id} برای سفارش {order_number} ویرایش شد")
                        messages.success(request, 'سند تراکنش با موفقیت ویرایش شد.')
                        return redirect('sales:transaction_receipt_upload', order_number=order_number)
                    except Exception as e:
                        bug_logger.error(f"خطا در ویرایش سند تراکنش {document_id} سفارش {order_number}: {str(e)}", exc_info=True)
                        messages.error(request, f'خطا در ویرایش سند تراکنش: {str(e)}')
        else:
            bug_logger.warning(f"فرم ویرایش سند تراکنش {document_id} سفارش {order_number} معتبر نیست")
            messages.error(request, 'اطلاعات فرم معتبر نیست. لطفاً خطاها را بررسی کنید.')
    else:
        form = TransactionDocumentForm(instance=document, customer=order.customer)

    context = {
        'order': order,
        'document': document,
        'form': form,
        'page_title': f'ویرایش سند تراکنش - سفارش {order.order_number}',
    }
    return render(request, 'transaction/transaction_receipt_edit.html', context)


@login_required
def transaction_receipt_approve_reject_view(request, order_number, document_id, action):
    """
    تایید یا رد یک تراکنش
    action می‌تواند 'approve' یا 'reject' باشد
    """
    audit_logger.info(f"درخواست {action} سند تراکنش {document_id} برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_TRANSACTION_RECEIPT.value):
        audit_logger.activity(f"تلاش برای {action} سند تراکنش {document_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید/رد رسیدهای تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)
    document = get_object_or_404(TransactionDocument, id=document_id, settlement__order=order)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if action not in ['approve', 'reject']:
        messages.error(request, 'عملیات نامعتبر است.')
        return redirect('sales:transaction_receipt_upload', order_number=order_number)

    try:
        with transaction.atomic():
            if action == 'approve':
                document.approval_status = 'approved'
                bug_logger.info(f"سند تراکنش {document_id} برای سفارش {order_number} تایید شد")
                messages.success(request, 'تراکنش با موفقیت تایید شد.')
            else:  # reject
                document.approval_status = 'rejected'
                bug_logger.info(f"سند تراکنش {document_id} برای سفارش {order_number} رد شد")
                messages.success(request, 'تراکنش رد شد.')
            
            document.save(update_fields=['approval_status'])

            # بررسی اینکه آیا همه تراکنش‌ها تایید شده‌اند
            settlement = document.settlement
            documents_qs = settlement.transaction_documents.all()
            total_document_amount = documents_qs.aggregate(total=Sum('document_amount'))['total'] or 0
            
            all_approved = documents_qs.exclude(approval_status='approved').count() == 0
            all_documents_exist = documents_qs.count() > 0

            # اگر مبلغ کل سند مبدا تعریف شده و مجموع اسناد >= آن شد
            if settlement.original_document_amount and total_document_amount >= settlement.original_document_amount:
                if all_approved and all_documents_exist:
                    # همه تراکنش‌ها تایید شده‌اند و مبلغ برابر است
                    settlement.settlement_status = 'completed'
                    # فقط اگر سفارش هنوز در وضعیت pending_transaction_receipt_upload است، وضعیت را تغییر بده
                    if order.status == 'pending_transaction_receipt_upload':
                        order.status = 'pending_accounting_approval'
                        order.save(update_fields=['status'])
                        bug_logger.info(f"وضعیت سفارش {order_number} به pending_accounting_approval تغییر یافت")
                        messages.success(request, 'همه تراکنش‌ها تایید شدند. سفارش به مرحله "در انتظار تایید حسابداری" منتقل شد.')
                else:
                    settlement.settlement_status = 'partial'
            else:
                settlement.settlement_status = 'partial'

            settlement.save(update_fields=['settlement_status'])

    except Exception as e:
        bug_logger.error(f"خطا در {action} سند تراکنش {document_id} سفارش {order_number}: {str(e)}", exc_info=True)
        messages.error(request, f'خطا در {action} تراکنش: {str(e)}')

    return redirect('sales:transaction_receipt_upload', order_number=order_number)


