import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.db import transaction
from django.http import HttpResponseForbidden
from django_tables2 import RequestConfig
import jdatetime
from jdatetime import datetime as jdatetime_datetime

from core.logging_levels import *
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

from core.TransportFolder.TransportModel import Transport
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem

from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.PersonFolder.PersonModel import Person
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.StockEntryFolder.StockEntryModel import StockEntry
from core.StockEntryFolder.SourceStockModel import SourceStock
from core.StockEntryFolder.TargetStockModel import TargetStock
from core.StockEntryFolder.TargetStockModel import TargetStock
from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from supply.tables import TransportTable, WarehouseDeliveryTable
import django_tables2 as tables
from django.utils.html import format_html

User = get_user_model()


# ==================== Field Access Helper Functions ====================

def get_accessible_purchase_transport_fields(user):
    """Check field access for Transport model (view permission)"""
    return {
        'transport_number': user_can_access_field(user, Transport, 'transport_number', 'view'),
        'purchase_order': user_can_access_field(user, Transport, 'purchase_order', 'view'),
        'status': user_can_access_field(user, Transport, 'status', 'view'),
        'vehicle_type': user_can_access_field(user, Transport, 'vehicle_type', 'view'),
        'plate_number': user_can_access_field(user, Transport, 'plate_number', 'view'),
        'driver': user_can_access_field(user, Transport, 'driver', 'view'),
        'gross_weight': user_can_access_field(user, Transport, 'gross_weight', 'view'),
        'tare_weight': user_can_access_field(user, Transport, 'tare_weight', 'view'),
        'net_weight': user_can_access_field(user, Transport, 'net_weight', 'view'),
        'waybill_weight': user_can_access_field(user, Transport, 'waybill_weight', 'view'),
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'view'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'view'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'view'),
        'discount': user_can_access_field(user, Transport, 'discount', 'view'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'view'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'view'),
        'loading_date': user_can_access_field(user, Transport, 'loading_date', 'view'),
        'created_at': user_can_access_field(user, Transport, 'created_at', 'view'),
    }


def get_accessible_purchase_transport_fields_edit(user):
    """Check field access for Transport model (edit permission)"""
    return {
        'gross_weight': user_can_access_field(user, Transport, 'gross_weight', 'edit'),
        'tare_weight': user_can_access_field(user, Transport, 'tare_weight', 'edit'),
        'net_weight': user_can_access_field(user, Transport, 'net_weight', 'edit'),
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'edit'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'edit'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'edit'),
        'discount': user_can_access_field(user, Transport, 'discount', 'edit'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'edit'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'edit'),
        'loading_date': user_can_access_field(user, Transport, 'loading_date', 'edit'),
    }


def get_accessible_procurement_purchase_order_fields_for_warehouse(user):
    """Check field access for ProcurementPurchaseOrder model (for warehouse views)"""
    return {
        'order_number': user_can_access_field(user, Order, 'order_number', 'view'),
        'status': user_can_access_field(user, Order, 'status', 'view'),
        'supplier': user_can_access_field(user, Order, 'supplier', 'view'),
        'materials': user_can_access_field(user, Order, 'materials', 'view'),
        'created_at': user_can_access_field(user, Order, 'created_at', 'view'),
    }


def get_accessible_raw_material_fields_for_warehouse(user):
    """Check field access for RawMaterial model (for warehouse views)"""
    return {
        'name': user_can_access_field(user, RawMaterial, 'name', 'view'),
        'material_code': user_can_access_field(user, RawMaterial, 'material_code', 'view'),
        'unit': user_can_access_field(user, RawMaterial, 'unit', 'view'),
    }


def get_accessible_person_fields_for_warehouse(user):
    """Check field access for Person model (for warehouse views)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'phone_number': user_can_access_field(user, Person, 'phone_number', 'view'),
        'type': user_can_access_field(user, Person, 'type', 'view'),
    }


def get_accessible_po_material_fields_for_warehouse(user):
    """Check field access for OrderItem model (materials in purchase orders)"""
    # برای سوپریوزر، همه فیلدها قابل دسترسی هستند
    if user.is_superuser:
        return {
            'quantity': True,
            'unit': True,
            'raw_material': True,
        }
    
    return {
        'quantity': user_can_access_field(user, OrderItem, 'quantity', 'view'),
        'unit': user_can_access_field(user, OrderItem, 'weight_unit', 'view'),
        'raw_material': user_can_access_field(user, OrderItem, 'raw_material', 'view'),
    }

# ==================== End Field Access Helper Functions ====================


class WarehouseDeliveryForm(forms.Form):
    """فرم تحویل انبار - صفحه اطلاعات تخلیه"""
    # نوع کرایه
    freight_payment_type = forms.ChoiceField(
        label='نوع کرایه',
        choices=[('', 'انتخاب کنید')] + Transport.FREIGHT_PAYMENT_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_freight_payment_type'})
    )
    
    # کرایه اولیه
    initial_freight = forms.DecimalField(
        label='کرایه اولیه',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_initial_freight'})
    )
    
    # کرایه کل (read-only - محاسبه خودکار)
    total_freight = forms.DecimalField(
        label='کرایه کل',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True, 'id': 'id_total_freight'})
    )
    
    # تخفیف
    discount = forms.DecimalField(
        label='تخفیف',
        required=False,
        max_digits=15,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0', 'id': 'id_discount'})
    )
    
    # مازاد
    surplus = forms.DecimalField(
        label='مازاد',
        required=False,
        max_digits=15,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0', 'id': 'id_surplus'})
    )
    
    # کرایه پرداختی (read-only - محاسبه خودکار)
    freight_payment = forms.DecimalField(
        label='کرایه پرداختی',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True, 'id': 'id_freight_payment'})
    )
    
    # انبار مبدأ (انبار مجازی تامین‌کننده)
    source_warehouse = forms.ModelChoiceField(
        label='انبار مبدأ (تامین‌کننده)',
        queryset=Warehouse.objects.filter(warehouse_type='supplier'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='انبار مجازی تامین‌کننده که ماده اولیه از آنجا آمده است'
    )
    
    # انبار مقصد (انبار کارخانه) - اختیاری (چون هر مرحله انبار مقصد خودش را دارد)
    destination_warehouse = forms.ModelChoiceField(
        label='انبار مقصد پیش‌فرض (کارخانه)',
        queryset=Warehouse.objects.exclude(warehouse_type='supplier'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='انبار کارخانه پیش‌فرض (اختیاری - هر مرحله می‌تواند انبار مقصد جداگانه‌ای داشته باشد)'
    )
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        freight_payment_type = cleaned_data.get('freight_payment_type')
        
        bug_logger.debug(f"Form validation - freight_payment_type: {freight_payment_type}")
        
        # اگر نوع کرایه "محاسبه شده در فی" نباشد، فیلدهای کرایه باید پر شوند
        if freight_payment_type and freight_payment_type != 'calculated_in_invoice':
            initial_freight = cleaned_data.get('initial_freight')
            if not initial_freight or initial_freight <= 0:
                raise forms.ValidationError(
                    'برای نوع کرایه انتخاب شده، کرایه اولیه باید وارد شود.'
                )
            
            # محاسبه کرایه کل و کرایه پرداختی
            discount = cleaned_data.get('discount') or 0
            surplus = cleaned_data.get('surplus') or 0
            total_freight = initial_freight - discount + surplus
            cleaned_data['total_freight'] = total_freight
            cleaned_data['freight_payment'] = total_freight
        
        return cleaned_data


@login_required
def warehouse_delivery_list_view(request):
    """صفحه لیست حمل‌های در انتظار تخلیه - مخصوص انباردار"""
    audit_logger.info("مشاهده صفحه تحویل انبار")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه تحویل انبار بدون دسترسی")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_warehouse(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_warehouse(request.user)
    accessible_person_fields = get_accessible_person_fields_for_warehouse(request.user)
    accessible_po_material_fields = get_accessible_po_material_fields_for_warehouse(request.user)
    
    try:
        # حمل‌های در وضعیت های قابل تحویل انبار (awaiting_unloading for warehouseman)
        transports_unloading_qs = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_UNLOADING
        ).select_related('allocation__order', 'driver').order_by('-created_at')
        
        bug_logger.debug(f"Found {transports_unloading_qs.count()} transports awaiting unloading")
        
        # حمل‌های در انتظار تایید خروج توسط نگهبان (awaiting_wh_reconciliation)
        transports_guard_qs = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_WH_RECONCILIATION
        ).select_related('allocation__order', 'driver').order_by('-created_at')
        
        bug_logger.debug(f"Found {transports_guard_qs.count()} transports awaiting guard reconciliation")

        # Ensure transport_number is populated for all records
        transports_unloading = []
        for pt in transports_unloading_qs:
            if not pt.transport_number:
                try:
                    bug_logger.debug(f"Backfilling transport_number for transport pk={pt.pk}")
                    pt.save()
                except Exception as gen_err:
                    bug_logger.warning(f"Failed to backfill transport_number for transport pk={pt.pk}: {gen_err}")
            transports_unloading.append(pt)
        
        transports_guard = []
        for pt in transports_guard_qs:
            if not pt.transport_number:
                try:
                    bug_logger.debug(f"Backfilling transport_number for transport pk={pt.pk}")
                    pt.save()
                except Exception as gen_err:
                    bug_logger.warning(f"Failed to backfill transport_number for transport pk={pt.pk}: {gen_err}")
            transports_guard.append(pt)
        
        table_unloading = WarehouseDeliveryTable(transports_unloading, prefix='wh-', accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 20}).configure(table_unloading)
        
        from supply.tables import GuardExitTable
        table_guard = GuardExitTable(transports_guard, prefix='guard-', accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 20}).configure(table_guard)
        
        context = {
            'table': table_unloading,
            'guard_table': table_guard,
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        }
        return render(request, 'warehouse_delivery_list.html', context)
    except Exception as e:
        bug_logger.error(f"Warehouse delivery list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست تحویل انبار.')
        context = {
            'table': WarehouseDeliveryTable([], prefix='wh-'),
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        }
        return render(request, 'warehouse_delivery_list.html', context)


@login_required
def warehouse_delivery_detail_view(request, transport_number):
    """صفحه اطلاعات تخلیه - ثبت وزن‌ها و اطلاعات مالی (انباردار)"""
    audit_logger.info(f"دسترسی به صفحه تخلیه حمل {transport_number}")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
        audit_logger.activity(f"تلاش برای ثبت تخلیه بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به ثبت تخلیه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_edit(request.user)
    accessible_transport_fields_view = get_accessible_purchase_transport_fields(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_warehouse(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_warehouse(request.user)
    accessible_po_material_fields = get_accessible_po_material_fields_for_warehouse(request.user)
    
    # Support both transport_number and numeric pk as identifier
    try:
        if transport_number and str(transport_number).isdigit():
            bug_logger.debug(f"Fetching transport by pk: {transport_number}")
            pt = get_object_or_404(
                Transport.objects.select_related('driver', 'allocation', 'allocation__order'),
                pk=int(transport_number)
            )
        else:
            bug_logger.debug(f"Fetching transport by transport_number: {transport_number}")
            pt = get_object_or_404(
                Transport.objects.select_related('driver', 'allocation', 'allocation__order'),
                transport_number=transport_number
            )
        bug_logger.debug(f"Transport found - ID: {pt.pk}, Status: {pt.status}, Order: {pt.allocation.order.order_number if pt.allocation and pt.allocation.order else 'N/A'}")
    except Exception as e:
        bug_logger.error(f"Warehouse delivery detail fetch error for identifier={transport_number}: {e}")
        messages.error(request, 'شناسه حمل نامعتبر است یا یافت نشد.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    # Allow viewing in awaiting_unloading (for data entry) or awaiting_wh_reconciliation (read-only)
    if pt.status not in [Transport.STATUS_AWAITING_UNLOADING, Transport.STATUS_AWAITING_WH_RECONCILIATION]:
        audit_logger.activity(f"تلاش برای دسترسی به تخلیه با وضعیت نامعتبر - حمل {transport_number}: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل مشاهده نیست.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    # If awaiting guard reconciliation, show read-only
    if pt.status == Transport.STATUS_AWAITING_WH_RECONCILIATION:
        # Get order items for mixed material support
        # فقط مواد اولیه‌ای که در این حمل تخصیص یافته‌اند را نمایش می‌دهیم
        order_items = []
        if pt.allocation and pt.allocation.order:
            # Check for existing RawMaterialInfo records (if previously saved)
            existing_infos = RawMaterialInfo.objects.filter(transport=pt).select_related('order_item', 'raw_material', 'order_item__raw_material')
            
            for info in existing_infos:
                if info.order_item and info.order_item.raw_material:
                    order_items.append({
                        'item': info.order_item,
                        'raw_material': info.raw_material,
                        'allocated_quantity': info.allocated_quantity
                    })
        
        # Initialize form for display
        initial = {
            'freight_payment_type': pt.freight_payment_type,
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
        }
        form = WarehouseDeliveryForm(initial=initial)
        
        context = {
            'form': form,
            'pt': pt,
            'order_items': order_items,
            'read_only': True,
            'awaiting_guard': True,
            'accessible_transport_fields': accessible_transport_fields_view,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        }
        return render(request, 'warehouse_delivery_detail.html', context)
    
    if request.method == 'POST':
        form = WarehouseDeliveryForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            audit_logger.info(f"شروع ثبت تخلیه برای حمل {transport_number}")
            
            try:
                with transaction.atomic():
                    # دریافت وزن پر اولیه از فیلد جداگانه
                    gross = request.POST.get('initial_gross_weight')
                    source_warehouse = data.get('source_warehouse')
                    destination_warehouse = data.get('destination_warehouse')
                    
                    if not gross:
                        messages.error(request, 'وزن پر اولیه وارد نشده است.')
                        return redirect(request.path)
                    
                    try:
                        gross = float(gross)
                    except (ValueError, TypeError):
                        messages.error(request, 'وزن پر اولیه نامعتبر است.')
                        return redirect(request.path)
                    
                    if gross <= 0:
                        messages.error(request, 'وزن پر اولیه باید بزرگتر از صفر باشد.')
                        return redirect(request.path)
                    
                    # پردازش داده‌های مرحله‌ای تخلیه
                    # فرمت: unloading_stages[0][item_id]=X&unloading_stages[0][weight]=Y
                    po = pt.allocation.order if pt.allocation else None
                    items_qs = po.order_items.filter(raw_material__isnull=False).select_related('raw_material') if po else []
                    
                    # دریافت مراحل تخلیه از POST
                    unloading_stages = []
                    stage_index = 0
                    while True:
                        item_id_key = f'unloading_stages[{stage_index}][item_id]'
                        weight_key = f'unloading_stages[{stage_index}][weight]'
                        warehouse_id_key = f'unloading_stages[{stage_index}][warehouse_id]'
                        
                        item_id = request.POST.get(item_id_key)
                        weight = request.POST.get(weight_key)
                        warehouse_id = request.POST.get(warehouse_id_key)
                        
                        if not item_id or not weight or not warehouse_id:
                            break
                        
                        try:
                            item_id = int(item_id)
                            weight = float(weight)
                            warehouse_id = int(warehouse_id)
                            if weight > 0:
                                unloading_stages.append({
                                    'item_id': item_id,
                                    'weight': weight,
                                    'warehouse_id': warehouse_id
                                })
                        except (ValueError, TypeError):
                            pass
                        
                        stage_index += 1
                    
                    if not unloading_stages:
                        messages.error(request, 'حداقل یک مرحله تخلیه باید ثبت شود.')
                        return redirect(request.path)
                    
                    # محاسبه وزن‌های خالص هر محصول و وزن خالی نهایی
                    item_weights = {}
                    item_warehouses = {}  # نگهداری انبار مقصد برای هر ماده اولیه
                    current_weight = float(gross)
                    
                    for stage in unloading_stages:
                        item_id = stage['item_id']
                        weight_after_unloading = stage['weight']
                        warehouse_id = stage.get('warehouse_id')
                        
                        # وزن خالص این محصول = وزن قبلی - وزن بعد از تخلیه
                        net_item_weight = current_weight - weight_after_unloading
                        
                        if net_item_weight <= 0:
                            messages.error(request, f'وزن خالص محصول نامعتبر است. وزن بعد از تخلیه باید کمتر از وزن قبلی باشد.')
                            return redirect(request.path)
                        
                        # بررسی اینکه این محصول قبلاً تخلیه نشده باشد
                        if item_id in item_weights:
                            messages.error(request, 'هر محصول فقط یک بار می‌تواند تخلیه شود.')
                            return redirect(request.path)
                        
                        item_weights[item_id] = net_item_weight
                        if warehouse_id:
                            try:
                                warehouse = Warehouse.objects.get(pk=warehouse_id)
                                item_warehouses[item_id] = warehouse
                            except Warehouse.DoesNotExist:
                                messages.error(request, f'انبار مقصد برای محصول نامعتبر است.')
                                return redirect(request.path)
                        else:
                            messages.error(request, f'انبار مقصد برای محصول انتخاب نشده است.')
                            return redirect(request.path)
                        
                        current_weight = weight_after_unloading
                    
                    # وزن خالی نهایی = آخرین وزن ثبت شده
                    tare = current_weight
                    net_weight = float(gross) - float(tare)
                    
                    # بررسی اینکه همه محصولات تخلیه شده‌اند
                    if items_qs:
                        item_ids_in_stages = set(item_weights.keys())
                        item_ids_in_order = set(items_qs.values_list('id', flat=True))
                        
                        if item_ids_in_stages != item_ids_in_order:
                            missing = item_ids_in_order - item_ids_in_stages
                            messages.error(request, f'همه محصولات باید تخلیه شوند. محصولات باقیمانده: {missing}')
                            return redirect(request.path)
                    
                    bug_logger.debug(f"Saving sequential unloading data - Transport: {transport_number}, Gross: {gross}, Tare: {tare}, Net: {net_weight}, Stages: {len(unloading_stages)}, Source: {source_warehouse}, Destination: {destination_warehouse}")

                    # به‌روزرسانی فیلدهای حمل
                    pt.gross_weight = gross
                    pt.tare_weight = tare  # وزن خالی نهایی
                    pt.net_weight = net_weight
                    pt.freight_payment_type = data.get('freight_payment_type')
                    
                    # اگر نوع کرایه "محاسبه شده در فی" نباشد، فیلدهای کرایه را تنظیم کن
                    if data.get('freight_payment_type') != 'calculated_in_invoice':
                        pt.initial_freight = data.get('initial_freight') or 0
                        pt.discount = data.get('discount', 0) or 0
                        pt.surplus = data.get('surplus', 0) or 0
                        # محاسبه کرایه کل: کرایه اولیه - تخفیف + مازاد
                        pt.total_freight = (pt.initial_freight or 0) - (pt.discount or 0) + (pt.surplus or 0)
                        # کرایه پرداختی = کرایه کل
                        pt.freight_payment = pt.total_freight
                    else:
                        # اگر نوع کرایه "محاسبه شده در فی" باشد، فیلدهای کرایه را صفر کن
                        pt.initial_freight = None
                        pt.discount = None
                        pt.surplus = None
                        pt.total_freight = None
                        pt.freight_payment = None
                    
                    # ثبت تاریخ تخلیه
                    pt.loading_date = jdatetime.date.today()
                    
                    # اطمینان از اینکه direction تنظیم شده است (برای inbound)
                    if not pt.direction:
                        pt.direction = 'inbound'
                    
                    # ذخیره اولیه برای ثبت وزن‌ها
                    pt.save()
                    
                    # Save RawMaterialInfo records
                    valid_raw_material_infos = [] # To be used for StockEntry
                    if items_qs:
                        # دریافت allocated_quantity از RawMaterialInfo قبلی (اگر وجود دارد)
                        existing_infos = RawMaterialInfo.objects.filter(transport=pt)
                        allocated_map = {info.order_item_id: info.allocated_quantity for info in existing_infos}
                        
                        # Clear old ones to avoid duplicates if re-submitting
                        RawMaterialInfo.objects.filter(transport=pt).delete()
                        
                        for item in items_qs:
                            w = item_weights.get(item.id, 0)
                            if w > 0:
                                # استفاده از allocated_quantity قبلی (اگر وجود دارد)
                                # اگر وجود نداشت، از وزن خالص استفاده می‌کنیم (برای اولین بار)
                                allocated_qty = allocated_map.get(item.id, w)
                                
                                rmi = RawMaterialInfo.objects.create(
                                    transport=pt,
                                    order_item=item,
                                    raw_material=item.raw_material,
                                    allocated_quantity=allocated_qty,  # وزن تخصیص یافته قبلی (یا وزن خالص برای اولین بار)
                                    net_weight=w,  # وزن خالص محاسبه شده از تخلیه
                                    weight_unit='kg' # Unloading is usually in KG
                                )
                                valid_raw_material_infos.append(rmi)

                    bug_logger.info(f"اطلاعات تخلیه برای حمل {transport_number} ثبت شد - وزن خالص: {net_weight}")
                    
                    # ایجاد لاگ موجودیت: از انبار مبدأ (تامین‌کننده) به انبار مقصد (کارخانه)
                    # برای هر ماده اولیه، انبار مقصد جداگانه است
                    if source_warehouse and net_weight and net_weight > 0:
                        try:
                            if valid_raw_material_infos:
                                raw_material_content_type = ContentType.objects.get_for_model(RawMaterial)
                                
                                # برای هر ماده اولیه یک StockEntry جداگانه ایجاد می‌کنیم (چون انبار مقصد متفاوت است)
                                for rmi in valid_raw_material_infos:
                                    # دریافت انبار مقصد برای این ماده اولیه
                                    destination_warehouse_for_item = item_warehouses.get(rmi.order_item.id)
                                    
                                    if not destination_warehouse_for_item:
                                        bug_logger.warning(f"انبار مقصد برای ماده اولیه {rmi.raw_material.name} یافت نشد")
                                        continue
                                    
                                    # ایجاد StockEntry برای این ماده اولیه
                                    stock_entry = StockEntry.objects.create(
                                        transaction_date=jdatetime_datetime.now(),
                                        entry_type=StockEntry.StockEntryType.PURCHASE,
                                        notes=f"تخلیه حمل {transport_number} - {rmi.raw_material.name} - انتقال از انبار {source_warehouse.warehouse_id} به انبار {destination_warehouse_for_item.warehouse_id}",
                                        is_committed=False  # ابتدا commit نمی‌کنیم، بعد commit می‌کنیم
                                    )
                                    
                                    # ایجاد SourceStock (از انبار تامین‌کننده)
                                    SourceStock.objects.create(
                                        stock_entry=stock_entry,
                                        from_content_type=raw_material_content_type,
                                        from_object_id=rmi.raw_material.pk,
                                        from_warehouse=source_warehouse,
                                        quantity=rmi.allocated_quantity
                                    )
                                    
                                    # ایجاد TargetStock (به انبار کارخانه - انبار مقصد مربوط به این ماده اولیه)
                                    TargetStock.objects.create(
                                        stock_entry=stock_entry,
                                        to_content_type=raw_material_content_type,
                                        to_object_id=rmi.raw_material.pk,
                                        to_warehouse=destination_warehouse_for_item,
                                        quantity=rmi.allocated_quantity
                                    )
                                    
                                    # Commit کردن StockEntry برای به‌روزرسانی موجودیت‌ها
                                    stock_entry.commit()
                                    
                                    bug_logger.info(
                                        f"لاگ موجودیت ایجاد شد - "
                                        f"StockEntry ID: {stock_entry.pk}, "
                                        f"ماده اولیه: {rmi.raw_material.name}, "
                                        f"از انبار: {source_warehouse.warehouse_id}, "
                                        f"به انبار: {destination_warehouse_for_item.warehouse_id}, "
                                        f"مقدار: {rmi.allocated_quantity} کیلوگرم"
                                    )
                                
                                # لاگ کلی برای audit
                                warehouses_list = ', '.join([wh.warehouse_id for wh in set(item_warehouses.values())])
                                audit_logger.info(
                                    f"لاگ موجودیت برای تخلیه - "
                                    f"حمل: {transport_number}, "
                                    f"از انبار: {source_warehouse.warehouse_id}, "
                                    f"به انبارها: {warehouses_list}, "
                                    f"مقدار کل: {net_weight} کیلوگرم, "
                                    f"کاربر: {request.user.username}"
                                )
                            else:
                                bug_logger.warning(f"ماده اولیه‌ای برای ثبت موجودیت یافت نشد (Transport: {transport_number})")

                        except Exception as inv_err:
                            bug_logger.error(f"خطا در ایجاد لاگ موجودیت برای حمل {transport_number}: {inv_err}", exc_info=True)
                            # خطا را لاگ می‌کنیم اما فرآیند را متوقف نمی‌کنیم
                            messages.warning(request, f'اطلاعات تخلیه ثبت شد اما خطا در ایجاد لاگ موجودیت: {str(inv_err)}')
                    
                    # تغییر وضعیت حمل به "در انتظار تطبیق انبار"
                    pt.status = Transport.STATUS_AWAITING_WH_RECONCILIATION
                    pt.save()
                    bug_logger.info(f"وضعیت حمل {transport_number} به 'در انتظار تطبیق انبار' تغییر یافت")
                    
                    # تغییر وضعیت سفارش از "در انتظار تحویل بار" به "در انتظار تطبیق اطلاعات انبار"
                    po = pt.allocation.order if pt.allocation else None
                    if po and po.status == Order.STATUS_AWAITING_DELIVERY:
                        po.transition(Order.STATUS_AWAITING_WAREHOUSE_RECONCILIATION, user=request.user, note=f"تخلیه برای حمل {transport_number} تکمیل شد و در انتظار تطبیق اطلاعات انبار است.")
                        bug_logger.info(f"وضعیت سفارش {po.order_number} به 'در انتظار تطبیق اطلاعات انبار' تغییر یافت")
                    
                    # ثبت در Audit Trail
                    audit_logger.info(
                        f"تخلیه تکمیل شد - "
                        f"حمل: {transport_number} - "
                        f"سفارش: {pt.allocation.order.order_number if pt.allocation and pt.allocation.order else 'N/A'} - "
                        f"وزن پر: {gross} - "
                        f"وزن خالی: {tare} - "
                        f"وزن خالص: {net_weight} - "
                        f"انبار مبدأ: {source_warehouse.warehouse_id if source_warehouse else 'N/A'} - "
                        f"انبار مقصد: {destination_warehouse.warehouse_id if destination_warehouse else 'N/A'} - "
                        f"کاربر: {request.user.username} - "
                        f"کرایه پرداختی: {data.get('freight_payment')}"
                    )
                    
                messages.success(request, f'اطلاعات تخلیه ثبت شد. وزن خالص: {net_weight} - حمل به مرحله تطبیق انبار منتقل شد.')
                return redirect(reverse('supply:warehouse_delivery'))
            except Exception as e:
                bug_logger.error(f"خطا در ثبت تخلیه برای حمل {transport_number}: {e}")
                messages.error(request, f'خطا در ثبت اطلاعات تخلیه: {str(e)}')
        else:
            bug_logger.warning(f"فرم ثبت تخلیه نامعتبر برای حمل {transport_number}: {form.errors}")
            audit_logger.activity(f"فرم نامعتبر برای ثبت تخلیه حمل {transport_number}")
    else:
        # مقداردهی اولیه فرم
        initial = {
            'freight_payment_type': pt.freight_payment_type,
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
        }
        form = WarehouseDeliveryForm(initial=initial)
        
    # Prepare order items for context (for both new POST with errors and GET)
    # فقط مواد اولیه‌ای که در این حمل تخصیص یافته‌اند را نمایش می‌دهیم
    order_items = []
    if pt.allocation and pt.allocation.order:
        existing_infos = RawMaterialInfo.objects.filter(transport=pt).select_related('order_item', 'raw_material', 'order_item__raw_material')
        
        for info in existing_infos:
            if info.order_item and info.order_item.raw_material:
                order_items.append({
                    'item': info.order_item,
                    'raw_material': info.raw_material,
                    'allocated_quantity': info.allocated_quantity
                })
    
    # لیست انبارهای مقصد (غیر از تامین‌کننده) برای انتخاب در هر مرحله
    destination_warehouses = Warehouse.objects.exclude(warehouse_type='supplier')
    
    context = {
        'form': form,
        'pt': pt,
        'order_items': order_items,
        'read_only': False,
        'awaiting_guard': False,
        'destination_warehouses': destination_warehouses,
        'accessible_transport_fields': accessible_transport_fields_view,
        'accessible_po_fields': accessible_po_fields,
        'accessible_raw_material_fields': accessible_raw_material_fields,
        'accessible_po_material_fields': accessible_po_material_fields,
    }
    return render(request, 'warehouse_delivery_detail.html', context)


@login_required  
def guard_vehicle_exit_view(request, transport_number):
    """صفحه تایید خروج خودرو توسط نگهبان"""
    audit_logger.info(f"دسترسی نگهبان به صفحه خروج خودرو - حمل {transport_number}")
    
    # Check guard permission - using SUPPLY_REGISTER_VEHICLE_EXIT which is the existing guard permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_VEHICLE_EXIT.value):
        audit_logger.activity(f"تلاش برای تایید خروج خودرو بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به تایید خروج خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions for view
    accessible_transport_fields = get_accessible_purchase_transport_fields(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_warehouse(request.user)
    
    # Get transport
    try:
        if transport_number and str(transport_number).isdigit():
            bug_logger.debug(f"Guard fetching transport by pk: {transport_number}")
            pt = get_object_or_404(Transport, pk=int(transport_number))
        else:
            bug_logger.debug(f"Guard fetching transport by transport_number: {transport_number}")
            pt = get_object_or_404(Transport, transport_number=transport_number)
        bug_logger.debug(f"Guard access - Transport: {pt.pk}, Status: {pt.status}, Net weight: {pt.net_weight}")
    except Exception as e:
        bug_logger.error(f"Guard exit fetch error for identifier={transport_number}: {e}")
        messages.error(request, 'شناسه حمل نامعتبر است یا یافت نشد.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    # Check status - must be awaiting_wh_reconciliation (warehouseman completed)
    if pt.status != Transport.STATUS_AWAITING_WH_RECONCILIATION:
        audit_logger.activity(f"تلاش برای خروج خودرو با وضعیت نامعتبر - حمل {transport_number}: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل خروج نیست. ابتدا باید اطلاعات تخلیه توسط انباردار تکمیل شود.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    if request.method == 'POST':
        # Confirm vehicle exit
        bug_logger.debug(f"Guard confirming vehicle exit for transport {transport_number}")
        try:
            with transaction.atomic():
                # تغییر وضعیت حمل به "در انتظار تسویه"
                bug_logger.debug(f"Changing transport {transport_number} status to awaiting_settlement")
                pt.status = Transport.STATUS_AWAITING_SETTLEMENT
                pt.delivery_date = jdatetime.date.today()
                pt.save()
                
                # تغییر وضعیت سفارش از "در انتظار تطبیق اطلاعات انبار" به "در انتظار تسویه نهایی"
                po = pt.allocation.order if pt.allocation else None
                if po and po.status == Order.STATUS_AWAITING_WAREHOUSE_RECONCILIATION:
                    # بعد از تایید خروج خودرو توسط نگهبان، سفارش به مرحله تسویه نهایی می‌رود
                    po.transition(Order.STATUS_AWAITING_FINAL_SETTLEMENT, user=request.user, note=f"خروج خودرو برای حمل {transport_number} تایید شد و سفارش به مرحله تسویه نهایی منتقل شد.")
                    bug_logger.info(f"وضعیت سفارش {po.order_number} به 'در انتظار تسویه نهایی' تغییر یافت")
                
                audit_logger.info(
                    f"خروج خودرو تایید شد - "
                    f"حمل: {transport_number} - "
                    f"سفارش: {pt.allocation.order.order_number if pt.allocation and pt.allocation.order else 'N/A'} - "
                    f"نگهبان: {request.user.username} - "
                    f"وزن خالص: {pt.net_weight}"
                )
                
            messages.success(request, f'خروج خودرو تایید شد. حمل {transport_number} به مرحله تسویه منتقل شد.')
            return redirect(reverse('supply:warehouse_delivery'))
        except Exception as e:
            bug_logger.error(f"خطا در تایید خروج خودرو برای حمل {transport_number}: {e}")
            messages.error(request, f'خطا در تایید خروج خودرو: {str(e)}')
    
    context = {
        'pt': pt,
        'accessible_transport_fields': accessible_transport_fields,
        'accessible_po_fields': accessible_po_fields,
    }
    return render(request, 'car_exit_custodian_confirmation.html', context)
