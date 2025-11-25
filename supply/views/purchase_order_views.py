from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django import forms
from django.forms import ModelForm, inlineformset_factory
from django.db import transaction
import logging
from core.logging_levels import *
from django_tables2 import RequestConfig

from core.SupplyFolder.ProcurementPurchaseOrderModel import (
    ProcurementPurchaseOrder,
    ProcurementPurchaseOrderMaterial,
    ProcurementPurchaseOrderStatusLog,
)
from core.PersonFolder.PersonModel import Person
from core.RawMaterialFolder.RawMaterialModel import RawMaterial

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


class ProcurementPurchaseOrderForm(ModelForm):
    class Meta:
        model = ProcurementPurchaseOrder
        fields = [
            'supplier', 'freight_payment_type',
            'subtotal_without_freight', 'freight_cost', 'vat_percentage',
            'pre_invoice_file', 'pre_invoice_approved'
        ]
        labels = {
            'supplier': 'تأمین‌کننده',
            'freight_payment_type': 'نوع پرداخت کرایه',
            'subtotal_without_freight': 'جمع بدون کرایه',
            'freight_cost': 'هزینه کرایه',
            'vat_percentage': 'درصد مالیات',
            'pre_invoice_file': 'فایل پیش‌فاکتور',
            'pre_invoice_approved': 'پیش‌فاکتور تایید شد؟',
        }
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.Select(attrs={'class': 'form-control'}),
            'subtotal_without_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vat_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'pre_invoice_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'pre_invoice_approved': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only supplier persons
        self.fields['supplier'].queryset = Person.objects.filter(type='supplier').order_by('name')
        # Lock financial fields if payment confirmed
        if self.instance and self.instance.payment_confirmed:
            for f in ['subtotal_without_freight', 'freight_cost', 'vat_percentage']:
                if f in self.fields:
                    self.fields[f].disabled = True


class ProcurementPurchaseOrderMaterialForm(ModelForm):
    class Meta:
        model = ProcurementPurchaseOrderMaterial
        fields = ['raw_material', 'quantity', 'unit']
        labels = {
            'raw_material': 'ماده اولیه',
            'quantity': 'مقدار',
            'unit': 'واحد',
        }
        widgets = {
            'raw_material': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['raw_material'].queryset = RawMaterial.objects.filter(status='active').order_by('name')


MaterialFormSet = inlineformset_factory(
    ProcurementPurchaseOrder,
    ProcurementPurchaseOrderMaterial,
    form=ProcurementPurchaseOrderMaterialForm,
    fields=['raw_material', 'quantity', 'unit'],
    extra=1,
    can_delete=True
)


def purchase_order_management_view(request):
    """صفحه مدیریت سفارش‌های خرید شامل دو جدول سفارشات باز و تکمیل‌شده"""
    audit_logger.info("مشاهده مدیریت سفارش‌های خرید")
    try:
        from supply.tables import ProcurementPurchaseOrderTable
        open_orders = ProcurementPurchaseOrder.objects.exclude(status=ProcurementPurchaseOrder.STATUS_COMPLETED).order_by('-created_at')
        completed_orders = ProcurementPurchaseOrder.objects.filter(status=ProcurementPurchaseOrder.STATUS_COMPLETED).order_by('-created_at')
        
        # Create tables
        open_table = ProcurementPurchaseOrderTable(open_orders, prefix='open-')
        completed_table = ProcurementPurchaseOrderTable(completed_orders, prefix='completed-')
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 15}).configure(open_table)
        RequestConfig(request, paginate={'per_page': 15}).configure(completed_table)
        
        context = {
            'open_table': open_table,
            'completed_table': completed_table,
        }
        return render(request, 'supply_purchase_order_management.html', context)
    except Exception as e:
        bug_logger.error(f"Purchase order management error: {e}")
        messages.error(request, 'خطا در بارگذاری سفارش‌های خرید.')
        from supply.tables import ProcurementPurchaseOrderTable
        open_table = ProcurementPurchaseOrderTable([], prefix='open-')
        completed_table = ProcurementPurchaseOrderTable([], prefix='completed-')
        return render(request, 'supply_purchase_order_management.html', {
            'open_table': open_table,
            'completed_table': completed_table,
        })


def create_procurement_purchase_order_view(request):
    """ایجاد سفارش خرید جدید"""
    audit_logger.info("ایجاد سفارش خرید جدید")
    try:
        if request.method == 'POST':
            form = ProcurementPurchaseOrderForm(request.POST, request.FILES)
            if form.is_valid():
                with transaction.atomic():
                    po = form.save(commit=False)
                    po.status = ProcurementPurchaseOrder.STATUS_DRAFT  # initial
                    po.save()  # triggers order_number generation
                    material_formset = MaterialFormSet(request.POST, instance=po, prefix='mat')
                    if material_formset.is_valid():
                        material_formset.save()
                    else:
                        raise ValueError(f"Material formset invalid: {material_formset.errors}")
                messages.success(request, 'سفارش خرید ثبت شد.')
                return redirect(reverse('supply:purchase_order_management'))
            else:
                bug_logger.warning(f"Procurement PO form invalid: {form.errors}")
                material_formset = MaterialFormSet(request.POST, prefix='mat')
        else:
            form = ProcurementPurchaseOrderForm()
            material_formset = MaterialFormSet(prefix='mat')
        return render(request, 'supply_create_procurement_purchase_order.html', {
            'form': form,
            'material_formset': material_formset,
        })
    except Exception as e:
        bug_logger.error(f"Create procurement PO error: {e}")
        messages.error(request, 'خطا در ایجاد سفارش خرید.')
        return render(request, 'supply_create_procurement_purchase_order.html', {
            'form': ProcurementPurchaseOrderForm(),
            'material_formset': MaterialFormSet(prefix='mat'),
        })


def procurement_purchase_order_detail_view(request, order_number):
    """جزئیات سفارش خرید"""
    audit_logger.info(f"مشاهده جزئیات سفارش خرید {order_number}")
    from supply.tables import ProcurementPurchaseOrderStatusLogTable
    po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
    materials = po.materials.select_related('raw_material').all()
    logs = po.status_logs.all()
    log_table = ProcurementPurchaseOrderStatusLogTable(logs)
    can_edit_financial = not po.payment_confirmed
    return render(request, 'supply_procurement_purchase_order_detail.html', {
        'po': po,
        'materials': materials,
        'logs': logs,
        'log_table': log_table,
        'can_edit_financial': can_edit_financial,
    })


def edit_procurement_purchase_order_view(request, order_number):
    """ویرایش سفارش خرید (فقط قبل از تایید پرداخت برای داده مالی)"""
    audit_logger.info(f"ویرایش سفارش خرید {order_number}")
    po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
    if po.status == ProcurementPurchaseOrder.STATUS_COMPLETED:
        messages.error(request, 'سفارش تکمیل شده قابل ویرایش نیست.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        if request.method == 'POST':
            form = ProcurementPurchaseOrderForm(request.POST, request.FILES, instance=po)
            material_formset = MaterialFormSet(request.POST, instance=po, prefix='mat')
            if form.is_valid() and material_formset.is_valid():
                with transaction.atomic():
                    form.save()
                    material_formset.save()
                messages.success(request, 'سفارش خرید ویرایش شد.')
                return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
            else:
                bug_logger.warning(f"Edit PO invalid form={form.errors} mat={material_formset.errors}")
        else:
            form = ProcurementPurchaseOrderForm(instance=po)
            material_formset = MaterialFormSet(instance=po, prefix='mat')
        return render(request, 'supply_edit_procurement_purchase_order.html', {
            'form': form,
            'material_formset': material_formset,
            'po': po,
        })
    except Exception as e:
        bug_logger.error(f"Edit procurement PO error: {e}")
        messages.error(request, 'خطا در ویرایش سفارش خرید.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))


def delete_procurement_purchase_order_view(request, order_number):
    audit_logger.activity(f"حذف سفارش خرید {order_number}")
    po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
    if not po.can_delete():
        messages.error(request, 'حذف فقط در وضعیت پیش‌نویس مجاز است.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        po.delete()
        messages.success(request, 'سفارش خرید حذف شد.')
    except Exception as e:
        bug_logger.error(f"Delete procurement PO error: {e}")
        messages.error(request, 'خطا در حذف سفارش.')
    return redirect(reverse('supply:purchase_order_management'))


def transition_procurement_purchase_order_status_view(request, order_number, new_status):
    audit_logger.activity(f"درخواست تغییر وضعیت سفارش خرید {order_number} -> {new_status}")
    po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
    try:
        po.transition(new_status, user=request.user)
        messages.success(request, 'وضعیت سفارش بروزرسانی شد.')
    except ValueError as ve:
        bug_logger.warning(f"Invalid PO status transition {order_number}: {ve}")
        messages.error(request, str(ve))
    except Exception as e:
        bug_logger.error(f"Transition procurement PO error: {e}")
        messages.error(request, 'خطای تغییر وضعیت سفارش.')
    return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))


def confirm_procurement_purchase_order_payment_view(request, order_number):
    """تایید پرداخت سفارش خرید و قفل شدن داده‌های مالی"""
    audit_logger.activity(f"تایید پرداخت سفارش خرید {order_number}")
    po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
    if po.payment_confirmed:
        messages.info(request, 'پرداخت قبلاً تایید شده است.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        po.payment_confirmed = True
        po.save(update_fields=['payment_confirmed'])
        ProcurementPurchaseOrderStatusLog.objects.create(
            purchase_order=po,
            old_status=po.status,
            new_status=po.status,
            changed_by=request.user,
            note='تایید پرداخت'
        )
        messages.success(request, 'پرداخت تایید شد. داده‌های مالی قفل شدند.')
    except Exception as e:
        bug_logger.error(f"Confirm payment PO error: {e}")
        messages.error(request, 'خطا در تایید پرداخت.')
    return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
