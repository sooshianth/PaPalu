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
from sales.forms.transaction_receipt_approve_form import TransactionApprovalForm, TransactionRejectionForm
from sales.tables.tables_transaction_receipt import ApproveTransactionReceiptTable

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
def approve_transaction_receipt_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تأیید حسابداری»
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تأیید حسابداری")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity("تلاش برای دسترسی به لیست تأیید تراکنش فروش بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # گرفتن سفارش‌های در وضعیت pending_accounting_approval
    orders_qs = Order.objects.filter(status='pending_accounting_approval').order_by('-created_at')
    
    # همچنین سفارش‌هایی که در وضعیت pending_transaction_receipt_upload هستند اما مبلغ کل رسیده است
    from django.db.models import Q
    
    # گرفتن همه سفارش‌های در وضعیت pending_transaction_receipt_upload
    pending_upload_orders = Order.objects.filter(status='pending_transaction_receipt_upload')
    
    # فیلتر کردن سفارش‌هایی که مبلغ کل رسیده است
    # باید از مجموع همه تراکنش‌ها (چه تایید شده و چه نشده) استفاده کنیم
    orders_with_complete_amount = []
    for order in pending_upload_orders:
        try:
            settlement = Settlement.objects.get(order=order)
            if settlement.original_document_amount:
                # محاسبه مجموع همه تراکنش‌های موجود (چه تایید شده و چه نشده)
                all_documents_total = settlement.transaction_documents.aggregate(total=Sum('document_amount'))['total'] or 0
                # بررسی اینکه آیا همه تراکنش‌ها تایید شده‌اند یا نه
                all_approved = settlement.transaction_documents.exclude(approval_status='approved').count() == 0
                all_documents_exist = settlement.transaction_documents.count() > 0
                # فقط اگر مبلغ کامل رسیده و هنوز همه تایید نشده‌اند، نمایش بده
                if float(all_documents_total) >= float(settlement.original_document_amount) and not (all_approved and all_documents_exist):
                    orders_with_complete_amount.append(order.order_number)
        except Settlement.DoesNotExist:
            pass
    
    # اضافه کردن سفارش‌های با مبلغ کامل به query
    if orders_with_complete_amount:
        orders_qs = orders_qs | Order.objects.filter(order_number__in=orders_with_complete_amount)
    
    # حذف سفارش‌هایی که همه تراکنش‌هایشان تایید شده است
    orders_to_exclude = []
    for order in orders_qs:
        try:
            settlement = Settlement.objects.get(order=order)
            all_documents = settlement.transaction_documents.all()
            all_approved = all_documents.exclude(approval_status='approved').count() == 0
            all_documents_exist = all_documents.count() > 0
            # اگر همه تراکنش‌ها تایید شده‌اند، از لیست حذف کن
            if all_approved and all_documents_exist:
                orders_to_exclude.append(order.order_number)
        except Settlement.DoesNotExist:
            pass
    
    if orders_to_exclude:
        orders_qs = orders_qs.exclude(order_number__in=orders_to_exclude)
    
    orders_qs = orders_qs.distinct().order_by('-created_at')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    # بررسی اینکه آیا تراکنش رد شده وجود دارد و اضافه کردن به record
    for order in orders_qs:
        try:
            settlement = Settlement.objects.get(order=order)
            has_rejected = settlement.transaction_documents.filter(approval_status='rejected').exists()
            order._has_rejected = has_rejected
        except Settlement.DoesNotExist:
            order._has_rejected = False

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار تأیید حسابداری لود شد")

    # محاسبه فیلدهای قابل دسترسی (در حال حاضر همه فیلدها قابل دسترسی هستند)
    accessible_fields = {
        'order_number': True,
        'customer': True,
        'created_at': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    table = ApproveTransactionReceiptTable(orders_qs.select_related('registered_by', 'customer'), user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)

    context = {
        'table': table,
        'accessible_fields': accessible_fields,
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

    # بررسی اینکه آیا سفارش در وضعیت مناسب است یا مبلغ کل رسیده است
    is_pending_accounting = order.status == 'pending_accounting_approval'
    is_pending_upload_with_complete_amount = False
    
    if order.status == 'pending_transaction_receipt_upload':
        try:
            settlement = Settlement.objects.get(order=order)
            if settlement.original_document_amount:
                # محاسبه مجموع همه تراکنش‌های موجود (چه تایید شده و چه نشده)
                all_documents_total = settlement.transaction_documents.aggregate(total=Sum('document_amount'))['total'] or 0
                if float(all_documents_total) >= float(settlement.original_document_amount):
                    is_pending_upload_with_complete_amount = True
        except Settlement.DoesNotExist:
            pass
    
    if not is_pending_accounting and not is_pending_upload_with_complete_amount:
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است و مبلغ کل نرسیده است")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تأیید حسابداری نیست یا مبلغ کل نرسیده است.')
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
    
    # بررسی اینکه آیا تراکنش رد شده وجود دارد
    has_rejected_documents = documents.filter(approval_status='rejected').exists()
    
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
        # بررسی اینکه آیا درخواست رد است یا تایید
        action = request.POST.get('action', 'approve')
        
        # اگر document_id در POST هم باشد، از آن استفاده کن
        if not document and 'document_id' in request.POST:
            try:
                document = documents.get(id=request.POST['document_id'])
            except (TransactionDocument.DoesNotExist, ValueError):
                bug_logger.warning(f"سند تراکنش {request.POST.get('document_id')} برای سفارش {order_number} یافت نشد")
                messages.error(request, 'سند تراکنش یافت نشد.')
                return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
        
        if not document:
            bug_logger.warning(f"درخواست POST تأیید/رد تراکنش بدون document_id برای سفارش {order_number}")
            messages.error(request, 'لطفاً یک سند تراکنش را انتخاب کنید.')
            return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
        
        # اگر درخواست رد است
        if action == 'reject':
            rejection_form = TransactionRejectionForm(request.POST)
            if rejection_form.is_valid():
                try:
                    with transaction.atomic():
                        document.approval_status = 'rejected'
                        document.rejection_reason = rejection_form.cleaned_data['rejection_reason']
                        document.save(update_fields=['approval_status', 'rejection_reason'])
                        
                        bug_logger.info(f"تراکنش سند {document.id} برای سفارش {order_number} رد شد")
                        messages.success(request, 'تراکنش با موفقیت رد شد.')
                        
                        return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
                except Exception as e:
                    bug_logger.error(f"خطا در رد تراکنش سفارش {order_number}: {str(e)}", exc_info=True)
                    messages.error(request, f'خطا در رد تراکنش: {str(e)}')
            else:
                bug_logger.warning(f"فرم رد تراکنش سفارش {order_number} معتبر نیست")
                messages.error(request, 'اطلاعات فرم معتبر نیست. لطفاً خطاها را بررسی کنید.')
        else:
            # درخواست تایید
            form = TransactionApprovalForm(request.POST, settlement=settlement, document=document)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # ثبت تأیید (override فیلدهای سند)
                        doc = form.save()
                        # اطمینان از اینکه approval_status = 'approved' است
                        doc.approval_status = 'approved'
                        doc.rejection_reason = None
                        doc.save(update_fields=['approval_status', 'rejection_reason'])
                        
                        bug_logger.info(f"تأیید تراکنش سند {document.id} برای سفارش {order_number} ثبت شد")
                        messages.success(request, 'تأیید تراکنش با موفقیت ثبت شد.')
                        
                        # Refresh settlement از دیتابیس
                        settlement.refresh_from_db()
                        
                        # محاسبه مجدد مجموع مبالغ استعلام
                        approved_documents_qs = settlement.transaction_documents.filter(inquiry_amount__isnull=False)
                        total_inquiry_amount = approved_documents_qs.aggregate(total=Sum('inquiry_amount'))['total'] or 0
                        
                        # بررسی اینکه آیا همه تراکنش‌ها تایید شده‌اند
                        all_documents = settlement.transaction_documents.all()
                        all_approved = all_documents.exclude(approval_status='approved').count() == 0
                        all_documents_exist = all_documents.count() > 0
                        
                        # اگر همه تراکنش‌ها تایید شدند، وضعیت سفارش را تغییر بده
                        if all_approved and all_documents_exist:
                            # Refresh order از دیتابیس
                            order.refresh_from_db()
                            # بررسی مجدد وضعیت قبل از تغییر
                            if order.status in ['pending_accounting_approval', 'pending_transaction_receipt_upload']:
                                order.status = 'pending_allocation'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"وضعیت سفارش {order_number} به pending_allocation تغییر یافت - همه تراکنش‌ها تایید شدند")
                                messages.success(request, 'همه تراکنش‌ها تایید شدند. سفارش به مرحله "در انتظار تخصیص" منتقل شد.')
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
            # توجه: inquiry_amount نباید پیش‌پر شود - کاربر باید آن را دستی وارد کند برای بررسی تطابق
            initial_data = {}
            if document.accounting_document_number:
                initial_data['accounting_document_number'] = document.accounting_document_number
            if document.tracking_number:
                initial_data['tracking_number'] = document.tracking_number
            # inquiry_name در فرم به صورت ChoiceField است و خود فرم مقدار پیش‌فرض را تنظیم می‌کند
            # اما اگر نام دیگری است، باید آن را به initial_data اضافه کنیم
            if document.inquiry_name:
                # بررسی می‌کنیم که آیا نام مشتری است یا نه
                customer_name = None
                if settlement.order and settlement.order.customer:
                    customer_name = settlement.order.customer.name or 'مشتری'
                
                if document.inquiry_name != customer_name:
                    # اگر نام مشتری نیست، باید "سایر" را انتخاب کنیم و نام را در inquiry_name_other بگذاریم
                    initial_data['inquiry_name'] = 'other'
                    initial_data['inquiry_name_other'] = document.inquiry_name
                else:
                    initial_data['inquiry_name'] = document.inquiry_name
            if document.transfer_time:
                initial_data['transfer_time'] = document.transfer_time
            
            # اگر حساب بانکی موجود است، آن را به initial_data اضافه کن
            if document.source_account:
                try:
                    from core.PersonFolder import BankAccount
                    bank_account = BankAccount.objects.filter(
                        account_number=document.source_account.account_number
                    ).first()
                    if bank_account:
                        initial_data['bank_account'] = bank_account.id
                except:
                    pass
            
            form = TransactionApprovalForm(settlement=settlement, document=document, instance=document, initial=initial_data)
            rejection_form = TransactionRejectionForm()
        else:
            # فرم خالی برای انتخاب سند
            form = None
            rejection_form = None

    # محاسبه باقیمانده
    remaining_amount = 0
    if settlement.original_document_amount:
        remaining_amount = float(settlement.original_document_amount) - float(total_inquiry_amount)

    bug_logger.debug(f"نمایش صفحه جزئیات تأیید تراکنش سفارش {order_number}: {len(documents)} سند، {len(approved_documents)} تأیید شده")

    # اطمینان از وجود rejection_form در context
    if 'rejection_form' not in locals():
        if form and document:
            rejection_form = TransactionRejectionForm()
        else:
            rejection_form = None

    # فارسی کردن اعداد برای نمایش در template
    order_number_persian = to_persian_digits(order.order_number)
    original_document_amount_persian = persian_number_with_comma(settlement.original_document_amount) if settlement.original_document_amount else '-'
    settled_amount_persian = persian_number_with_comma(settlement.settled_amount) if settlement.settled_amount else '۰'
    total_inquiry_amount_persian = persian_number_with_comma(total_inquiry_amount) if total_inquiry_amount else '۰'
    remaining_amount_persian = persian_number_with_comma(remaining_amount) if settlement.original_document_amount else '۰'
    
    # فارسی کردن اعداد برای هر سند
    documents_with_persian = []
    for doc in documents:
        doc_dict = {
            'doc': doc,
            'document_amount_persian': persian_number_with_comma(doc.document_amount) if doc.document_amount else '-',
        }
        documents_with_persian.append(doc_dict)
    
    # فارسی کردن اعداد برای اسناد تأیید شده
    approved_documents_with_persian = []
    for doc in approved_documents:
        doc_dict = {
            'doc': doc,
            'inquiry_amount_persian': persian_number_with_comma(doc.inquiry_amount) if doc.inquiry_amount else '-',
            'tracking_number_persian': to_persian_digits(doc.tracking_number) if doc.tracking_number else '-',
            'approval_account_number_persian': to_persian_digits(doc.approval_account_number) if doc.approval_account_number else '-',
            'shaba_number_persian': to_persian_digits(doc.shaba_number) if doc.shaba_number else '-',
        }
        approved_documents_with_persian.append(doc_dict)
    
    # فارسی کردن اعداد برای سند انتخابی
    selected_document_persian = None
    if document:
        selected_document_persian = {
            'document_amount_persian': persian_number_with_comma(document.document_amount) if document.document_amount else '-',
        }

    context = {
        'order': order,
        'settlement': settlement,
        'documents': documents,
        'documents_with_persian': documents_with_persian,
        'approved_documents': approved_documents,
        'approved_documents_with_persian': approved_documents_with_persian,
        'total_inquiry_amount': total_inquiry_amount,
        'remaining_amount': remaining_amount,
        'can_approve': can_approve,
        'has_rejected_documents': has_rejected_documents,
        'form': form,
        'rejection_form': rejection_form if 'rejection_form' in locals() else None,
        'selected_document': document,
        'selected_document_persian': selected_document_persian,
        # اعداد فارسی شده
        'order_number_persian': order_number_persian,
        'original_document_amount_persian': original_document_amount_persian,
        'settled_amount_persian': settled_amount_persian,
        'total_inquiry_amount_persian': total_inquiry_amount_persian,
        'remaining_amount_persian': remaining_amount_persian,
        'page_title': f'تأیید تراکنش - سفارش {order.order_number}',
    }
    return render(request, 'transaction/approve_transaction_receipt_detail.html', context)

