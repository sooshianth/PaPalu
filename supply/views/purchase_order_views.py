from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm, inlineformset_factory
from django.db import transaction
from django.http import HttpResponseForbidden
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
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from django.contrib.auth import get_user_model

User = get_user_model()

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_procurement_purchase_order_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل ProcurementPurchaseOrder"""
    return {
        'order_number': user_can_access_field(user, ProcurementPurchaseOrder, 'order_number', 'view'),
        'supplier': user_can_access_field(user, ProcurementPurchaseOrder, 'supplier', 'view'),
        'status': user_can_access_field(user, ProcurementPurchaseOrder, 'status', 'view'),
        'freight_payment_type': user_can_access_field(user, ProcurementPurchaseOrder, 'freight_payment_type', 'view'),
        'subtotal_without_freight': user_can_access_field(user, ProcurementPurchaseOrder, 'subtotal_without_freight', 'view'),
        'freight_cost': user_can_access_field(user, ProcurementPurchaseOrder, 'freight_cost', 'view'),
        'vat_percentage': user_can_access_field(user, ProcurementPurchaseOrder, 'vat_percentage', 'view'),
        'payment_confirmed': user_can_access_field(user, ProcurementPurchaseOrder, 'payment_confirmed', 'view'),
        'external_system_id': user_can_access_field(user, ProcurementPurchaseOrder, 'external_system_id', 'view'),
        'created_by': user_can_access_field(user, ProcurementPurchaseOrder, 'created_by', 'view'),
        'created_at': user_can_access_field(user, ProcurementPurchaseOrder, 'created_at', 'view'),
        'updated_at': user_can_access_field(user, ProcurementPurchaseOrder, 'updated_at', 'view'),
    }


def get_accessible_procurement_purchase_order_material_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل ProcurementPurchaseOrderMaterial"""
    return {
        'raw_material': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'raw_material', 'view'),
        'quantity': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'quantity', 'view'),
        'unit': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'unit', 'view'),
        'notes': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'notes', 'view'),
        'unit_price': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'unit_price', 'view'),
        'total_price': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'total_price', 'view'),
        'freight_included': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'freight_included', 'view'),
        'vat_on_material': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'vat_on_material', 'view'),
        'freight_cost_completed': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'freight_cost_completed', 'view'),
        'total_cost_completed': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'total_cost_completed', 'view'),
        'external_allocation_id': user_can_access_field(user, ProcurementPurchaseOrderMaterial, 'external_allocation_id', 'view'),
    }


def get_accessible_raw_material_fields_for_po(user):
    """دریافت فیلدهای قابل دسترس برای مدل RawMaterial"""
    return {
        'raw_material_id': user_can_access_field(user, RawMaterial, 'raw_material_id', 'view'),
        'name': user_can_access_field(user, RawMaterial, 'name', 'view'),
        'physical_form': user_can_access_field(user, RawMaterial, 'physical_form', 'view'),
    }


def get_accessible_person_fields_for_po(user):
    """دریافت فیلدهای قابل دسترس برای مدل Person (supplier)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'national_id': user_can_access_field(user, Person, 'national_id', 'view'),
    }


def get_accessible_user_fields_for_po(user):
    """دریافت فیلدهای قابل دسترس برای مدل User (created_by)"""
    return {
        'username': user_can_access_field(user, User, 'username', 'view'),
        'first_name': user_can_access_field(user, User, 'first_name', 'view'),
        'last_name': user_can_access_field(user, User, 'last_name', 'view'),
    }


class ProcurementPurchaseOrderForm(ModelForm):
    class Meta:
        model = ProcurementPurchaseOrder
        fields = [
            'supplier', 'freight_payment_type',
            'subtotal_without_freight', 'freight_cost', 'vat_percentage',
            'external_system_id'
        ]
        labels = {
            'supplier': 'تأمین‌کننده',
            'freight_payment_type': 'نوع پرداخت کرایه',
            'subtotal_without_freight': 'جمع بدون کرایه',
            'freight_cost': 'هزینه کرایه',
            'vat_percentage': 'درصد مالیات بر ارزش افزوده',
            'external_system_id': 'شناسه یکتا در سیستم دامپروش/کی‌اچ/انبار/لبه‌ژنت',
        }
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.Select(attrs={'class': 'form-control'}),
            'subtotal_without_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vat_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'external_system_id': forms.TextInput(attrs={'class': 'form-control'}),
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
        fields = [
            'raw_material', 'quantity', 'unit', 'notes',
            'unit_price', 'total_price', 'freight_included',
            'vat_on_material', 'freight_cost_completed',
            'total_cost_completed', 'external_allocation_id'
        ]
        labels = {
            'raw_material': 'ماده اولیه',
            'quantity': 'مقدار',
            'unit': 'واحد',
            'notes': 'توضیحات',
            'unit_price': 'قیمت واحد',
            'total_price': 'قیمت کل',
            'freight_included': 'بهای تمام شده بدون احتساب کرایه',
            'vat_on_material': 'مالیات بر ارزش افزوده',
            'freight_cost_completed': 'بهای تمام شده کرایه خرید',
            'total_cost_completed': 'بهای تمام شده خرید',
            'external_allocation_id': 'شناسه تخصیص',
        }
        widgets = {
            'raw_material': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_included': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'vat_on_material': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_cost_completed': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_cost_completed': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'external_allocation_id': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['raw_material'].queryset = RawMaterial.objects.filter(status='active').order_by('name')
    
    def clean(self):
        """اعتبارسنجی: واحد باید با واحد اصلی یا فرعی ماده اولیه مطابقت داشته باشد"""
        cleaned_data = super().clean()
        raw_material = cleaned_data.get('raw_material')
        unit = cleaned_data.get('unit')
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        total_price = cleaned_data.get('total_price')
        
        if raw_material and unit:
            # Get allowed units from raw material
            allowed_units = []
            if raw_material.primary_unit:
                allowed_units.append(raw_material.get_primary_unit_display())
            if raw_material.secondary_unit:
                allowed_units.append(raw_material.get_secondary_unit_display())
            
            # Check if entered unit matches
            if unit not in allowed_units and allowed_units:
                raise forms.ValidationError(
                    f'واحد "{unit}" برای ماده اولیه "{raw_material.name}" معتبر نیست. '
                    f'واحدهای مجاز: {" یا ".join(allowed_units)}'
                )
        
        # Validate total price calculation
        if quantity and unit_price and total_price:
            calculated_total = quantity * unit_price
            # Allow small floating point difference
            if abs(float(total_price) - float(calculated_total)) > 0.01:
                cleaned_data['total_price'] = calculated_total
        
        return cleaned_data


MaterialFormSet = inlineformset_factory(
    ProcurementPurchaseOrder,
    ProcurementPurchaseOrderMaterial,
    form=ProcurementPurchaseOrderMaterialForm,
    fields=[
        'raw_material', 'quantity', 'unit', 'notes',
        'unit_price', 'total_price', 'freight_included',
        'vat_on_material', 'freight_cost_completed',
        'total_cost_completed', 'external_allocation_id'
    ],
    extra=1,
    can_delete=True
)


@login_required
def purchase_order_management_view(request):
    """صفحه مدیریت سفارش‌های خرید شامل دو جدول سفارشات باز و تکمیل‌شده"""
    audit_logger.info("مشاهده مدیریت سفارش‌های خرید")
    
    # Check task permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_CREATE_ORDER.value):
        audit_logger.activity(f"تلاش برای دسترسی به مدیریت سفارش‌های خرید بدون مجوز - کاربر: {request.user.username}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_po_fields = get_accessible_procurement_purchase_order_fields(request.user)
    accessible_po_material_fields = get_accessible_procurement_purchase_order_material_fields(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_po(request.user)
    accessible_person_fields = get_accessible_person_fields_for_po(request.user)
    accessible_user_fields = get_accessible_user_fields_for_po(request.user)
    
    try:
        from supply.tables import ProcurementPurchaseOrderTable
        open_orders = ProcurementPurchaseOrder.objects.exclude(
            status=ProcurementPurchaseOrder.STATUS_COMPLETED
        ).select_related('supplier', 'created_by').prefetch_related(
            'materials__raw_material'
        ).order_by('-created_at')
        completed_orders = ProcurementPurchaseOrder.objects.filter(
            status=ProcurementPurchaseOrder.STATUS_COMPLETED
        ).select_related('supplier', 'created_by').prefetch_related(
            'materials__raw_material'
        ).order_by('-created_at')
        
        # Prepare table accessible fields dict
        # materials_list requires both PO material and raw material access
        table_accessible_fields = {
            'order_number': accessible_po_fields.get('order_number', False),
            'status': accessible_po_fields.get('status', False),
            'materials_list': (
                accessible_po_material_fields.get('raw_material', False) and
                accessible_raw_material_fields.get('name', False)
            ),
            'supplier': (
                accessible_po_fields.get('supplier', False) and
                accessible_person_fields.get('name', False)
            ),
            'created_by': accessible_po_fields.get('created_by', False),
            'created_at': accessible_po_fields.get('created_at', False),
        }
        
        # Create tables
        open_table = ProcurementPurchaseOrderTable(open_orders, prefix='open-', accessible_fields=table_accessible_fields)
        completed_table = ProcurementPurchaseOrderTable(completed_orders, prefix='completed-', accessible_fields=table_accessible_fields)
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 15}).configure(open_table)
        RequestConfig(request, paginate={'per_page': 15}).configure(completed_table)
        
        context = {
            'open_table': open_table,
            'completed_table': completed_table,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
        }
        return render(request, 'supply_purchase_order_management.html', context)
    except Exception as e:
        bug_logger.error(f"Purchase order management error: {e}")
        messages.error(request, 'خطا در بارگذاری سفارش‌های خرید.')
        from supply.tables import ProcurementPurchaseOrderTable
        table_accessible_fields = {
            'order_number': accessible_po_fields.get('order_number', False),
            'status': accessible_po_fields.get('status', False),
            'materials_list': False,
            'supplier': False,
            'created_by': accessible_po_fields.get('created_by', False),
            'created_at': accessible_po_fields.get('created_at', False),
        }
        open_table = ProcurementPurchaseOrderTable([], prefix='open-', accessible_fields=table_accessible_fields)
        completed_table = ProcurementPurchaseOrderTable([], prefix='completed-', accessible_fields=table_accessible_fields)
        return render(request, 'supply_purchase_order_management.html', {
            'open_table': open_table,
            'completed_table': completed_table,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
        })


@login_required
def create_procurement_purchase_order_view(request):
    """ایجاد سفارش خرید جدید"""
    audit_logger.info("ایجاد سفارش خرید جدید")
    
    # Check task permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_CREATE_ORDER.value):
        audit_logger.activity(f"تلاش برای دسترسی به ایجاد سفارش خرید بدون مجوز - کاربر: {request.user.username}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions (edit permissions for form)
    accessible_po_fields = {
        'supplier': user_can_access_field(request.user, ProcurementPurchaseOrder, 'supplier', 'edit'),
        'freight_payment_type': user_can_access_field(request.user, ProcurementPurchaseOrder, 'freight_payment_type', 'edit'),
        'subtotal_without_freight': user_can_access_field(request.user, ProcurementPurchaseOrder, 'subtotal_without_freight', 'edit'),
        'freight_cost': user_can_access_field(request.user, ProcurementPurchaseOrder, 'freight_cost', 'edit'),
        'vat_percentage': user_can_access_field(request.user, ProcurementPurchaseOrder, 'vat_percentage', 'edit'),
        'external_system_id': user_can_access_field(request.user, ProcurementPurchaseOrder, 'external_system_id', 'edit'),
    }
    
    accessible_po_material_fields = {
        'raw_material': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'raw_material', 'edit'),
        'quantity': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'quantity', 'edit'),
        'unit': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'unit', 'edit'),
        'notes': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'notes', 'edit'),
        'unit_price': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'unit_price', 'edit'),
        'total_price': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'total_price', 'edit'),
        'freight_included': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'freight_included', 'edit'),
        'vat_on_material': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'vat_on_material', 'edit'),
        'freight_cost_completed': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'freight_cost_completed', 'edit'),
        'total_cost_completed': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'total_cost_completed', 'edit'),
        'external_allocation_id': user_can_access_field(request.user, ProcurementPurchaseOrderMaterial, 'external_allocation_id', 'edit'),
    }
    
    try:
        if request.method == 'POST':
            form = ProcurementPurchaseOrderForm(request.POST, request.FILES)
            if form.is_valid():
                with transaction.atomic():
                    po = form.save(commit=False)
                    po.created_by = request.user
                    po.save()  # triggers order_number generation, status defaults to DRAFT
                    
                    # Create initial status log
                    ProcurementPurchaseOrderStatusLog.objects.create(
                        purchase_order=po,
                        old_status='',
                        new_status=po.status,
                        changed_by=request.user,
                        note='ایجاد سفارش خرید'
                    )
                    
                    material_formset = MaterialFormSet(request.POST, instance=po, prefix='mat')
                    if material_formset.is_valid():
                        material_formset.save()
                    else:
                        bug_logger.warning(f"Material formset invalid on create: {material_formset.errors}")
                        messages.error(request, 'مواد اولیه تکراری یا نامعتبر هستند. لطفاً خطاهای فرم را بررسی و اصلاح کنید.')
                        # Rollback parent creation to avoid orphan PO
                        try:
                            po.delete()
                        except Exception:
                            pass
                        return render(request, 'supply_create_procurement_purchase_order.html', {
                            'form': form,
                            'material_formset': material_formset,
                            'accessible_po_fields': accessible_po_fields,
                            'accessible_po_material_fields': accessible_po_material_fields,
                        })
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
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        })
    except Exception as e:
        bug_logger.error(f"Create procurement PO error: {e}")
        messages.error(request, 'خطا در ایجاد سفارش خرید.')
        return render(request, 'supply_create_procurement_purchase_order.html', {
            'form': ProcurementPurchaseOrderForm(),
            'material_formset': MaterialFormSet(prefix='mat'),
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        })


@login_required
def procurement_purchase_order_detail_view(request, order_number):
    """جزئیات سفارش خرید"""
    audit_logger.info(f"مشاهده جزئیات سفارش خرید {order_number}")
    from supply.tables import ProcurementPurchaseOrderStatusLogTable
    from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
    
    po = get_object_or_404(ProcurementPurchaseOrder, order_number=order_number)
    materials = po.materials.select_related('raw_material').all()
    logs = po.status_logs.all().order_by('-changed_at')
    log_table = ProcurementPurchaseOrderStatusLogTable(logs)
    RequestConfig(request, paginate=False).configure(log_table)
    can_edit_financial = not po.payment_confirmed
    
    # Get transports for this purchase order
    transports = PurchaseTransport.objects.filter(purchase_order=po).order_by('-created_at')
    
    # Get allowed next statuses for workflow transitions
    allowed_next_statuses = po.WORKFLOW_ALLOWED.get(po.status, set())
    next_status_choices = [(code, label) for code, label in po.STATUS_CHOICES if code in allowed_next_statuses]
    
    return render(request, 'supply_procurement_purchase_order_detail.html', {
        'po': po,
        'materials': materials,
        'logs': logs,
        'log_table': log_table,
        'can_edit_financial': can_edit_financial,
        'next_status_choices': next_status_choices,
        'transports': transports,
    })


@login_required
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


@login_required
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


@login_required
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


@login_required
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
