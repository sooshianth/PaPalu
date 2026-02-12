import logging
from decimal import Decimal
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
from django.utils import timezone

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


def _carexit_secondary_context(pt):
    """اطلاعات واحد ثانویه برای خروج خودرو - وقتی خرید با واحد ثانویه بوده"""
    res = {'purchase_in_secondary': False, 'net_weight_secondary': None, 'secondary_unit_display': ''}
    if not (pt.allocation and pt.allocation.order):
        return res
    for oi in pt.allocation.order.order_items.select_related('raw_material').filter(raw_material__isnull=False):
        if oi.is_purchased_in_secondary_unit():
            res['purchase_in_secondary'] = True
            res['secondary_unit_display'] = oi.get_weight_unit_display()
            if pt.net_weight and oi.raw_material and oi.raw_material.conversion_factor:
                res['net_weight_secondary'] = oi.kg_to_order_unit(float(pt.net_weight))
            break
    return res


def _guard_exit_delivery_items(pt):
    """
    برای صفحه تایید خروج خودرو: لیست تحویل به تفکیک جنس.
    هر آیتم: نام ماده، وزن خالص (کیلوگرم)، و در صورت خرید با واحد ثانویه مقدار در واحد ثانویه.
    """
    items = []
    for rmi in pt.raw_material_infos.select_related('raw_material', 'order_item').all():
        name = (rmi.raw_material.name if rmi.raw_material else None) or '—'
        net_kg = rmi.net_weight
        secondary_value = None
        secondary_unit_display = ''
        if net_kg is not None and rmi.order_item and rmi.order_item.is_purchased_in_secondary_unit():
            try:
                secondary_value = rmi.order_item.kg_to_order_unit(float(net_kg))
                secondary_unit_display = rmi.order_item.get_weight_unit_display() or ''
            except (TypeError, ValueError, ZeroDivisionError):
                pass
        items.append({
            'name': name,
            'net_kg': net_kg,
            'secondary_value': secondary_value,
            'secondary_unit_display': secondary_unit_display,
        })
    return items


def _comparison_totals_from_order_items(order_items):
    """محاسبه جمع کل تخصیص، وزن خالص محاسبه‌شده و اختلاف برای جدول مقایسه وزن‌ها"""
    total_allocated = sum((item.get('allocated_quantity') or Decimal('0')) for item in order_items)
    total_calculated = sum((item.get('calculated_net_weight') or Decimal('0')) for item in order_items)
    return {
        'total_allocated': total_allocated,
        'total_calculated': total_calculated,
        'total_diff': total_calculated - total_allocated,
    }


def _initial_stages_from_order_items(pt, order_items):
    """
    برای نمایش مراحل تخلیه و خلاصه وزن‌ها وقتی داده قبلاً ذخیره شده است.
    از gross، tare و وزن خالص هر ماده، وزن بعد از هر مرحله را بازسازی می‌کند.
    خروجی لیست دیکت‌های قابل JSON برای استفاده در فرانت‌اند.
    """
    if not order_items or not getattr(pt, 'gross_weight', None) or not getattr(pt, 'tare_weight', None):
        return []
    gross = float(pt.gross_weight)
    cum = 0.0
    out = []
    for i, item_data in enumerate(order_items):
        net = item_data.get('calculated_net_weight')
        if net is None:
            continue
        net_f = float(net)
        if net_f <= 0:
            continue
        weight_after = gross - cum - net_f
        cum += net_f
        wh_id = item_data.get('destination_warehouse_id')
        out.append({
            'id': i + 1,
            'item_id': item_data['item'].id,
            'net_weight': round(net_f, 6),
            'weight_after': round(weight_after, 6),
            'warehouse_id': int(wh_id) if wh_id else None,
        })
    return out


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
    # نوع کرایه (readonly - از سفارش خرید گرفته می‌شود)
    freight_payment_type = forms.ChoiceField(
        label='نوع کرایه',
        choices=[('', 'انتخاب کنید')] + Transport.FREIGHT_PAYMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control', 
            'id': 'id_freight_payment_type',
            'readonly': True,
            'disabled': True,
            'style': 'background-color: #f5f5f5; cursor: not-allowed;'
        })
    )
    
    # کرایه اولیه
    initial_freight = forms.DecimalField(
        label='کرایه اولیه (ریال)',
        required=False,
        max_digits=15,
        decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'id': 'id_initial_freight'})
    )
    
    # کرایه کل (read-only - محاسبه خودکار)
    total_freight = forms.DecimalField(
        label='کرایه کل (ریال)',
        required=False,
        max_digits=15,
        decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'readonly': True, 'id': 'id_total_freight'})
    )
    
    # تخفیف
    discount = forms.DecimalField(
        label='تخفیف (ریال)',
        required=False,
        max_digits=15,
        decimal_places=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'value': '0', 'id': 'id_discount'})
    )
    
    # مازاد
    surplus = forms.DecimalField(
        label='مازاد (ریال)',
        required=False,
        max_digits=15,
        decimal_places=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'value': '0', 'id': 'id_surplus'})
    )
    
    # کرایه پرداختی (read-only - محاسبه خودکار)
    freight_payment = forms.DecimalField(
        label='کرایه پرداختی (ریال)',
        required=False,
        max_digits=15,
        decimal_places=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'readonly': True, 'id': 'id_freight_payment'})
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
    
    def __init__(self, *args, transport=None, **kwargs):
        """Initialize form with transport to get freight_payment_type"""
        super().__init__(*args, **kwargs)
        self.transport = transport
        
        # دریافت انبار تأمین‌کننده
        supplier_warehouse = None
        if self.transport and self.transport.allocation and self.transport.allocation.order:
            supplier = self.transport.allocation.order.customer
            if supplier and supplier.warehouse:
                supplier_warehouse = supplier.warehouse
        
        # اگر تأمین‌کننده انبار دارد، فیلد را readonly کن و مقدار را تنظیم کن
        if supplier_warehouse:
            # غیرفعال کردن required چون خودمان مقدار را تنظیم می‌کنیم
            self.fields['source_warehouse'].required = False
            # تنظیم مقدار اولیه
            if 'source_warehouse' not in self.initial:
                self.initial['source_warehouse'] = supplier_warehouse
            # محدود کردن queryset به فقط انبار تأمین‌کننده
            self.fields['source_warehouse'].queryset = Warehouse.objects.filter(pk=supplier_warehouse.pk)
            # استفاده از disabled (مقدار در clean تنظیم می‌شود)
            self.fields['source_warehouse'].widget.attrs['disabled'] = True
            self.fields['source_warehouse'].widget.attrs['style'] = 'background-color: #f5f5f5; cursor: not-allowed;'
            # تغییر label برای نشان دادن اینکه فقط خواندنی است
            self.fields['source_warehouse'].label = 'انبار مبدأ (تأمین‌کننده)'
            # ذخیره انبار تأمین‌کننده برای استفاده در clean
            self._supplier_warehouse = supplier_warehouse
        else:
            # اگر انبار ندارد، فقط انبارهای supplier را نمایش بده
            self.fields['source_warehouse'].queryset = Warehouse.objects.filter(warehouse_type='supplier')
            self.fields['source_warehouse'].label = 'انتخاب انبار مبدأ (تأمین‌کننده)'
            self._supplier_warehouse = None
        
        # دریافت freight_payment_type برای تعیین required بودن فیلدهای کرایه
        freight_payment_type = None
        
        # اول از transport بگیر
        if self.transport:
            if self.transport.allocation and self.transport.allocation.order and self.transport.allocation.order.freight_payment_type:
                freight_payment_type = self.transport.allocation.order.freight_payment_type
            elif self.transport.freight_payment_type:
                freight_payment_type = self.transport.freight_payment_type
        
        # اگر از transport پیدا نشد، از initial بگیر
        if not freight_payment_type and 'freight_payment_type' in self.initial:
            freight_payment_type = self.initial.get('freight_payment_type')
        
        # اگر نوع کرایه "محاسبه شده در فی" نباشد، فیلدهای کرایه اجباری هستند
        if freight_payment_type and freight_payment_type != 'calculated_in_invoice':
            self.fields['initial_freight'].required = True
            # اضافه کردن ستاره قرمز به label
            original_label = self.fields['initial_freight'].label
            if original_label and '*' not in str(original_label):
                self.fields['initial_freight'].label = format_html('{} <span style="color: red;">*</span>', original_label)
            
            # discount و surplus می‌توانند 0 باشند (در initial هم 0 است)
            # اما باید مقدار داشته باشند (حتی 0)
            self.fields['discount'].required = True
            original_discount_label = self.fields['discount'].label
            if original_discount_label and '*' not in str(original_discount_label):
                self.fields['discount'].label = format_html('{} <span style="color: red;">*</span>', original_discount_label)
            
            self.fields['surplus'].required = True
            original_surplus_label = self.fields['surplus'].label
            if original_surplus_label and '*' not in str(original_surplus_label):
                self.fields['surplus'].label = format_html('{} <span style="color: red;">*</span>', original_surplus_label)
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        
        # دریافت source_warehouse از انبار تأمین‌کننده اگر disabled است
        source_warehouse = cleaned_data.get('source_warehouse')
        if not source_warehouse:
            # اگر فیلد disabled است (یعنی تأمین‌کننده انبار دارد)، از انبار تأمین‌کننده بگیر
            if hasattr(self, '_supplier_warehouse') and self._supplier_warehouse:
                source_warehouse = self._supplier_warehouse
                cleaned_data['source_warehouse'] = source_warehouse
            elif self.transport and self.transport.allocation and self.transport.allocation.order:
                supplier = self.transport.allocation.order.customer
                if supplier and supplier.warehouse:
                    source_warehouse = supplier.warehouse
                    cleaned_data['source_warehouse'] = source_warehouse
        
        # بررسی اینکه source_warehouse حتماً وجود داشته باشد
        if not source_warehouse:
            self.add_error('source_warehouse', 'انبار مبدأ باید انتخاب شود.')
        
        # دریافت freight_payment_type از transport (چون فیلد disabled است و در cleaned_data نیست)
        freight_payment_type = cleaned_data.get('freight_payment_type')
        if not freight_payment_type and self.transport:
            # از سفارش خرید بگیر
            if self.transport.allocation and self.transport.allocation.order and self.transport.allocation.order.freight_payment_type:
                freight_payment_type = self.transport.allocation.order.freight_payment_type
            elif self.transport.freight_payment_type:
                freight_payment_type = self.transport.freight_payment_type
        
        # اضافه کردن به cleaned_data برای استفاده در view
        if freight_payment_type:
            cleaned_data['freight_payment_type'] = freight_payment_type
        
        bug_logger.debug(f"Form validation - freight_payment_type: {freight_payment_type}")
        
        # اگر نوع کرایه "محاسبه شده در فی" نباشد، فیلدهای کرایه باید پر شوند
        if freight_payment_type and freight_payment_type != 'calculated_in_invoice':
            initial_freight = cleaned_data.get('initial_freight')
            discount = cleaned_data.get('discount')
            surplus = cleaned_data.get('surplus')
            
            # بررسی اجباری بودن فیلدها
            if not initial_freight or initial_freight <= 0:
                self.add_error('initial_freight', 'کرایه اولیه الزامی است و باید بیشتر از صفر باشد.')
            
            # discount و surplus باید مقدار داشته باشند (حتی 0)
            if discount is None:
                self.add_error('discount', 'این فیلد الزامی است. در صورت عدم تخفیف، مقدار 0 وارد کنید.')
            
            if surplus is None:
                self.add_error('surplus', 'این فیلد الزامی است. در صورت عدم مازاد، مقدار 0 وارد کنید.')
            
            # اگر خطایی وجود دارد، ادامه نده
            if self.errors:
                return cleaned_data
            
            # محاسبه کرایه کل و کرایه پرداختی
            discount = discount or 0
            surplus = surplus or 0
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
        # حمل‌های در وضعیت های قابل تحویل انبار (awaiting_unloading for warehouseman) - بدون ارجاع‌شده به مدیر
        transports_unloading_qs = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_UNLOADING,
            warehouse_delivery_referred_to_manager=False
        ).select_related('allocation__order', 'driver').order_by('-created_at')
        
        bug_logger.debug(f"Found {transports_unloading_qs.count()} transports awaiting unloading")
        
        # حمل‌های در انتظار تایید خروج توسط نگهبان - بدون ارجاع‌شده به مدیر (تحویل انبار یا خروج خودرو)
        transports_guard_qs = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_WH_RECONCILIATION,
            carexit_referred_to_manager=False,
            warehouse_delivery_referred_to_manager=False
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
        if user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
            table_unloading = WarehouseDeliveryTable(transports_unloading, prefix='wh-', accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 20}).configure(table_unloading)
        
        from supply.tables import GuardExitTable
        if user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_VEHICLE_EXIT.value):
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
        if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
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

    # اگر تحویل انبار به مدیر ارجاع شده، فقط سوپرادمین می‌تواند وارد شود
    if getattr(pt, 'warehouse_delivery_referred_to_manager', False) and not request.user.is_superuser:
        audit_logger.activity(f"تلاش برای دسترسی به تحویل انبار ارجاع‌شده به مدیر - حمل {transport_number}")
        messages.error(request, 'این مورد به مدیر ارجاع شده و فقط مدیر می‌تواند آن را مشاهده و حل کند.')
        return HttpResponseForbidden('دسترسی غیرمجاز. این مورد به مدیر ارجاع شده است.')
    
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
                    net = info.net_weight or Decimal('0')
                    alloc = info.allocated_quantity or Decimal('0')
                    order_items.append({
                        'item': info.order_item,
                        'raw_material': info.raw_material,
                        'allocated_quantity': info.allocated_quantity,
                        'calculated_net_weight': info.net_weight,
                        'weight_diff': (net - alloc) if info.net_weight is not None else None,
                        'destination_warehouse_id': getattr(info, 'destination_warehouse_id', None),
                    })
        
        comparison_totals = _comparison_totals_from_order_items(order_items)
        initial_stages = _initial_stages_from_order_items(pt, order_items)
        # Initialize form for display
        # نوع کرایه از سفارش خرید گرفته می‌شود (نه از transport)
        freight_payment_type = None
        if pt.allocation and pt.allocation.order and pt.allocation.order.freight_payment_type:
            freight_payment_type = pt.allocation.order.freight_payment_type
        elif pt.freight_payment_type:
            freight_payment_type = pt.freight_payment_type
        
        initial = {
            'freight_payment_type': freight_payment_type,
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
        }
        form = WarehouseDeliveryForm(initial=initial, transport=pt)
        
        context = {
            'form': form,
            'pt': pt,
            'order_items': order_items,
            'comparison_totals': comparison_totals,
            'initial_stages': initial_stages,
            'read_only': True,
            'awaiting_guard': True,
            'accessible_transport_fields': accessible_transport_fields_view,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
            'is_warehouse_delivery_referred': getattr(pt, 'warehouse_delivery_referred_to_manager', False),
            'show_refer_button': False,
            'warehouse_delivery_referral_reason': getattr(pt, 'warehouse_delivery_referral_reason', '') or '',
        }
        return render(request, 'warehouse_delivery_detail.html', context)
    
    if request.method == 'POST':
        is_refer_to_manager = request.POST.get('refer_to_manager') == '1'
        wh_referral_reason = (request.POST.get('warehouse_delivery_referral_reason') or '').strip()
        form = WarehouseDeliveryForm(request.POST, transport=pt)
        if form.is_valid():
            if is_refer_to_manager and not wh_referral_reason:
                messages.error(request, 'لطفاً دلیل ارجاع به مدیر را وارد کنید.')
                destination_warehouses = Warehouse.objects.filter(warehouse_type='primary')
                order_items = []
                if pt.allocation and pt.allocation.order:
                    existing_infos = RawMaterialInfo.objects.filter(transport=pt).select_related('order_item', 'raw_material', 'order_item__raw_material')
                    for info in existing_infos:
                        if info.order_item and info.order_item.raw_material:
                            net = info.net_weight or Decimal('0')
                            alloc = info.allocated_quantity or Decimal('0')
                            order_items.append({
                                'item': info.order_item, 'raw_material': info.raw_material, 'allocated_quantity': info.allocated_quantity,
                                'calculated_net_weight': info.net_weight, 'weight_diff': (net - alloc) if info.net_weight is not None else None,
                                'destination_warehouse_id': getattr(info, 'destination_warehouse_id', None),
                            })
                comparison_totals = _comparison_totals_from_order_items(order_items)
                initial_stages = _initial_stages_from_order_items(pt, order_items)
                context = {
                    'form': form, 'pt': pt, 'order_items': order_items, 'comparison_totals': comparison_totals,
                    'initial_stages': initial_stages,
                    'read_only': False, 'awaiting_guard': False,
                    'destination_warehouses': destination_warehouses,
                    'accessible_transport_fields': accessible_transport_fields_view,
                    'accessible_po_fields': accessible_po_fields,
                    'accessible_raw_material_fields': accessible_raw_material_fields,
                    'accessible_po_material_fields': accessible_po_material_fields,
                    'is_warehouse_delivery_referred': getattr(pt, 'warehouse_delivery_referred_to_manager', False),
                    'show_refer_button': not getattr(pt, 'warehouse_delivery_referred_to_manager', False) and not request.user.is_superuser,
                    'refer_modal_open': True,
                    'warehouse_delivery_referral_reason': getattr(pt, 'warehouse_delivery_referral_reason', '') or '',
                }
                return render(request, 'warehouse_delivery_detail.html', context)
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
                        gross = Decimal(str(gross))
                    except (ValueError, TypeError):
                        messages.error(request, 'وزن پر اولیه نامعتبر است.')
                        return redirect(request.path)
                    
                    if gross <= 0:
                        messages.error(request, 'وزن پر اولیه باید بزرگتر از صفر باشد.')
                        return redirect(request.path)
                    
                    # پردازش داده‌های مرحله‌ای تخلیه
                    # فرمت: unloading_stages[0][item_id]=X&unloading_stages[0][weight]=Y
                    # فقط order_items مربوط به این حمل (که در RawMaterialInfo ثبت شده‌اند) را بررسی می‌کنیم
                    po = pt.allocation.order if pt.allocation else None
                    existing_infos = RawMaterialInfo.objects.filter(transport=pt).select_related('order_item', 'raw_material')
                    
                    # اگر RawMaterialInfo وجود دارد، از آن استفاده می‌کنیم، وگرنه از order_items سفارش
                    if existing_infos.exists():
                        items_qs = [info.order_item for info in existing_infos if info.order_item and info.order_item.raw_material]
                    else:
                        # اولین بار - از order_items سفارش استفاده می‌کنیم
                        items_qs = list(po.order_items.filter(raw_material__isnull=False).select_related('raw_material')) if po else []
                    
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
                            weight = Decimal(str(weight))
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
                    
                    # بررسی و لاگ مقایسه وزن پر بارنامه با وزن پر باسکول
                    if pt.waybill_gross_weight and gross:
                        waybill_gross = Decimal(str(pt.waybill_gross_weight))
                        scale_gross = gross
                        if waybill_gross > 0:
                            weight_diff = abs(scale_gross - waybill_gross)
                            if weight_diff > 1000:
                                audit_logger.activity(
                                    f"اختلاف مشکوک وزن پر - حمل: {transport_number} | "
                                    f"وزن پر بارنامه: {waybill_gross} kg | "
                                    f"وزن پر باسکول: {scale_gross} kg | "
                                    f"اختلاف: {weight_diff:.0f} kg | "
                                    f"کاربر: {request.user.username}"
                                )
                                bug_logger.warning(
                                    f"اختلاف مشکوک وزن پر در حمل {transport_number}: "
                                    f"بارنامه={waybill_gross}kg, باسکول={scale_gross}kg, "
                                    f"اختلاف={weight_diff:.0f}kg"
                                )
                            elif weight_diff > 300:
                                bug_logger.info(
                                    f"اختلاف وزن پر در حمل {transport_number}: "
                                    f"بارنامه={waybill_gross}kg, باسکول={scale_gross}kg, "
                                    f"اختلاف={weight_diff:.0f}kg"
                                )
                    
                    # محاسبه وزن‌های خالص هر محصول و وزن خالی نهایی
                    item_weights = {}
                    item_warehouses = {}
                    current_weight = gross
                    
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
                    
                    tare = current_weight
                    net_weight = gross - tare
                    
                    # بررسی اینکه همه محصولات تخلیه شده‌اند
                    if items_qs:
                        item_ids_in_stages = set(item_weights.keys())
                        item_ids_in_order = set([item.id for item in items_qs])
                        
                        if item_ids_in_stages != item_ids_in_order:
                            missing = item_ids_in_order - item_ids_in_stages
                            messages.error(request, f'همه محصولات باید تخلیه شوند. محصولات باقیمانده: {missing}')
                            return redirect(request.path)
                    
                    bug_logger.debug(f"Saving sequential unloading data - Transport: {transport_number}, Gross: {gross}, Tare: {tare}, Net: {net_weight}, Stages: {len(unloading_stages)}, Source: {source_warehouse}, Destination: {destination_warehouse}")

                    # به‌روزرسانی فیلدهای حمل
                    pt.gross_weight = gross
                    pt.tare_weight = tare  # وزن خالی نهایی
                    pt.net_weight = net_weight
                    
                    # نوع کرایه از سفارش خرید گرفته می‌شود (نه از فرم)
                    if pt.allocation and pt.allocation.order and pt.allocation.order.freight_payment_type:
                        pt.freight_payment_type = pt.allocation.order.freight_payment_type
                    elif data.get('freight_payment_type'):
                        # Fallback: اگر در سفارش نبود، از فرم بگیر (برای سازگاری با داده‌های قدیمی)
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
                                dest_warehouse = item_warehouses.get(item.id)
                                rmi = RawMaterialInfo.objects.create(
                                    transport=pt,
                                    order_item=item,
                                    raw_material=item.raw_material,
                                    allocated_quantity=allocated_qty,  # وزن تخصیص یافته قبلی (یا وزن خالص برای اولین بار)
                                    net_weight=w,  # وزن خالص محاسبه شده از تخلیه
                                    destination_warehouse=dest_warehouse,  # انبار مقصد این مرحله تخلیه
                                    weight_unit='kg' # Unloading is usually in KG
                                )
                                valid_raw_material_infos.append(rmi)

                    bug_logger.info(f"اطلاعات تخلیه برای حمل {transport_number} ثبت شد - وزن خالص: {net_weight}")
                    
                    # ایجاد لاگ موجودیت: از انبار مبدأ (تامین‌کننده) به انبار مقصد (کارخانه)
                    # از تامین‌کننده به اندازه وزن بارنامه کم می‌شود، به انبار کارخانه به اندازه وزن خالص باسکول اضافه می‌شود (تفاوت ممکن است سرک یا کسری باشد)
                    if source_warehouse and net_weight and net_weight > 0:
                        try:
                            if valid_raw_material_infos:
                                raw_material_content_type = ContentType.objects.get_for_model(RawMaterial)
                                total_allocated = sum((rmi.allocated_quantity or Decimal('0')) for rmi in valid_raw_material_infos)
                                waybill_total = (pt.waybill_weight or Decimal('0'))
                                
                                # برای هر ماده اولیه یک StockEntry جداگانه ایجاد می‌کنیم (چون انبار مقصد متفاوت است)
                                for rmi in valid_raw_material_infos:
                                    # دریافت انبار مقصد برای این ماده اولیه
                                    destination_warehouse_for_item = item_warehouses.get(rmi.order_item.id)
                                    
                                    if not destination_warehouse_for_item:
                                        bug_logger.warning(f"انبار مقصد برای ماده اولیه {rmi.raw_material.name} یافت نشد")
                                        continue
                                    
                                    # مقدار اضافه‌شده به انبار کارخانه = وزن خالص باسکول
                                    scale_net_weight = rmi.net_weight
                                    if not scale_net_weight or scale_net_weight <= 0:
                                        bug_logger.warning(
                                            f"رد شد: ماده اولیه {rmi.raw_material.name} - وزن خالص باسکول نامعتبر (net_weight={rmi.net_weight}). به انبار اضافه نمی‌شود."
                                        )
                                        continue
                                    
                                    # مقدار کم‌شده از تامین‌کننده = سهم این ماده از وزن بارنامه (نسبت تخصیص). در صورت نبود وزن بارنامه از تخصیص استفاده می‌شود.
                                    if waybill_total and total_allocated and total_allocated > 0:
                                        waybill_portion = waybill_total * (rmi.allocated_quantity or Decimal('0')) / total_allocated
                                    else:
                                        waybill_portion = rmi.allocated_quantity or Decimal('0')
                                    
                                    if not waybill_portion or waybill_portion <= 0:
                                        bug_logger.warning(
                                            f"رد شد: ماده اولیه {rmi.raw_material.name} - سهم وزن بارنامه نامعتبر. از انبار تامین‌کننده کم نمی‌شود."
                                        )
                                        continue
                                    
                                    # ایجاد StockEntry برای این ماده اولیه
                                    stock_entry = StockEntry.objects.create(
                                        transaction_date=jdatetime_datetime.now(),
                                        entry_type=StockEntry.StockEntryType.PURCHASE,
                                        notes=f"تخلیه حمل {transport_number} - {rmi.raw_material.name} - انتقال از انبار {source_warehouse.warehouse_id} به انبار {destination_warehouse_for_item.warehouse_id}",
                                        is_committed=False  # ابتدا commit نمی‌کنیم، بعد commit می‌کنیم
                                    )
                                    
                                    # ایجاد SourceStock (از انبار تامین‌کننده) — به اندازه وزن بارنامه (سهم این ماده)
                                    SourceStock.objects.create(
                                        stock_entry=stock_entry,
                                        from_content_type=raw_material_content_type,
                                        from_object_id=rmi.raw_material.pk,
                                        from_warehouse=source_warehouse,
                                        quantity=waybill_portion
                                    )
                                    
                                    # ایجاد TargetStock (به انبار کارخانه) — به اندازه وزن خالص باسکول
                                    TargetStock.objects.create(
                                        stock_entry=stock_entry,
                                        to_content_type=raw_material_content_type,
                                        to_object_id=rmi.raw_material.pk,
                                        to_warehouse=destination_warehouse_for_item,
                                        quantity=scale_net_weight
                                    )
                                    
                                    # Commit کردن StockEntry برای به‌روزرسانی موجودیت‌ها
                                    stock_entry.commit()
                                    
                                    bug_logger.info(
                                        f"لاگ موجودیت ایجاد شد - "
                                        f"StockEntry ID: {stock_entry.pk}, "
                                        f"ماده اولیه: {rmi.raw_material.name}, "
                                        f"از انبار: {source_warehouse.warehouse_id} (وزن بارنامه: {waybill_portion} kg), "
                                        f"به انبار: {destination_warehouse_for_item.warehouse_id} (وزن خالص باسکول: {scale_net_weight} kg)"
                                    )
                                
                                # لاگ کلی برای audit (از تامین‌کننده وزن بارنامه کم، به انبار وزن خالص باسکول اضافه)
                                warehouses_list = ', '.join([wh.warehouse_id for wh in set(item_warehouses.values())])
                                audit_logger.info(
                                    f"لاگ موجودیت برای تخلیه - "
                                    f"حمل: {transport_number}, "
                                    f"از انبار تامین‌کننده: {source_warehouse.warehouse_id} (وزن بارنامه), "
                                    f"به انبارها: {warehouses_list} (وزن خالص باسکول), "
                                    f"کاربر: {request.user.username}"
                                )
                            else:
                                bug_logger.warning(f"ماده اولیه‌ای برای ثبت موجودیت یافت نشد (Transport: {transport_number})")

                        except Exception as inv_err:
                            bug_logger.error(f"خطا در ایجاد لاگ موجودیت برای حمل {transport_number}: {inv_err}", exc_info=True)
                            # خطا را لاگ می‌کنیم اما فرآیند را متوقف نمی‌کنیم
                            messages.warning(request, f'اطلاعات تخلیه ثبت شد اما خطا در ایجاد لاگ موجودیت: {str(inv_err)}')
                    
                    # در صورت ارجاع به مدیر: وضعیت و سفارش را عوض نکن، فقط فلگ ارجاع را بزن (مثل ورود خودرو)
                    if is_refer_to_manager and wh_referral_reason:
                        pt.warehouse_delivery_referred_to_manager = True
                        pt.warehouse_delivery_referred_at = timezone.now()
                        pt.warehouse_delivery_referral_reason = wh_referral_reason
                        pt.save(update_fields=['warehouse_delivery_referred_to_manager', 'warehouse_delivery_referred_at', 'warehouse_delivery_referral_reason'])
                        audit_logger.activity(f"تحویل انبار برای حمل {transport_number} به مدیر ارجاع داده شد توسط {request.user.username} - دلیل: {wh_referral_reason[:100]}")
                        bug_logger.info(f"حمل {transport_number} به مدیر ارجاع داده شد - وضعیت بدون تغییر (در انتظار تایید مدیر)")
                    else:
                        # بدون ارجاع (یا تایید مدیر پس از ارجاع): وضعیت را به «در انتظار تطبیق انبار» ببر و در صورت ارجاع‌شده، پرچم را پاک کن
                        pt.status = Transport.STATUS_AWAITING_WH_RECONCILIATION
                        if getattr(pt, 'warehouse_delivery_referred_to_manager', False):
                            pt.warehouse_delivery_referred_to_manager = False
                            pt.warehouse_delivery_referred_at = None
                            pt.warehouse_delivery_referral_reason = None
                            bug_logger.info(f"ارجاع تحویل انبار برای حمل {transport_number} توسط مدیر تایید شد - وضعیت به 'در انتظار تطبیق انبار' تغییر یافت")
                        pt.save()
                        bug_logger.info(f"وضعیت حمل {transport_number} به 'در انتظار تطبیق انبار' تغییر یافت")
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
                    
                if is_refer_to_manager:
                    messages.warning(request, 'اطلاعات تخلیه ثبت شد و این مورد به مدیر ارجاع داده شد. تا تایید مدیر، این حمل در همین مرحله باقی می‌ماند، در لیست تحویل انبار نمایش داده نمی‌شود و فقط مدیر می‌تواند آن را باز کرده و تایید کند.')
                else:
                    messages.success(request, f'اطلاعات تخلیه ثبت شد. وزن خالص: {net_weight} - حمل به مرحله تطبیق انبار منتقل شد.')
                return redirect(reverse('supply:warehouse_delivery'))
            except Exception as e:
                bug_logger.error(f"خطا در ثبت تخلیه برای حمل {transport_number}: {e}")
                messages.error(request, f'خطا در ثبت اطلاعات تخلیه: {str(e)}')
        else:
            bug_logger.warning(f"فرم ثبت تخلیه نامعتبر برای حمل {transport_number}: {form.errors}")
            audit_logger.activity(f"فرم نامعتبر برای ثبت تخلیه حمل {transport_number}")
            # برای نمایش مجدد فرم با مودال ارجاع در صورت نیاز
            destination_warehouses = Warehouse.objects.filter(warehouse_type='primary')
            order_items = []
            if pt.allocation and pt.allocation.order:
                existing_infos = RawMaterialInfo.objects.filter(transport=pt).select_related('order_item', 'raw_material', 'order_item__raw_material')
                for info in existing_infos:
                    if info.order_item and info.order_item.raw_material:
                        net = info.net_weight or Decimal('0')
                        alloc = info.allocated_quantity or Decimal('0')
                        order_items.append({
                            'item': info.order_item, 'raw_material': info.raw_material, 'allocated_quantity': info.allocated_quantity,
                            'calculated_net_weight': info.net_weight, 'weight_diff': (net - alloc) if info.net_weight is not None else None,
                            'destination_warehouse_id': getattr(info, 'destination_warehouse_id', None),
                        })
            comparison_totals = _comparison_totals_from_order_items(order_items)
            initial_stages = _initial_stages_from_order_items(pt, order_items)
            context = {
                'form': form, 'pt': pt, 'order_items': order_items, 'comparison_totals': comparison_totals,
                'initial_stages': initial_stages,
                'read_only': False, 'awaiting_guard': False,
                'destination_warehouses': destination_warehouses,
                'accessible_transport_fields': accessible_transport_fields_view,
                'accessible_po_fields': accessible_po_fields,
                'accessible_raw_material_fields': accessible_raw_material_fields,
                'accessible_po_material_fields': accessible_po_material_fields,
                'is_warehouse_delivery_referred': getattr(pt, 'warehouse_delivery_referred_to_manager', False),
                'show_refer_button': not getattr(pt, 'warehouse_delivery_referred_to_manager', False) and not request.user.is_superuser,
                'refer_modal_open': is_refer_to_manager,
                'warehouse_delivery_referral_reason': getattr(pt, 'warehouse_delivery_referral_reason', '') or '',
            }
            return render(request, 'warehouse_delivery_detail.html', context)
    else:
        # مقداردهی اولیه فرم
        # نوع کرایه از سفارش خرید گرفته می‌شود (نه از transport)
        freight_payment_type = None
        if pt.allocation and pt.allocation.order and pt.allocation.order.freight_payment_type:
            freight_payment_type = pt.allocation.order.freight_payment_type
        elif pt.freight_payment_type:
            freight_payment_type = pt.freight_payment_type
        
        initial = {
            'freight_payment_type': freight_payment_type,
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
        }
        form = WarehouseDeliveryForm(initial=initial, transport=pt)
        
    # Prepare order items for context (for both new POST with errors and GET)
    # فقط مواد اولیه‌ای که در این حمل تخصیص یافته‌اند را نمایش می‌دهیم
    order_items = []
    if pt.allocation and pt.allocation.order:
        existing_infos = RawMaterialInfo.objects.filter(transport=pt).select_related('order_item', 'raw_material', 'order_item__raw_material')
        
        for info in existing_infos:
            if info.order_item and info.order_item.raw_material:
                net = info.net_weight or Decimal('0')
                alloc = info.allocated_quantity or Decimal('0')
                order_items.append({
                    'item': info.order_item,
                    'raw_material': info.raw_material,
                    'allocated_quantity': info.allocated_quantity,
                    'calculated_net_weight': info.net_weight,
                    'weight_diff': (net - alloc) if info.net_weight is not None else None,
                    'destination_warehouse_id': getattr(info, 'destination_warehouse_id', None),
                })
    
    comparison_totals = _comparison_totals_from_order_items(order_items)
    initial_stages = _initial_stages_from_order_items(pt, order_items)
    # لیست انبارهای مقصد (فقط انبارهای اولیه) برای انتخاب در هر مرحله
    destination_warehouses = Warehouse.objects.filter(warehouse_type='primary')
    
    is_wh_referred = getattr(pt, 'warehouse_delivery_referred_to_manager', False)
    show_refer_btn = not is_wh_referred and not request.user.is_superuser
    context = {
        'form': form,
        'pt': pt,
        'order_items': order_items,
        'comparison_totals': comparison_totals,
        'initial_stages': initial_stages,
        'read_only': False,
        'awaiting_guard': False,
        'destination_warehouses': destination_warehouses,
        'accessible_transport_fields': accessible_transport_fields_view,
        'accessible_po_fields': accessible_po_fields,
        'accessible_raw_material_fields': accessible_raw_material_fields,
        'accessible_po_material_fields': accessible_po_material_fields,
        'is_warehouse_delivery_referred': is_wh_referred,
        'show_refer_button': show_refer_btn,
        'refer_modal_open': False,
        'warehouse_delivery_referral_reason': getattr(pt, 'warehouse_delivery_referral_reason', '') or '',
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

    # اگر خروج خودرو به مدیر ارجاع شده، فقط سوپرادمین می‌تواند وارد شود
    if getattr(pt, 'carexit_referred_to_manager', False) and not request.user.is_superuser:
        audit_logger.activity(f"تلاش برای دسترسی به خروج خودرو ارجاع‌شده به مدیر - حمل {transport_number}")
        messages.error(request, 'این مورد به مدیر ارجاع شده و فقط مدیر می‌تواند خروج را تایید کند.')
        return HttpResponseForbidden('دسترسی غیرمجاز. این مورد به مدیر ارجاع شده است.')
    
    if request.method == 'POST':
        is_refer = request.POST.get('refer_to_manager') == '1'
        carexit_reason = (request.POST.get('carexit_referral_reason') or '').strip()
        if is_refer and not carexit_reason:
            messages.error(request, 'لطفاً دلیل ارجاع به مدیر را وارد کنید.')
            ctx = _carexit_secondary_context(pt)
            ctx.update({
                'pt': pt,
                'accessible_transport_fields': accessible_transport_fields,
                'accessible_po_fields': accessible_po_fields,
                'is_carexit_referred': getattr(pt, 'carexit_referred_to_manager', False),
                'show_refer_button': True,
                'carexit_referral_reason': getattr(pt, 'carexit_referral_reason', '') or '',
                'refer_modal_open': True,
                'delivery_items': _guard_exit_delivery_items(pt),
            })
            return render(request, 'car_exit_custodian_confirmation.html', ctx)
        if is_refer and carexit_reason:
            # ارجاع به مدیر بدون تغییر وضعیت
            try:
                pt.carexit_referred_to_manager = True
                pt.carexit_referred_at = timezone.now()
                pt.carexit_referral_reason = carexit_reason
                pt.save(update_fields=['carexit_referred_to_manager', 'carexit_referred_at', 'carexit_referral_reason'])
                audit_logger.activity(f"خروج خودرو برای حمل {transport_number} به مدیر ارجاع داده شد توسط {request.user.username} - دلیل: {carexit_reason[:100]}")
                messages.warning(request, 'این مورد به مدیر ارجاع داده شد. فقط مدیر می‌تواند از صفحه ارجاعات خروج را تایید کند.')
            except Exception as e:
                bug_logger.error(f"خطا در ارجاع خروج خودرو برای حمل {transport_number}: {e}")
                messages.error(request, f'خطا در ارجاع: {str(e)}')
            return redirect(reverse('supply:warehouse_delivery'))
        if not is_refer:
            # Confirm vehicle exit
            bug_logger.debug(f"Guard confirming vehicle exit for transport {transport_number}")
            try:
                with transaction.atomic():
                    pt.status = Transport.STATUS_AWAITING_SETTLEMENT
                    pt.delivery_date = jdatetime.date.today()
                    # در صورت تایید توسط مدیر، فلگ‌های ارجاع را پاک کن
                    if request.user.is_superuser:
                        pt.warehouse_delivery_referred_to_manager = False
                        pt.warehouse_delivery_referred_at = None
                        pt.warehouse_delivery_referral_reason = None
                        pt.carexit_referred_to_manager = False
                        pt.carexit_referred_at = None
                        pt.carexit_referral_reason = None
                    pt.save()
                    
                    po = pt.allocation.order if pt.allocation else None
                    if po and po.status == Order.STATUS_AWAITING_WAREHOUSE_RECONCILIATION:
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
    
    is_carexit_referred = getattr(pt, 'carexit_referred_to_manager', False)
    context = {
        'pt': pt,
        'accessible_transport_fields': accessible_transport_fields,
        'accessible_po_fields': accessible_po_fields,
        'is_carexit_referred': is_carexit_referred,
        'show_refer_button': not is_carexit_referred and not request.user.is_superuser,
        'carexit_referral_reason': getattr(pt, 'carexit_referral_reason', '') or '',
        'refer_modal_open': False,
        'delivery_items': _guard_exit_delivery_items(pt),
        **_carexit_secondary_context(pt),
    }
    return render(request, 'car_exit_custodian_confirmation.html', context)
