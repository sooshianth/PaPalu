from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django import forms
from django.forms import ModelForm
from django_tables2 import RequestConfig
from django.utils import timezone
import logging
from core.logging_levels import *

from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
from core.RBACModel.TaskPermission import TaskChoices
from core.RBACModel.Roles import user_has_task
from supply.tables import UploadFarePaymentDocsTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


class UploadFarePaymentDocForm(ModelForm):
    """فرم بارگذاری اسناد پرداخت کرایه"""
    
    class Meta:
        model = PurchaseTransport
        fields = ['freight_payment_document']
        labels = {
            'freight_payment_document': 'سند پرداخت کرایه',
        }
        widgets = {
            'freight_payment_document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['freight_payment_document'].required = True


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
        # Get transports awaiting payment document upload
        # Include both awaiting_payment_doc (new workflow) and completed (legacy/backward compatibility)
        # that don't have payment documents uploaded yet
        from django.db.models import Q
        transports = PurchaseTransport.objects.filter(
            status__in=[PurchaseTransport.STATUS_AWAITING_PAYMENT_DOC, PurchaseTransport.STATUS_COMPLETED]
        ).filter(
            Q(freight_payment_document__isnull=True) | Q(freight_payment_document='')  # NULL or empty string
        ).select_related(
            'purchase_order',
            'purchase_order__supplier',
            'driver'
        ).order_by('-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های در انتظار بارگذاری اسناد: {transports.count()}")
        
        # Create table
        table = UploadFarePaymentDocsTable(transports)
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
        }
        
        return render(request, 'supply_upload_fare_payment_docs_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در نمایش لیست بارگذاری اسناد پرداخت: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها')
        return redirect('supply:home')


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
            PurchaseTransport.objects.select_related(
                'purchase_order',
                'purchase_order__supplier',
                'driver'
            ),
            transport_number=transport_number
        )
        
        # Check if transport is in valid status (awaiting_payment_doc or completed for legacy)
        # and doesn't already have a document
        if transport.status not in [PurchaseTransport.STATUS_AWAITING_PAYMENT_DOC, PurchaseTransport.STATUS_COMPLETED]:
            audit_logger.warning(
                f"تلاش برای بارگذاری سند در وضعیت نامناسب - حمل {transport_number} - "
                f"وضعیت: {transport.get_status_display()}"
            )
            messages.warning(request, 'این حمل در وضعیت مناسب برای بارگذاری اسناد پرداخت نیست.')
            return redirect('supply:upload_fare_payment_docs_list')
        
        # Check if document already uploaded
        if transport.freight_payment_document and str(transport.freight_payment_document).strip():
            audit_logger.warning(f"تلاش برای بارگذاری مجدد سند - حمل {transport_number}")
            messages.info(request, 'سند پرداخت قبلاً برای این حمل بارگذاری شده است.')
            return redirect('supply:upload_fare_payment_docs_list')
        
        if request.method == 'POST':
            form = UploadFarePaymentDocForm(request.POST, request.FILES, instance=transport)
            
            if form.is_valid():
                try:
                    # Save the transport with payment document
                    transport = form.save(commit=False)
                    transport.freight_payment_document_uploaded_at = timezone.now()
                    transport.freight_payment_document_uploaded_by = request.user
                    transport.save()
                    
                    # Transition to payment_doc_uploaded status
                    transport.transition(
                        new_status=PurchaseTransport.STATUS_PAYMENT_DOC_UPLOADED,
                        user=request.user,
                        note='بارگذاری سند پرداخت کرایه'
                    )
                    
                    # Log successful upload
                    audit_logger.info(
                        f"بارگذاری موفق سند پرداخت - حمل {transport_number} | "
                        f"فایل: {transport.freight_payment_document.name if transport.freight_payment_document else 'N/A'}"
                    )
                    
                    messages.success(request, 'سند پرداخت با موفقیت بارگذاری شد و وضعیت تکمیل گردید.')
                    return redirect('supply:upload_fare_payment_docs_list')
                    
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
        
        return render(request, 'supply_upload_fare_payment_docs_detail.html', context)
        
    except PurchaseTransport.DoesNotExist:
        audit_logger.alert(f"تلاش برای دسترسی به حمل ناموجود - حمل {transport_number}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect('supply:upload_fare_payment_docs_list')
    except Exception as e:
        bug_logger.error(f"خطا در نمایش جزئیات بارگذاری سند - حمل {transport_number}: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری جزئیات حمل')
        return redirect('supply:upload_fare_payment_docs_list')
