from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django import forms
from django.forms import ModelForm
from django_tables2 import RequestConfig
import logging
from core.logging_levels import *

from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
from core.SupplyFolder.ProcurementPurchaseOrderModel import (
    ProcurementPurchaseOrder,
    ProcurementPurchaseOrderMaterial,
)
from core.PersonFolder.PersonModel import Person
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from django.contrib.auth import get_user_model
from supply.tables import LogisticConfirmationTable

User = get_user_model()
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


# ==================== Field Access Helper Functions ====================

def get_accessible_purchase_transport_fields_logistic(user):
    """Check field access for PurchaseTransport model (view permission)"""
    return {
        'transport_number': user_can_access_field(user, PurchaseTransport, 'transport_number', 'view'),
        'purchase_order': user_can_access_field(user, PurchaseTransport, 'purchase_order', 'view'),
        'status': user_can_access_field(user, PurchaseTransport, 'status', 'view'),
        'vehicle_type': user_can_access_field(user, PurchaseTransport, 'vehicle_type', 'view'),
        'plate_number': user_can_access_field(user, PurchaseTransport, 'plate_number', 'view'),
        'driver': user_can_access_field(user, PurchaseTransport, 'driver', 'view'),
        'gross_weight': user_can_access_field(user, PurchaseTransport, 'gross_weight', 'view'),
        'tare_weight': user_can_access_field(user, PurchaseTransport, 'tare_weight', 'view'),
        'net_weight': user_can_access_field(user, PurchaseTransport, 'net_weight', 'view'),
        'freight_payment_type': user_can_access_field(user, PurchaseTransport, 'freight_payment_type', 'view'),
        'initial_freight': user_can_access_field(user, PurchaseTransport, 'initial_freight', 'view'),
        'total_freight': user_can_access_field(user, PurchaseTransport, 'total_freight', 'view'),
        'discount': user_can_access_field(user, PurchaseTransport, 'discount', 'view'),
        'surplus': user_can_access_field(user, PurchaseTransport, 'surplus', 'view'),
        'freight_payment': user_can_access_field(user, PurchaseTransport, 'freight_payment', 'view'),
        'created_at': user_can_access_field(user, PurchaseTransport, 'created_at', 'view'),
    }


def get_accessible_purchase_transport_fields_logistic_edit(user):
    """Check field access for PurchaseTransport model (edit permission)"""
    return {
        'freight_payment_type': user_can_access_field(user, PurchaseTransport, 'freight_payment_type', 'edit'),
        'initial_freight': user_can_access_field(user, PurchaseTransport, 'initial_freight', 'edit'),
        'total_freight': user_can_access_field(user, PurchaseTransport, 'total_freight', 'edit'),
        'discount': user_can_access_field(user, PurchaseTransport, 'discount', 'edit'),
        'surplus': user_can_access_field(user, PurchaseTransport, 'surplus', 'edit'),
        'freight_payment': user_can_access_field(user, PurchaseTransport, 'freight_payment', 'edit'),
    }


def get_accessible_procurement_purchase_order_fields_logistic(user):
    """Check field access for ProcurementPurchaseOrder model (for logistic views)"""
    return {
        'order_number': user_can_access_field(user, ProcurementPurchaseOrder, 'order_number', 'view'),
        'status': user_can_access_field(user, ProcurementPurchaseOrder, 'status', 'view'),
        'supplier': user_can_access_field(user, ProcurementPurchaseOrder, 'supplier', 'view'),
        'materials': user_can_access_field(user, ProcurementPurchaseOrder, 'materials', 'view'),
        'created_at': user_can_access_field(user, ProcurementPurchaseOrder, 'created_at', 'view'),
    }


def get_accessible_person_fields_logistic(user):
    """Check field access for Person model (for logistic views)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'phone_number': user_can_access_field(user, Person, 'phone_number', 'view'),
        'type': user_can_access_field(user, Person, 'type', 'view'),
    }

# ==================== End Field Access Helper Functions ====================


class LogisticConfirmationForm(ModelForm):
    """فرم تایید لجستیک برای تکمیل اطلاعات مالی حمل"""
    
    class Meta:
        model = PurchaseTransport
        fields = [
            'freight_payment_type',
            'initial_freight',
            'total_freight',
            'discount',
            'surplus',
            'freight_payment',
        ]
        labels = {
            'freight_payment_type': 'نوع کرایه',
            'initial_freight': 'کرایه اولیه',
            'total_freight': 'کرایه کل',
            'discount': 'تخفیف',
            'surplus': 'مازاد',
            'freight_payment': 'کرایه پرداختی',
        }
        widgets = {
            'freight_payment_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نقدی، اعتباری و غیره',
                'required': True
            }),
            'initial_freight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'total_freight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'surplus': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'freight_payment': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required
        for field_name in self.fields:
            self.fields[field_name].required = True


@login_required
def logistic_confirmation_list_view(request):
    """صفحه لیست حمل‌های در انتظار تایید لجستیک"""
    audit_logger.info(f"دسترسی به لیست تایید لجستیک")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_LOGISTIC_CONFIRMATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به لیست تایید لجستیک بدون مجوز")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_logistic(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_logistic(request.user)
    accessible_person_fields = get_accessible_person_fields_logistic(request.user)
    
    try:
        # Get transports awaiting settlement (status = awaiting_settlement)
        transports = PurchaseTransport.objects.filter(
            status=PurchaseTransport.STATUS_AWAITING_SETTLEMENT
        ).select_related(
            'purchase_order',
            'purchase_order__supplier',
            'driver'
        ).order_by('-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های در انتظار تسویه: {transports.count()}")
        
        # Create table
        table = LogisticConfirmationTable(transports, accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_person_fields': accessible_person_fields,
        }
        
        return render(request, 'supply_logistic_confirmation_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در نمایش لیست تایید لجستیک: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها')
        return redirect('supply:home')


@login_required
def logistic_confirmation_detail_view(request, transport_number):
    """صفحه جزئیات و تایید لجستیک برای یک حمل"""
    audit_logger.info(f"دسترسی به جزئیات تایید لجستیک - حمل {transport_number}")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_LOGISTIC_CONFIRMATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به تایید لجستیک بدون مجوز - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_logistic_edit(request.user)
    accessible_transport_fields_view = get_accessible_purchase_transport_fields_logistic(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_logistic(request.user)
    accessible_person_fields = get_accessible_person_fields_logistic(request.user)
    
    try:
        transport = get_object_or_404(
            PurchaseTransport.objects.select_related(
                'purchase_order',
                'purchase_order__supplier',
                'driver'
            ),
            transport_number=transport_number
        )
        
        # Check if transport is in awaiting_settlement status
        if transport.status != PurchaseTransport.STATUS_AWAITING_SETTLEMENT:
            audit_logger.warning(
                f"تلاش برای تایید لجستیک در وضعیت نامناسب - حمل {transport_number} - "
                f"وضعیت: {transport.get_status_display()}"
            )
            messages.warning(request, 'این حمل در وضعیت مناسب برای تایید لجستیک نیست.')
            return redirect('supply:logistic_confirmation_list')
        
        if request.method == 'POST':
            form = LogisticConfirmationForm(request.POST, instance=transport)
            
            if form.is_valid():
                try:
                    # Save the transport with financial data
                    transport = form.save()
                    
                    # Transition to awaiting payment doc status
                    transport.transition(
                        new_status=PurchaseTransport.STATUS_AWAITING_PAYMENT_DOC,
                        user=request.user,
                        note='تایید لجستیک و تکمیل اطلاعات مالی'
                    )
                    
                    # Log successful completion
                    audit_logger.info(
                        f"تایید لجستیک موفق - حمل {transport_number} | "
                        f"نوع_کرایه: {transport.freight_payment_type} | "
                        f"کرایه_کل: {transport.total_freight} | "
                        f"کرایه_پرداختی: {transport.freight_payment}"
                    )
                    
                    messages.success(request, 'تایید لجستیک با موفقیت انجام شد و وضعیت به تسویه شده تغییر یافت.')
                    return redirect('supply:logistic_confirmation_list')
                    
                except ValueError as ve:
                    bug_logger.warning(f"خطای تغییر وضعیت در تایید لجستیک - حمل {transport_number}: {str(ve)}")
                    messages.error(request, f'خطا در تغییر وضعیت: {str(ve)}')
                except Exception as e:
                    bug_logger.error(f"خطا در تایید لجستیک - حمل {transport_number}: {str(e)}", exc_info=True)
                    messages.error(request, 'خطا در ثبت تایید لجستیک')
            else:
                bug_logger.warning(f"فرم تایید لجستیک نامعتبر - حمل {transport_number}: {form.errors}")
                messages.error(request, 'لطفا خطاهای فرم را بررسی کنید.')
        else:
            form = LogisticConfirmationForm(instance=transport)
        
        context = {
            'transport': transport,
            'form': form,
            'purchase_order': transport.purchase_order,
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_transport_fields_view': accessible_transport_fields_view,
            'accessible_po_fields': accessible_po_fields,
            'accessible_person_fields': accessible_person_fields,
        }
        
        return render(request, 'supply_logistic_confirmation_detail.html', context)
        
    except PurchaseTransport.DoesNotExist:
        audit_logger.alert(f"تلاش برای دسترسی به حمل ناموجود - حمل {transport_number}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect('supply:logistic_confirmation_list')
    except Exception as e:
        bug_logger.error(f"خطا در نمایش جزئیات تایید لجستیک - حمل {transport_number}: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری جزئیات حمل')
        return redirect('supply:logistic_confirmation_list')
