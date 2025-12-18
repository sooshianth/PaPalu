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
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from supply.tables import TransportTable
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
    # وزن ها
    gross_weight = forms.DecimalField(
        label='وزن پر (کیلوگرم)',
        required=True,
        max_digits=15,
        decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    tare_weight = forms.DecimalField(
        label='وزن خالی (کیلوگرم)',
        required=True,
        max_digits=15,
        decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    
    # نوع کرایه
    freight_payment_type = forms.ChoiceField(
        label='نوع کرایه',
        choices=[
            ('', 'انتخاب کنید'),
            ('cash', 'نقدی'),
            ('credit', 'اعتباری'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # فی حمل
    freight_rate = forms.DecimalField(
        label='فی حمل',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه اولیه
    initial_freight = forms.DecimalField(
        label='کرایه اولیه',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه کل
    total_freight = forms.DecimalField(
        label='کرایه کل',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # تخفیف
    discount = forms.DecimalField(
        label='تخفیف',
        required=True,
        max_digits=15,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'})
    )
    
    # مازاد
    surplus = forms.DecimalField(
        label='مازاد',
        required=True,
        max_digits=15,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'})
    )
    
    # کرایه پرداختی
    freight_payment = forms.DecimalField(
        label='کرایه پرداختی',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # انبار مبدأ (انبار مجازی تامین‌کننده)
    source_warehouse = forms.ModelChoiceField(
        label='انبار مبدأ (تامین‌کننده)',
        queryset=Warehouse.objects.filter(warehouse_type='supplier'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='انبار مجازی تامین‌کننده که ماده اولیه از آنجا آمده است'
    )
    
    # انبار مقصد (انبار کارخانه)
    destination_warehouse = forms.ModelChoiceField(
        label='انبار مقصد (کارخانه)',
        queryset=Warehouse.objects.exclude(warehouse_type='supplier'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='انبار کارخانه که ماده اولیه در آنجا تخلیه می‌شود'
    )
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        gross = cleaned_data.get('gross_weight')
        tare = cleaned_data.get('tare_weight')
        
        bug_logger.debug(f"Form validation - gross_weight: {gross}, tare_weight: {tare}")
        
        # وزن پر باید بزرگتر از وزن خالی باشد
        if gross and tare:
            if gross <= tare:
                bug_logger.warning(f"Invalid weights - gross ({gross}) <= tare ({tare})")
                raise forms.ValidationError(
                    'وزن پر باید همیشه بزرگ‌تر از وزن خالی باشد.'
                )
            
            net_weight = gross - tare
            bug_logger.debug(f"Calculated net_weight: {net_weight}")
            if net_weight <= 0:
                bug_logger.warning(f"Invalid net_weight: {net_weight}")
                raise forms.ValidationError(
                    'مقدار تحویلی (وزن پر − وزن خالی) نامعقول است.'
                )
        
        return cleaned_data


class WarehouseDeliveryTable(TransportTable):
    """جدول حمل‌های در انتظار تخلیه"""
    
    raw_materials = tables.Column(
        verbose_name='نام ماده اولیه',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    quantity = tables.Column(
        verbose_name='مقدار',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    unit = tables.Column(
        verbose_name='واحد',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ستون‌های مورد نیاز برای انباردار: شماره سفارش، نوع ماده اولیه، مقدار، واحد، پلاک، نوع ماشین
        # این ستون‌ها باید همیشه نمایش داده شوند
        required_columns = ['purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions']
        
        # همیشه ستون‌های مورد نیاز را نمایش بده
        for col_name in required_columns:
            if col_name in ['raw_materials', 'quantity', 'unit']:
                # ستون‌های custom که در base_columns تعریف شده‌اند
                if col_name in self.base_columns:
                    self.base_columns[col_name].visible = True
            elif col_name in self.columns:
                # ستون‌های عادی
                self.columns[col_name].column.visible = True
    
    def render_raw_materials(self, record):
        """نمایش لیست مواد اولیه از سفارش خرید"""
        if not record.purchase_order:
            return '—'
        # استفاده از order_items به جای materials
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials if m.raw_material]
            return format_html('<br>'.join(names)) if names else '—'
        return '—'
    
    def render_quantity(self, record):
        """نمایش مقدار سفارش"""
        if not record.purchase_order:
            return '—'
        # استفاده از order_items به جای materials
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).all()
        if materials:
            quantities = [str(m.quantity) for m in materials if m.quantity]
            return format_html('<br>'.join(quantities)) if quantities else '—'
        return '—'
    
    def render_unit(self, record):
        """نمایش واحد سفارش"""
        if not record.purchase_order:
            return '—'
        # استفاده از order_items به جای materials
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).all()
        if materials:
            units = [m.get_weight_unit_display() or '—' for m in materials]
            return format_html('<br>'.join(units)) if units else '—'
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه جزئیات حمل"""
        # استفاده از transport_number یا pk در صورت None بودن
        transport_id = record.transport_number
        if not transport_id or transport_id == 'None' or str(transport_id).strip() == '':
            transport_id = str(record.pk)
        detail_url = reverse('supply:warehouse_delivery_detail', args=[str(transport_id)])
        return format_html(
            '<a href="{}" class="btn btn-primary btn-sm">جزئیات حمل</a>',
            detail_url
        )
    
    class Meta(TransportTable.Meta):
        sequence = ('purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')
        fields = ('purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')


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
        return render(request, 'supply_warehouse_delivery_list.html', context)
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
        return render(request, 'supply_warehouse_delivery_list.html', context)


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
            pt = get_object_or_404(Transport, pk=int(transport_number))
        else:
            bug_logger.debug(f"Fetching transport by transport_number: {transport_number}")
            pt = get_object_or_404(Transport, transport_number=transport_number)
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
    
    # Only allow editing if status is awaiting_unloading
    if pt.status != Transport.STATUS_AWAITING_UNLOADING:
        # Read-only mode for awaiting_wh_reconciliation
        bug_logger.debug(f"Loading read-only form for transport {transport_number} - status: {pt.status}")
        initial = {
            'gross_weight': pt.gross_weight,
            'tare_weight': pt.tare_weight,
            'freight_payment_type': pt.freight_payment_type,
            'freight_rate': getattr(pt, 'freight_rate', None),
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
            'source_warehouse': getattr(pt, 'source_warehouse', None),
            'destination_warehouse': getattr(pt, 'destination_warehouse', None),
        }
        form = WarehouseDeliveryForm(initial=initial)
        for field in form.fields:
            form.fields[field].disabled = True
        
        context = {
            'form': form,
            'pt': pt,
            'read_only': True,
            'awaiting_guard': True,
            'accessible_transport_fields': accessible_transport_fields_view,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        }
        return render(request, 'supply_warehouse_delivery_detail.html', context)
    
    if request.method == 'POST':
        form = WarehouseDeliveryForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            audit_logger.info(f"شروع ثبت تخلیه برای حمل {transport_number}")
            
            try:
                with transaction.atomic():
                    # محاسبه وزن خالص
                    gross = data.get('gross_weight')
                    tare = data.get('tare_weight')
                    net_weight = gross - tare if gross and tare else None
                    source_warehouse = data.get('source_warehouse')
                    destination_warehouse = data.get('destination_warehouse')
                    
                    bug_logger.debug(f"Saving unloading data - Transport: {transport_number}, Gross: {gross}, Tare: {tare}, Net: {net_weight}, Source: {source_warehouse}, Destination: {destination_warehouse}")
                    
                    # به‌روزرسانی فیلدهای حمل
                    pt.gross_weight = gross
                    pt.tare_weight = tare
                    pt.net_weight = net_weight
                    pt.freight_payment_type = data.get('freight_payment_type')
                    pt.initial_freight = data.get('initial_freight')
                    pt.total_freight = data.get('total_freight')
                    pt.discount = data.get('discount', 0)
                    pt.surplus = data.get('surplus', 0)
                    pt.freight_payment = data.get('freight_payment')
                    
                    # ثبت تاریخ تخلیه
                    pt.loading_date = jdatetime.date.today()
                    pt.save()
                    
                    bug_logger.info(f"اطلاعات تخلیه برای حمل {transport_number} ثبت شد - وزن خالص: {net_weight}")
                    
                    # ایجاد لاگ موجودیت: از انبار مبدأ (تامین‌کننده) به انبار مقصد (کارخانه)
                    if source_warehouse and destination_warehouse and net_weight and net_weight > 0:
                        try:
                            # گرفتن ماده اولیه از سفارش
                            po = pt.allocation.order if pt.allocation else None
                            if po:
                                # گرفتن اولین ماده اولیه از سفارش
                                order_item = po.order_items.filter(raw_material__isnull=False).select_related('raw_material').first()
                                if order_item and order_item.raw_material:
                                    raw_material = order_item.raw_material
                                    
                                    # ایجاد StockEntry
                                    stock_entry = StockEntry.objects.create(
                                        transaction_date=jdatetime_datetime.now(),
                                        notes=f"تخلیه حمل {transport_number} - انتقال از انبار {source_warehouse.warehouse_id} به انبار {destination_warehouse.warehouse_id}",
                                        is_committed=False  # ابتدا commit نمی‌کنیم، بعد commit می‌کنیم
                                    )
                                    
                                    # ایجاد SourceStock (از انبار تامین‌کننده)
                                    raw_material_content_type = ContentType.objects.get_for_model(RawMaterial)
                                    source_stock = SourceStock.objects.create(
                                        stock_entry=stock_entry,
                                        from_content_type=raw_material_content_type,
                                        from_object_id=raw_material.pk,
                                        from_warehouse=source_warehouse,
                                        quantity=net_weight
                                    )
                                    
                                    # ایجاد TargetStock (به انبار کارخانه)
                                    target_stock = TargetStock.objects.create(
                                        stock_entry=stock_entry,
                                        to_content_type=raw_material_content_type,
                                        to_object_id=raw_material.pk,
                                        to_warehouse=destination_warehouse,
                                        quantity=net_weight
                                    )
                                    
                                    # Commit کردن StockEntry برای به‌روزرسانی موجودیت‌ها
                                    stock_entry.commit()
                                    
                                    bug_logger.info(
                                        f"لاگ موجودیت ایجاد شد - "
                                        f"StockEntry ID: {stock_entry.pk}, "
                                        f"از انبار: {source_warehouse.warehouse_id}, "
                                        f"به انبار: {destination_warehouse.warehouse_id}, "
                                        f"مقدار: {net_weight} کیلوگرم, "
                                        f"ماده اولیه: {raw_material.name}"
                                    )
                                    
                                    audit_logger.info(
                                        f"لاگ موجودیت برای تخلیه - "
                                        f"حمل: {transport_number}, "
                                        f"از انبار: {source_warehouse.warehouse_id}, "
                                        f"به انبار: {destination_warehouse.warehouse_id}, "
                                        f"مقدار: {net_weight} کیلوگرم, "
                                        f"ماده اولیه: {raw_material.name}, "
                                        f"کاربر: {request.user.username}"
                                    )
                                else:
                                    bug_logger.warning(f"ماده اولیه برای سفارش {po.order_number} پیدا نشد")
                            else:
                                bug_logger.warning(f"سفارش برای حمل {transport_number} پیدا نشد")
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
                        po.transition(Order.STATUS_AWAITING_WH_RECONCILIATION, user=request.user, note=f"تخلیه برای حمل {transport_number} تکمیل شد و در انتظار تطبیق اطلاعات انبار است.")
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
        # پیش‌پر کردن فرم با داده‌های موجود
        bug_logger.debug(f"Initializing edit form for transport {transport_number} with existing data")
        initial = {
            'gross_weight': pt.gross_weight,
            'tare_weight': pt.tare_weight,
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
        'read_only': False,
        'awaiting_guard': False,
        'accessible_transport_fields': accessible_transport_fields,
        'accessible_po_fields': accessible_po_fields,
        'accessible_raw_material_fields': accessible_raw_material_fields,
        'accessible_po_material_fields': accessible_po_material_fields,
    }
    return render(request, 'supply_warehouse_delivery_detail.html', context)


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
                
                # تغییر وضعیت سفارش از "در انتظار تطبیق اطلاعات انبار" به "در انتظار تطبیق اطلاعات تحویل انبار"
                po = pt.allocation.order if pt.allocation else None
                if po and po.status == Order.STATUS_AWAITING_WH_RECONCILIATION:
                    # در مستندات گفته شده که وضعیت به "در انتظار تطبیق اطلاعات تحویل انبار" تغییر می‌یابد
                    # اما این وضعیت در Order model وجود ندارد، پس از همان STATUS_AWAITING_WH_RECONCILIATION استفاده می‌کنیم
                    # یا می‌توانیم یک وضعیت جدید اضافه کنیم
                    bug_logger.info(f"وضعیت سفارش {po.order_number} در حالت 'در انتظار تطبیق اطلاعات انبار' باقی می‌ماند")
                
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
    return render(request, 'supply_guard_vehicle_exit.html', context)
