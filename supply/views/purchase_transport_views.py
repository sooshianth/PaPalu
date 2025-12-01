from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm
from django.db import transaction
import logging
from core.logging_levels import *
from django_tables2 import RequestConfig

from core.SupplyFolder.PurchaseTransportModel import (
    PurchaseTransport,
    PurchaseTransportStatusLog,
)
from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrder

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


class PurchaseTransportForm(ModelForm):
    class Meta:
        model = PurchaseTransport
        fields = [
            'purchase_order', 'transport_type', 'vehicle_type',
            'plate_number', 'driver',
            'freight_payment_type', 'initial_freight', 'total_freight',
            'discount', 'surplus', 'freight_payment',
            'driver_account_number', 'driver_sheba_number',
            'expected_arrival_date', 'actual_arrival_date',
            'loading_date', 'delivery_date',
            'gross_weight', 'tare_weight', 'net_weight',
            'waybill_number', 'notes'
        ]
        labels = {
            'purchase_order': 'سفارش خرید',
            'transport_type': 'نوع حمل',
            'vehicle_type': 'نوع ماشین',
            'plate_number': 'پلاک',
            'driver': 'راننده',
            'freight_payment_type': 'نوع کرایه',
            'initial_freight': 'کرایه اولیه',
            'total_freight': 'کرایه کل',
            'discount': 'تخفیف',
            'surplus': 'مازاد',
            'freight_payment': 'کرایه پرداختی',
            'driver_account_number': 'شماره حساب راننده',
            'driver_sheba_number': 'شماره شبا راننده',
            'expected_arrival_date': 'تاریخ پیش‌بینی ورود',
            'actual_arrival_date': 'تاریخ واقعی ورود',
            'loading_date': 'تاریخ بارگیری',
            'delivery_date': 'تاریخ تحویل',
            'gross_weight': 'وزن ناخالص',
            'tare_weight': 'وزن خالی',
            'net_weight': 'وزن خالص',
            'waybill_number': 'شماره بارنامه',
            'notes': 'یادداشت',
        }
        widgets = {
            'purchase_order': forms.Select(attrs={'class': 'form-control'}),
            'transport_type': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.TextInput(attrs={'class': 'form-control'}),
            'initial_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'surplus': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'driver_account_number': forms.Select(attrs={'class': 'form-control'}),
            'driver_sheba_number': forms.Select(attrs={'class': 'form-control'}),
            'expected_arrival_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'text', 'placeholder': '1403/09/15'}),
            'actual_arrival_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'text', 'placeholder': '1403/09/15'}),
            'loading_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'text', 'placeholder': '1403/09/15'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'text', 'placeholder': '1403/09/15'}),
            'gross_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'tare_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'net_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'waybill_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.PersonFolder.PersonModel import Person
        
        # Filter purchase orders that are not in draft or completed status
        self.fields['purchase_order'].queryset = ProcurementPurchaseOrder.objects.exclude(
            status__in=[
                ProcurementPurchaseOrder.STATUS_DRAFT,
                ProcurementPurchaseOrder.STATUS_COMPLETED
            ]
        ).order_by('-created_at')
        
        # Filter drivers only
        self.fields['driver'].queryset = Person.objects.filter(type='driver').order_by('name')
        self.fields['driver_account_number'].queryset = Person.objects.filter(type='driver').order_by('name')
        self.fields['driver_sheba_number'].queryset = Person.objects.filter(type='driver').order_by('name')


@login_required
def purchase_transport_list_view(request):
    """صفحه لیست حمل‌های خرید شامل دو جدول: فعال و تکمیل‌شده"""
    audit_logger.info("مشاهده لیست حمل‌های خرید")
    try:
        from supply.tables import PurchaseTransportTable
        # Orders awaiting transport definition (for quick create)
        awaiting_pos = ProcurementPurchaseOrder.objects.filter(
            status=ProcurementPurchaseOrder.STATUS_AWAITING_TRANSPORT_DEFINITION
        ).select_related('supplier').order_by('-created_at')
        
        # Active transports (not completed)
        active_transports = PurchaseTransport.objects.exclude(
            status=PurchaseTransport.STATUS_COMPLETED
        ).select_related('purchase_order', 'created_by').order_by('-created_at')
        
        # Completed transports
        completed_transports = PurchaseTransport.objects.filter(
            status=PurchaseTransport.STATUS_COMPLETED
        ).select_related('purchase_order', 'created_by').order_by('-created_at')
        
        # Create tables
        active_table = PurchaseTransportTable(active_transports, prefix='active-')
        completed_table = PurchaseTransportTable(completed_transports, prefix='completed-')
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 15}).configure(active_table)
        RequestConfig(request, paginate={'per_page': 15}).configure(completed_table)
        
        context = {
            'active_table': active_table,
            'completed_table': completed_table,
            'awaiting_pos': awaiting_pos,
        }
        return render(request, 'supply_purchase_transport_list.html', context)
    except Exception as e:
        bug_logger.error(f"Purchase transport list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها.')
        from supply.tables import PurchaseTransportTable
        active_table = PurchaseTransportTable([], prefix='active-')
        completed_table = PurchaseTransportTable([], prefix='completed-')
        return render(request, 'supply_purchase_transport_list.html', {
            'active_table': active_table,
            'completed_table': completed_table,
        })


@login_required
def create_purchase_transport_view(request):
    """ایجاد حمل جدید برای سفارش خرید"""
    audit_logger.info("ایجاد حمل خرید جدید")
    
    # Check if coming from purchase order detail page
    order_number = request.GET.get('order')
    initial_order = None
    if order_number:
        try:
            initial_order = ProcurementPurchaseOrder.objects.get(order_number=order_number)
        except ProcurementPurchaseOrder.DoesNotExist:
            pass
    
    try:
        if request.method == 'POST':
            form = PurchaseTransportForm(request.POST)
            if form.is_valid():
                with transaction.atomic():
                    pt = form.save(commit=False)
                    pt.status = PurchaseTransport.STATUS_DRAFT
                    pt.created_by = request.user
                    pt.save()
                    # Send notification when created
                    pt.send_guard_notification()
                messages.success(request, 'حمل ثبت شد.')
                return redirect(reverse('supply:purchase_transport_list'))
            else:
                bug_logger.warning(f"Purchase transport form invalid: {form.errors}")
        else:
            if initial_order:
                form = PurchaseTransportForm(initial={'purchase_order': initial_order})
                # Make purchase_order field read-only if coming from order detail
                form.fields['purchase_order'].disabled = True
            else:
                form = PurchaseTransportForm()
        
        return render(request, 'supply_create_purchase_transport.html', {
            'form': form,
            'initial_order': initial_order,
        })
    except Exception as e:
        bug_logger.error(f"Create purchase transport error: {e}")
        messages.error(request, 'خطا در ایجاد حمل.')
        return render(request, 'supply_create_purchase_transport.html', {
            'form': PurchaseTransportForm(),
            'initial_order': None,
        })


@login_required
def purchase_transport_detail_view(request, transport_number):
    """جزئیات حمل خرید"""
    audit_logger.info(f"مشاهده جزئیات حمل خرید {transport_number}")
    from supply.tables import PurchaseTransportStatusLogTable
    
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    logs = pt.status_logs.all().order_by('-changed_at')
    log_table = PurchaseTransportStatusLogTable(logs)
    RequestConfig(request, paginate=False).configure(log_table)
    
    # Get allowed next statuses for workflow transitions
    allowed_next_statuses = pt.WORKFLOW_ALLOWED.get(pt.status, set())
    next_status_choices = [(code, label) for code, label in pt.STATUS_CHOICES if code in allowed_next_statuses]
    
    return render(request, 'supply_purchase_transport_detail.html', {
        'pt': pt,
        'logs': logs,
        'log_table': log_table,
        'next_status_choices': next_status_choices,
    })


@login_required
def edit_purchase_transport_view(request, transport_number):
    """ویرایش حمل خرید"""
    audit_logger.info(f"ویرایش حمل خرید {transport_number}")
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    
    if pt.status == PurchaseTransport.STATUS_COMPLETED:
        messages.error(request, 'حمل تکمیل شده قابل ویرایش نیست.')
        return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
    
    try:
        if request.method == 'POST':
            form = PurchaseTransportForm(request.POST, instance=pt)
            if form.is_valid():
                form.save()
                messages.success(request, 'حمل ویرایش شد.')
                return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
            else:
                bug_logger.warning(f"Edit transport invalid form={form.errors}")
        else:
            form = PurchaseTransportForm(instance=pt)
        return render(request, 'supply_edit_purchase_transport.html', {
            'form': form,
            'pt': pt,
        })
    except Exception as e:
        bug_logger.error(f"Edit purchase transport error: {e}")
        messages.error(request, 'خطا در ویرایش حمل.')
        return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))


@login_required
def delete_purchase_transport_view(request, transport_number):
    """حذف حمل خرید (فقط پیش‌نویس)"""
    audit_logger.activity(f"حذف حمل خرید {transport_number}")
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    
    if not pt.can_delete():
        messages.error(request, 'حذف فقط در وضعیت پیش‌نویس مجاز است.')
        return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
    
    try:
        pt.delete()
        messages.success(request, 'حمل حذف شد.')
    except Exception as e:
        bug_logger.error(f"Delete purchase transport error: {e}")
        messages.error(request, 'خطا در حذف حمل.')
    return redirect(reverse('supply:purchase_transport_list'))


@login_required
def transition_purchase_transport_status_view(request, transport_number, new_status):
    """تغییر وضعیت حمل خرید"""
    audit_logger.activity(f"درخواست تغییر وضعیت حمل خرید {transport_number} -> {new_status}")
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    
    try:
        pt.transition(new_status, user=request.user)
        messages.success(request, 'وضعیت حمل بروزرسانی شد.')
    except ValueError as ve:
        bug_logger.warning(f"Invalid transport status transition {transport_number}: {ve}")
        messages.error(request, str(ve))
    except Exception as e:
        bug_logger.error(f"Transition purchase transport error: {e}")
        messages.error(request, 'خطای تغییر وضعیت حمل.')
    
    return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))


@login_required
def get_purchase_order_info_api(request, order_number):
    """API endpoint برای دریافت اطلاعات سفارش خرید"""
    from django.http import JsonResponse
    
    try:
        po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
        materials_data = []
        
        for material in po.materials.select_related('raw_material').all():
            materials_data.append({
                'name': material.raw_material.name,
                'quantity': str(material.quantity),
                'unit': material.unit,
            })
        
        data = {
            'order_date': po.created_at.strftime('%Y/%m/%d'),
            'supplier': po.supplier.name if po.supplier else '',
            'materials': materials_data,
        }
        
        return JsonResponse(data)
    except Exception as e:
        bug_logger.error(f"Get purchase order info API error: {e}")
        return JsonResponse({'error': 'خطا در دریافت اطلاعات سفارش'}, status=400)
