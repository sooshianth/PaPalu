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
from core.RBACModel.TaskPermission import TaskChoices
from core.RBACModel.Roles import user_has_task
from supply.tables import LogisticConfirmationTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


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
        table = LogisticConfirmationTable(transports)
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
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
