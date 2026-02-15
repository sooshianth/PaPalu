from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django_tables2 import RequestConfig
from django.utils import timezone
from django.db.models import Q
import logging

from core.logging_levels import *
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.FreightPaymentDocumentAttachmentModel import FreightPaymentDocumentAttachment
from core.OrderFolder.OrderModel import Order
from core.RBACModel.TaskPermission import TaskChoices
from core.RBACModel.Roles import user_has_task
from accounting.tables import UploadFarePaymentDocsTable
from accounting.forms import UploadFarePaymentDocForm
from sms_api.apis import queue_sms

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def to_persian_digits(value):
    """تبدیل اعداد انگلیسی به فارسی"""
    if value is None:
        return ""
    return str(value).replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")


def format_currency_persian(value):
    """فرمت کردن عدد به صورت پول با کاما و تبدیل به فارسی"""
    if value is None:
        return "۰"
    try:
        # حذف اعشار و فرمت با کاما
        num = int(value)
        formatted = f"{num:,}"
        # تبدیل به فارسی
        return to_persian_digits(formatted)
    except (ValueError, TypeError):
        return to_persian_digits(str(value))


@login_required
def upload_fare_payment_docs_list_view(request):
    """صفحه لیست حمل‌های در انتظار بارگذاری اسناد پرداخت"""
    audit_logger.info("دسترسی به لیست بارگذاری اسناد پرداخت کرایه")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_UPLOAD_FREIGHT_PAYMENT_DOCS.value):
        audit_logger.activity("تلاش برای دسترسی به لیست بارگذاری اسناد پرداخت بدون مجوز")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        # Get transports that need payment document upload
        # Include: awaiting_wh_reconciliation (آماده خروج), pending_settlement (در انتظار تایید لجستیک), awaiting_payment_doc (در انتظار بارگذاری اسناد)
        # Only those that don't have payment documents uploaded yet
        # Exclude transports with freight_payment_type = 'calculated_in_invoice' (کرایه محاسبه شده در فی)
        transports = Transport.objects.filter(
            status__in=[
                Transport.STATUS_AWAITING_WH_RECONCILIATION,
                Transport.STATUS_AWAITING_SETTLEMENT,
                Transport.STATUS_AWAITING_PAYMENT_DOC
            ]
        ).exclude(
            freight_payment_type='calculated_in_invoice'  # حمل‌هایی که کرایه در فی محاسبه شده، نیاز به بارگذاری سند ندارند
        ).filter(
            Q(freight_payment_document__isnull=True) | Q(freight_payment_document='')  # NULL or empty string
        ).select_related(
            'allocation__order',
            'allocation__order__customer',
            'driver'
        ).prefetch_related(
            'allocation__order__order_items__raw_material'
        ).order_by('-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های در انتظار بارگذاری اسناد: {transports.count()}")
        
        # Create table
        table = UploadFarePaymentDocsTable(transports)
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
        }
        
        return render(request, 'accounting_upload_fare_payment_docs_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در نمایش لیست بارگذاری اسناد پرداخت: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها')
        return redirect('home')


@login_required
def upload_fare_payment_docs_detail_view(request, transport_number):
    """صفحه جزئیات و بارگذاری اسناد پرداخت"""
    audit_logger.info(f"دسترسی به بارگذاری اسناد پرداخت - حمل {transport_number}")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_UPLOAD_FREIGHT_PAYMENT_DOCS.value):
        audit_logger.activity(f"تلاش برای دسترسی به بارگذاری اسناد پرداخت بدون مجوز - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        transport = get_object_or_404(
            Transport.objects.select_related(
                'allocation__order',
                'allocation__order__customer',
                'driver',
                'driver_bank_account'
            ).prefetch_related(
                'allocation__order__order_items__raw_material',
                'freight_payment_document_attachments'
            ),
            transport_number=transport_number
        )
        
        # بررسی اینکه آیا کرایه از نوع "محاسبه شده در فی" است
        if transport.freight_payment_type == 'calculated_in_invoice':
            audit_logger.warning(
                f"تلاش برای بارگذاری سند برای حمل با کرایه محاسبه شده در فی - حمل {transport_number}"
            )
            messages.info(request, 'این حمل دارای کرایه محاسبه شده در فی است و نیازی به بارگذاری سند پرداخت ندارد.')
            return redirect('accounting:upload_fare_payment_docs_list')
        
        # Check if transport is in valid status (awaiting_wh_reconciliation, pending_settlement, or awaiting_payment_doc)
        # and doesn't already have a document
        if transport.status not in [
            Transport.STATUS_AWAITING_WH_RECONCILIATION,
            Transport.STATUS_AWAITING_SETTLEMENT,
            Transport.STATUS_AWAITING_PAYMENT_DOC
        ]:
            audit_logger.warning(
                f"تلاش برای بارگذاری سند در وضعیت نامناسب - حمل {transport_number} - "
                f"وضعیت: {transport.get_status_display()}"
            )
            messages.warning(request, 'این حمل در وضعیت مناسب برای بارگذاری اسناد پرداخت نیست.')
            return redirect('accounting:upload_fare_payment_docs_list')
        
        # Check if document already uploaded (یک فایل اصلی یا حداقل یک پیوست)
        has_docs = (
            (transport.freight_payment_document and str(transport.freight_payment_document).strip())
            or transport.freight_payment_document_attachments.exists()
        )
        if has_docs:
            audit_logger.warning(f"تلاش برای بارگذاری مجدد سند - حمل {transport_number}")
            messages.info(request, 'سند پرداخت قبلاً برای این حمل بارگذاری شده است.')
            return redirect('accounting:upload_fare_payment_docs_list')
        
        if request.method == 'POST':
            doc_files = request.FILES.getlist('document_attachments')
            if not doc_files:
                messages.error(request, 'حداقل یک فایل سند الزامی است.')
                form = UploadFarePaymentDocForm(instance=transport)
            else:
                form = UploadFarePaymentDocForm(request.POST, instance=transport)
                if form.is_valid():
                    try:
                        from django.db import transaction as db_transaction
                        
                        with db_transaction.atomic():
                            # اولین فایل به فیلد اصلی (سازگاری با قبل)
                            transport = form.save(commit=False)
                            transport.freight_payment_document = doc_files[0]
                            transport.freight_payment_document_uploaded_at = timezone.now()
                            transport.freight_payment_document_uploaded_by = request.user
                            transport.payment_doc_uploaded = True
                            
                            original_status = transport.status
                            if transport.logistic_confirmed:
                                transport.status = Transport.STATUS_COMPLETED
                                bug_logger.info(f"حمل {transport_number} تکمیل شد - تایید لجستیک و بارگذاری سند هر دو انجام شده است")
                            elif transport.status == Transport.STATUS_AWAITING_WH_RECONCILIATION:
                                pass
                            else:
                                transport.status = Transport.STATUS_AWAITING_PAYMENT_DOC
                            
                            transport.save()
                            
                            # ذخیره همه فایل‌ها به عنوان پیوست
                            for f in doc_files:
                                if f:
                                    FreightPaymentDocumentAttachment.objects.create(transport=transport, file=f)
                            
                            # بررسی اینکه آیا تمام حمل‌های سفارش تکمیل شده‌اند
                            po = transport.allocation.order if transport.allocation else None
                            if po and po.order_type == 'purchase':
                                remaining_weight = po.get_remaining_weight()
                                all_transports = Transport.objects.filter(allocation__order=po)
                                all_completed = not all_transports.exclude(status=Transport.STATUS_COMPLETED).exists()
                                if remaining_weight <= 0 and all_completed and po.status != Order.STATUS_COMPLETED:
                                    try:
                                        po.transition(Order.STATUS_COMPLETED, user=request.user, note='تمام حمل‌های سفارش تکمیل شدند و تمام وزن تخصیص یافت.')
                                        bug_logger.info(f"وضعیت سفارش {po.order_number} به 'تکمیل شده' تغییر یافت - تمام حمل‌ها تکمیل شدند")
                                        audit_logger.info(f"سفارش {po.order_number} به صورت خودکار تکمیل شد - تمام حمل‌ها تکمیل شدند")
                                    except Exception as order_transition_err:
                                        bug_logger.warning(f"خطا در تغییر وضعیت سفارش {po.order_number} به تکمیل شده: {order_transition_err}")
                            
                            status_message = 'سند پرداخت با موفقیت بارگذاری شد.'
                            if transport.status == Transport.STATUS_COMPLETED:
                                status_message += ' حمل تکمیل شد (تایید لجستیک قبلاً انجام شده بود).'
                            elif original_status == Transport.STATUS_AWAITING_WH_RECONCILIATION:
                                status_message += ' وضعیت حمل در حالت آماده خروج باقی ماند.'
                            else:
                                status_message += ' وضعیت به "در انتظار تایید لجستیک" تغییر یافت.'
                            
                            audit_logger.info(
                                f"بارگذاری موفق سند پرداخت - حمل {transport_number} | "
                                f"وضعیت قبلی: {original_status} | وضعیت جدید: {transport.status} | "
                                f"تعداد فایل: {len(doc_files)}"
                            )
                            
                        messages.success(request, status_message)
                        return redirect('accounting:upload_fare_payment_docs_list')
                    
                    except ValueError as ve:
                        bug_logger.warning(f"خطای تغییر وضعیت در بارگذاری سند - حمل {transport_number}: {str(ve)}")
                        messages.error(request, f'خطا در تغییر وضعیت: {str(ve)}')
                    except Exception as e:
                        bug_logger.error(f"خطا در بارگذاری سند پرداخت - حمل {transport_number}: {str(e)}", exc_info=True)
                        messages.error(request, 'خطا در بارگذاری سند پرداخت')
                else:
                    bug_logger.warning(f"فرم بارگذاری سند نامعتبر - حمل {transport_number}: {form.errors}")
                    messages.error(request, 'لطفا خطاهای فرم را بررسی کنید.')
        else:
            form = UploadFarePaymentDocForm(instance=transport)
        
        context = {
            'transport': transport,
            'form': form,
            'purchase_order': transport.purchase_order,
        }
        
        return render(request, 'accounting_upload_fare_payment_docs_detail.html', context)
        
    except Transport.DoesNotExist:
        audit_logger.alert(f"تلاش برای دسترسی به حمل ناموجود - حمل {transport_number}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect('accounting:upload_fare_payment_docs_list')
    except Exception as e:
        bug_logger.error(f"خطا در نمایش جزئیات بارگذاری سند - حمل {transport_number}: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری جزئیات حمل')
        return redirect('accounting:upload_fare_payment_docs_list')


@login_required
def uploaded_fare_payment_docs_list_view(request):
    """صفحه لیست حمل‌های با اسناد پرداخت بارگذاری شده"""
    audit_logger.info("دسترسی به لیست حمل‌های با اسناد پرداخت بارگذاری شده")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_UPLOAD_FREIGHT_PAYMENT_DOCS.value):
        audit_logger.activity("تلاش برای دسترسی به لیست حمل‌های با اسناد بارگذاری شده بدون مجوز")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        # Get transports with uploaded payment documents
        # Include all transports that have payment documents uploaded (regardless of status)
        transports = Transport.objects.filter(
            freight_payment_document__isnull=False
        ).exclude(
            freight_payment_document=''  # Exclude empty string
        ).select_related(
            'allocation__order',
            'allocation__order__customer',
            'driver',
            'freight_payment_document_uploaded_by'
        ).prefetch_related(
            'allocation__order__order_items__raw_material'
        ).order_by('-freight_payment_document_uploaded_at', '-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های با اسناد بارگذاری شده: {transports.count()}")
        
        # Create table with custom detail URL for uploaded docs
        table = UploadFarePaymentDocsTable(transports, detail_url_name='accounting:uploaded_fare_payment_docs_detail')
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
        }
        
        return render(request, 'accounting_uploaded_fare_payment_docs_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در نمایش لیست حمل‌های با اسناد بارگذاری شده: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها')
        return redirect('home')


@login_required
def uploaded_fare_payment_docs_detail_view(request, transport_number):
    """صفحه جزئیات حمل با اسناد پرداخت بارگذاری شده (فقط خواندنی)"""
    audit_logger.info(f"دسترسی به جزئیات حمل با اسناد بارگذاری شده - حمل {transport_number}")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_UPLOAD_FREIGHT_PAYMENT_DOCS.value):
        audit_logger.activity(f"تلاش برای دسترسی به جزئیات حمل با اسناد بارگذاری شده بدون مجوز - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        transport = get_object_or_404(
            Transport.objects.select_related(
                'allocation__order',
                'allocation__order__customer',
                'driver',
                'driver_bank_account',
                'freight_payment_document_uploaded_by'
            ).prefetch_related(
                'allocation__order__order_items__raw_material',
                'freight_payment_document_attachments'
            ),
            transport_number=transport_number
        )
        
        # بررسی اینکه حمل دارای سند بارگذاری شده است (فایل اصلی یا حداقل یک پیوست)
        has_any_doc = (
            (transport.freight_payment_document and str(transport.freight_payment_document).strip())
            or transport.freight_payment_document_attachments.exists()
        )
        if not has_any_doc:
            audit_logger.warning(f"تلاش برای مشاهده جزئیات حمل بدون سند - حمل {transport_number}")
            messages.warning(request, 'این حمل دارای سند بارگذاری شده نیست.')
            return redirect('accounting:uploaded_fare_payment_docs_list')
        
        context = {
            'transport': transport,
            'purchase_order': transport.purchase_order,
        }
        
        return render(request, 'accounting_uploaded_fare_payment_docs_detail.html', context)
        
    except Transport.DoesNotExist:
        audit_logger.alert(f"تلاش برای دسترسی به حمل ناموجود - حمل {transport_number}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect('accounting:uploaded_fare_payment_docs_list')
    except Exception as e:
        bug_logger.error(f"خطا در نمایش جزئیات حمل با اسناد بارگذاری شده - حمل {transport_number}: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری جزئیات حمل')
        return redirect('accounting:uploaded_fare_payment_docs_list')

