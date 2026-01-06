import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.html import format_html, mark_safe
from django.utils import timezone
from django_tables2 import RequestConfig
import jdatetime

from core.logging_levels import *
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

from core.TransportFolder.TransportModel import Transport
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.BankAccountModel import BankAccount
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from django.contrib.auth import get_user_model
from supply.tables import TransportTable
import django_tables2 as tables

User = get_user_model()


# ==================== Field Access Helper Functions ====================

def get_accessible_purchase_transport_fields(user):
    """Check field access for Transport model (view permission)"""
    # برای سوپریوزر، همه فیلدها قابل دسترسی هستند
    if user.is_superuser:
        return {
            'transport_number': True,
            'purchase_order': True,
            'status': True,
            'transport_type': True,
            'vehicle_type': True,
            'plate_number': True,
            'driver': True,
            'freight_payment_type': True,
            'initial_freight': True,
            'total_freight': True,
            'discount': True,
            'surplus': True,
            'freight_payment': True,
            'driver_account_number': True,
            'driver_sheba_number': True,
            'expected_arrival_date': True,
            'actual_arrival_date': True,
            'loading_date': True,
            'delivery_date': True,
            'gross_weight': True,
            'tare_weight': True,
            'net_weight': True,
            'waybill_weight': True,
            'waybill_number': True,
            'waybill_date': True,
            'bill_of_lading_file': True,
            'notes': True,
            'created_at': True,
        }
    
    return {
        'transport_number': user_can_access_field(user, Transport, 'transport_number', 'view'),
        'purchase_order': user_can_access_field(user, Transport, 'purchase_order', 'view'),
        'status': user_can_access_field(user, Transport, 'status', 'view'),
        'transport_type': user_can_access_field(user, Transport, 'transport_type', 'view'),
        'vehicle_type': user_can_access_field(user, Transport, 'vehicle_type', 'view'),
        'plate_number': user_can_access_field(user, Transport, 'plate_number', 'view'),
        'driver': user_can_access_field(user, Transport, 'driver', 'view'),
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'view'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'view'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'view'),
        'discount': user_can_access_field(user, Transport, 'discount', 'view'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'view'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'view'),
        'driver_account_number': user_can_access_field(user, Transport, 'driver_account_number', 'view'),
        'driver_sheba_number': user_can_access_field(user, Transport, 'driver_sheba_number', 'view'),
        'expected_arrival_date': user_can_access_field(user, Transport, 'expected_arrival_date', 'view'),
        'actual_arrival_date': user_can_access_field(user, Transport, 'actual_arrival_date', 'view'),
        'loading_date': user_can_access_field(user, Transport, 'loading_date', 'view'),
        'delivery_date': user_can_access_field(user, Transport, 'delivery_date', 'view'),
        'gross_weight': user_can_access_field(user, Transport, 'gross_weight', 'view'),
        'tare_weight': user_can_access_field(user, Transport, 'tare_weight', 'view'),
        'net_weight': user_can_access_field(user, Transport, 'net_weight', 'view'),
        'waybill_weight': user_can_access_field(user, Transport, 'waybill_weight', 'view'),
        'waybill_number': user_can_access_field(user, Transport, 'waybill_number', 'view'),
        'waybill_date': user_can_access_field(user, Transport, 'waybill_date', 'view'),
        'bill_of_lading_file': user_can_access_field(user, Transport, 'bill_of_lading_file', 'view'),
        'notes': user_can_access_field(user, Transport, 'notes', 'view'),
        'created_at': user_can_access_field(user, Transport, 'created_at', 'view'),
    }


def get_accessible_purchase_transport_fields_edit(user):
    """Check field access for Transport model (edit permission)"""
    return {
        'transport_number': user_can_access_field(user, Transport, 'transport_number', 'edit'),
        'purchase_order': user_can_access_field(user, Transport, 'purchase_order', 'edit'),
        'status': user_can_access_field(user, Transport, 'status', 'edit'),
        'transport_type': user_can_access_field(user, Transport, 'transport_type', 'edit'),
        'vehicle_type': user_can_access_field(user, Transport, 'vehicle_type', 'edit'),
        'plate_number': user_can_access_field(user, Transport, 'plate_number', 'edit'),
        'driver': user_can_access_field(user, Transport, 'driver', 'edit'),
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'edit'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'edit'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'edit'),
        'discount': user_can_access_field(user, Transport, 'discount', 'edit'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'edit'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'edit'),
        'driver_account_number': user_can_access_field(user, Transport, 'driver_account_number', 'edit'),
        'driver_sheba_number': user_can_access_field(user, Transport, 'driver_sheba_number', 'edit'),
        'driver_bank_account': user_can_access_field(user, Transport, 'driver_bank_account', 'edit'),
        'expected_arrival_date': user_can_access_field(user, Transport, 'expected_arrival_date', 'edit'),
        'actual_arrival_date': user_can_access_field(user, Transport, 'actual_arrival_date', 'edit'),
        'loading_date': user_can_access_field(user, Transport, 'loading_date', 'edit'),
        'delivery_date': user_can_access_field(user, Transport, 'delivery_date', 'edit'),
        'gross_weight': user_can_access_field(user, Transport, 'gross_weight', 'edit'),
        'tare_weight': user_can_access_field(user, Transport, 'tare_weight', 'edit'),
        'net_weight': user_can_access_field(user, Transport, 'net_weight', 'edit'),
        'waybill_weight': user_can_access_field(user, Transport, 'waybill_weight', 'edit'),
        'waybill_number': user_can_access_field(user, Transport, 'waybill_number', 'edit'),
        'waybill_date': user_can_access_field(user, Transport, 'waybill_date', 'edit'),
        'bill_of_lading_file': user_can_access_field(user, Transport, 'bill_of_lading_file', 'edit'),
        'notes': user_can_access_field(user, Transport, 'notes', 'edit'),
    }


def get_accessible_procurement_purchase_order_fields_for_carentrance(user):
    """Check field access for ProcurementPurchaseOrder model (for car entrance views)"""
    # برای سوپریوزر، همه فیلدها قابل دسترسی هستند
    if user.is_superuser:
        return {
            'order_number': True,
            'status': True,
            'supplier': True,
            'created_at': True,
            'materials': True,
        }
    
    return {
        'order_number': user_can_access_field(user, Order, 'order_number', 'view'),
        'status': user_can_access_field(user, Order, 'status', 'view'),
        'supplier': user_can_access_field(user, Order, 'supplier', 'view'),
        'created_at': user_can_access_field(user, Order, 'created_at', 'view'),
        'materials': user_can_access_field(user, Order, 'materials', 'view'),
    }


def get_accessible_raw_material_fields_for_carentrance(user):
    """Check field access for RawMaterial model (for car entrance views)"""
    return {
        'name': user_can_access_field(user, RawMaterial, 'name', 'view'),
        'material_code': user_can_access_field(user, RawMaterial, 'material_code', 'view'),
        'unit': user_can_access_field(user, RawMaterial, 'unit', 'view'),
    }


def get_accessible_person_fields_for_carentrance(user):
    """Check field access for Person model (for car entrance views)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'phone_number': user_can_access_field(user, Person, 'phone_number', 'view'),
        'national_id': user_can_access_field(user, Person, 'national_id', 'view'),
        'type': user_can_access_field(user, Person, 'type', 'view'),
    }


def get_accessible_person_fields_edit_for_carentrance(user):
    """Check field access for Person model (edit permission for car entrance views)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'edit'),
        'phone_number': user_can_access_field(user, Person, 'phone_number', 'edit'),
        'national_id': user_can_access_field(user, Person, 'national_id', 'edit'),
        'type': user_can_access_field(user, Person, 'type', 'edit'),
    }


def get_accessible_user_fields_for_carentrance(user):
    """Check field access for User model (for car entrance views)"""
    return {
        'username': user_can_access_field(user, User, 'username', 'view'),
        'first_name': user_can_access_field(user, User, 'first_name', 'view'),
        'last_name': user_can_access_field(user, User, 'last_name', 'view'),
    }

# ==================== End Field Access Helper Functions ====================


class CarEntranceDriverForm(forms.Form):
    """فرم ثبت اطلاعات راننده برای ورود خودرو
    
    فیلدهای اجباری:
    - نام راننده
    - شماره تلفن راننده
    - پلاک
    - کد ملی راننده
    - وزن بارنامه
    - تصویر بارنامه
    - شماره حساب راننده (فقط اگر نوع کرایه "پرداخت به راننده" باشد)
    - شماره شبا راننده (فقط اگر نوع کرایه "پرداخت به راننده" باشد)
    """
    phone = forms.CharField(
        label='شماره تلفن راننده',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09123456789'})
    )
    name = forms.CharField(
        label='نام راننده',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'نام و نام خانوادگی راننده'})
    )
    national_id = forms.CharField(
        label='کد ملی راننده',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'کد ملی 10 رقمی'})
    )
    plate_number = forms.CharField(
        label='پلاک',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12الف34567'})
    )
    waybill_weight = forms.DecimalField(
        label='وزن بارنامه (کیلوگرم)',
        required=True,
        max_digits=15,
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.000',
            'step': '0.001',
            'min': '0'
        })
    )
    waybill_date = forms.DateField(
        label='تاریخ بارنامه',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'text',
            'placeholder': '1403/09/15',
            'id': 'id_waybill_date'
        })
    )
    bill_of_lading_file = forms.FileField(
        label='تصویر بارنامه',
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf'
        })
    )
    account = forms.CharField(
        label='شماره حساب راننده',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'شماره حساب بانکی'})
    )
    sheba = forms.CharField(
        label='شماره شبا راننده',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IR123456789012345678901234'})
    )
    
    def __init__(self, *args, freight_payment_type=None, driver=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.freight_payment_type = freight_payment_type
        self.driver = driver
        
        # اگر نوع کرایه "پرداخت به راننده" باشد، فیلدهای حساب و شبا را required می‌کنیم
        if freight_payment_type == 'pay_to_driver':
            self.fields['account'].required = True
            self.fields['sheba'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        # بررسی اینکه اگر نوع کرایه "پرداخت به راننده" باشد، فیلدهای حساب و شبا باید پر شوند
        if self.freight_payment_type == 'pay_to_driver':
            account = cleaned_data.get('account')
            sheba = cleaned_data.get('sheba')
            if not account:
                self.add_error('account', 'این فیلد برای نوع کرایه "پرداخت به راننده" اجباری است.')
            if not sheba:
                self.add_error('sheba', 'این فیلد برای نوع کرایه "پرداخت به راننده" اجباری است.')
        return cleaned_data


class CarEntranceTable(TransportTable):
    raw_materials = tables.Column(
        verbose_name='نام مواد اولیه',
        empty_values=(),
        orderable=False,
        visible=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ستون‌های مورد نیاز برای نگهبان: نوع ماشین، نام ماده اولیه، زمان ثبت، وضعیت، عملیات
        required_columns = ['vehicle_type', 'raw_materials', 'created_at', 'status', 'actions']
        
        # همیشه ستون‌های مورد نیاز را نمایش بده
        for col_name in required_columns:
            if col_name == 'raw_materials':
                if 'raw_materials' in self.base_columns:
                    self.base_columns['raw_materials'].visible = True
            elif col_name in self.columns:
                self.columns[col_name].column.visible = True
    
    def render_raw_materials(self, record):
        """نمایش لیست مواد اولیه از سفارش خرید"""
        if not record.purchase_order:
            return '—'
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials if m.raw_material]
            if names:
                # نمایش badge برای هر ماده اولیه
                badges = []
                for name in names:
                    badges.append(format_html(
                        '<span class="badge badge-green">{}</span>',
                        name
                    ))
                return format_html('<div style="display: flex; gap: 5px; flex-wrap: wrap;">{}</div>', mark_safe(' '.join(badges)))
            return '—'
        return '—'
    
    def render_vehicle_type(self, record):
        """نمایش نوع ماشین"""
        return record.get_vehicle_type_display() or '—'
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        status_display = record.get_status_display() if hasattr(record, 'get_status_display') else value
        return format_html('<span class="status-badge status-{}">{}</span>', record.status, status_display)
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        if hasattr(record, 'created_at') and record.created_at:
            import jdatetime
            dt = record.created_at
            if isinstance(dt, jdatetime.datetime):
                if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
                    return dt.strftime('%Y-%m-%d %H:%M')
                else:
                    return dt.strftime('%Y-%m-%d')
            elif isinstance(dt, jdatetime.date):
                return dt.strftime('%Y-%m-%d')
        return value or '—'
    
    def render_actions(self, record):
        """نمایش دکمه ثبت راننده"""
        transport_id = record.transport_number
        if not transport_id or transport_id == 'None' or str(transport_id).strip() == '':
            transport_id = str(record.pk)
        register_url = reverse('supply:carentrance_register_driver', args=[str(transport_id)])
        return format_html(
            '<a href="{}" class="btn-register-driver" title="ثبت راننده">ثبت راننده</a>',
            register_url
        )
    
    class Meta(TransportTable.Meta):
        template_name = 'django_tables2/bootstrap.html'
        fields = ('vehicle_type', 'raw_materials', 'created_at', 'status', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('vehicle_type', 'raw_materials', 'created_at', 'status', 'actions')


@login_required
def car_entrance_list_view(request):
    """صفحه لیست ورود خودروها مخصوص نگهبان - حمل‌هایی که وضعیت آنها یا سفارش خرید آنها "در انتظار ورود خودرو" است."""
    audit_logger.info("مشاهده صفحه ورود خودرو (نگهبان)")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_DRIVER.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه ورود خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_carentrance(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_carentrance(request.user)
    accessible_person_fields = get_accessible_person_fields_for_carentrance(request.user)
    
    try:
        # نمایش فقط حمل‌هایی که در وضعیت "در انتظار ورود خودرو" هستند
        # این حمل‌ها باید دارای اطلاعات پایه (نوع ماشین، نوع حمل) باشند
        # ولی فاقد داده‌های کامل راننده باشند
        # باید جهت ورودی داشته باشند (direction='inbound' یا transport_type='inbound')
        # برای حمل‌های قدیمی که direction ندارند، از transport_type استفاده می‌کنیم
        
        # ابتدا همه حمل‌های در انتظار ورود را بگیر
        all_awaiting = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_VEHICLE_ENTRY
        )
        
        # لاگ برای دیباگ
        total_count = all_awaiting.count()
        bug_logger.info(f"تعداد کل حمل‌های در انتظار ورود خودرو: {total_count}")
        
        # فیلتر بر اساس جهت ورودی
        # حمل‌های ورودی: direction='inbound' یا transport_type='inbound'
        # یا اگر هر دو null باشند (برای حمل‌های قدیمی که فقط status دارند)
        transports = all_awaiting.filter(
            Q(direction='inbound') | 
            Q(transport_type='inbound') |
            (Q(direction__isnull=True) & Q(transport_type__isnull=True))
        )
        
        inbound_count = transports.count()
        bug_logger.info(f"تعداد حمل‌های ورودی در انتظار ورود خودرو: {inbound_count}")
        
        # اگر هیچ حمل ورودی پیدا نشد ولی حمل‌های در انتظار وجود دارند، همه را نمایش بده (برای دیباگ)
        # این به ما کمک می‌کند تا ببینیم چه مشکلی وجود دارد
        if inbound_count == 0 and total_count > 0:
            bug_logger.warning(f"هیچ حمل ورودی پیدا نشد! نمایش همه حمل‌های در انتظار ورود برای دیباگ")
            sample_transports = list(all_awaiting.values_list('transport_number', 'direction', 'transport_type', 'status')[:5])
            bug_logger.warning(f"نمونه حمل‌ها (transport_number, direction, transport_type, status): {sample_transports}")
            # نمایش همه حمل‌های در انتظار ورود (حتی اگر direction/transport_type تنظیم نشده باشند)
            transports = all_awaiting
        
        transports = transports.select_related('allocation__order', 'allocation__order__customer', 'driver').order_by('-created_at')
        final_count = transports.count()
        bug_logger.info(f"تعداد نهایی حمل‌های برای نمایش: {final_count}")
        
        # لاگ accessible_fields برای دیباگ
        if request.user.is_superuser:
            bug_logger.info(f"کاربر سوپریوزر است - همه فیلدها باید قابل دسترسی باشند")
            # برای سوپریوزر، مطمئن شویم که همه فیلدها True هستند
            for key in accessible_transport_fields:
                accessible_transport_fields[key] = True
        else:
            bug_logger.info(f"accessible_transport_fields sample: {dict(list(accessible_transport_fields.items())[:5])}")
        
        # برای نگهبان، ستون‌های مورد نیاز را همیشه True می‌کنیم
        required_fields_for_guard = ['vehicle_type', 'created_at', 'status']
        for field in required_fields_for_guard:
            if field in accessible_transport_fields:
                accessible_transport_fields[field] = True
        
        table = CarEntranceTable(transports, prefix='car-', accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 20}).configure(table)
        
        # لاگ تعداد ردیف‌های جدول و ستون‌های visible
        visible_columns = [col for col in table.columns if col.visible]
        bug_logger.info(f"تعداد ردیف‌های جدول: {len(table.rows)}")
        bug_logger.info(f"ستون‌های visible: {[col.name for col in visible_columns]}")
        
        context = {
            'table': table,
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
        }
        return render(request, 'car_entrance_list.html', context)
    except Exception as e:
        bug_logger.error(f"Car entrance list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست ورود خودروها.')
        return render(request, 'car_entrance_list.html', {
            'table': TransportTable([], prefix='car-'),
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
        })


@login_required
def register_driver_for_transport_view(request, transport_number):
    """فرم ثبت اطلاعات راننده و پلاک برای یک حمل؛ پس از ثبت، وضعیت به "در انتظار تخلیه" تغییر می‌یابد."""
    audit_logger.info(f"دسترسی به فرم ثبت راننده برای حمل {transport_number}")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_DRIVER.value):
        audit_logger.activity(f"تلاش برای ثبت راننده بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به ثبت راننده را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # اگر transport_number برابر None است یا 'None'، از pk استفاده کن
    if not transport_number or transport_number == 'None':
        bug_logger.error(f"transport_number نامعتبر: {transport_number}")
        messages.error(request, 'شماره حمل نامعتبر است.')
        return redirect(reverse('supply:carentrance'))
    
    # Get field access permissions for edit
    accessible_transport_fields = get_accessible_purchase_transport_fields_edit(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_carentrance(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_carentrance(request.user)
    accessible_person_fields = get_accessible_person_fields_edit_for_carentrance(request.user)
    
    # تلاش برای پیدا کردن حمل با transport_number یا pk
    try:
        if transport_number.isdigit():
            pt = get_object_or_404(
                Transport.objects.select_related('allocation', 'allocation__order', 'allocation__order__customer', 'driver'),
                pk=int(transport_number)
            )
        else:
            pt = get_object_or_404(
                Transport.objects.select_related('allocation', 'allocation__order', 'allocation__order__customer', 'driver'),
                transport_number=transport_number
            )
    except (ValueError, Transport.DoesNotExist) as e:
        bug_logger.error(f"خطا در یافتن حمل با شناسه {transport_number}: {e}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect(reverse('supply:carentrance'))

    if pt.status != Transport.STATUS_AWAITING_VEHICLE_ENTRY:
        audit_logger.activity(f"تلاش برای ثبت راننده برای حمل {transport_number} با وضعیت نامعتبر: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل ثبت راننده نیست.')
        return redirect(reverse('supply:carentrance'))

    if request.method == 'POST':
        # ابتدا راننده را پیدا یا ایجاد می‌کنیم تا بتوانیم queryset فرم را تنظیم کنیم
        phone = request.POST.get('phone', '').strip()
        driver = None
        if phone:
            driver = Person.objects.filter(phone_number=phone, type='driver').first()
        
        # دریافت freight_payment_type از سفارش خرید (نه از transport)
        freight_payment_type = None
        if pt.allocation and pt.allocation.order and pt.allocation.order.freight_payment_type:
            freight_payment_type = pt.allocation.order.freight_payment_type
        elif pt.freight_payment_type:
            freight_payment_type = pt.freight_payment_type
        
        form = CarEntranceDriverForm(request.POST, request.FILES, freight_payment_type=freight_payment_type, driver=driver)
        if form.is_valid():
            data = form.cleaned_data
            phone = data.get('phone')
            audit_logger.info(f"شروع ثبت راننده برای حمل {transport_number}")
            try:
                with transaction.atomic():
                    # جستجوی راننده با شماره تلفن
                    driver = Person.objects.filter(phone_number=phone, type='driver').first()
                    if not driver:
                        bug_logger.info(f"ایجاد راننده جدید با شماره تلفن {phone} برای حمل {transport_number}")
                        # ایجاد رکورد راننده جدید
                        driver = Person.objects.create(
                            name=data.get('name'),
                            phone_number=phone,
                            national_id=data.get('national_id'),
                            type='driver'
                        )
                        audit_logger.info(f"راننده جدید ایجاد شد - شناسه: {driver.pk} - نام: {driver.name}")
                    else:
                        bug_logger.debug(f"راننده موجود یافت شد - شناسه: {driver.pk} - نام: {driver.name}")
                        # به‌روزرسانی اطلاعات راننده در صورت نیاز
                        if driver.name != data.get('name'):
                            driver.name = data.get('name')
                        if driver.national_id != data.get('national_id'):
                            driver.national_id = data.get('national_id')
                        driver.save()
                    
                    # به‌روزرسانی فیلدهای حمل
                    pt.driver = driver
                    pt.plate_number = data.get('plate_number')
                    
                    # ثبت وزن بارنامه
                    if data.get('waybill_weight'):
                        pt.waybill_weight = data.get('waybill_weight')
                    
                    # ثبت تاریخ بارنامه
                    if data.get('waybill_date'):
                        pt.waybill_date = data.get('waybill_date')
                    
                    # ثبت تصویر بارنامه
                    if 'bill_of_lading_file' in request.FILES:
                        pt.bill_of_lading_file = request.FILES['bill_of_lading_file']
                    
                    # دریافت freight_payment_type از سفارش خرید
                    freight_payment_type = None
                    if pt.allocation and pt.allocation.order and pt.allocation.order.freight_payment_type:
                        freight_payment_type = pt.allocation.order.freight_payment_type
                    elif pt.freight_payment_type:
                        freight_payment_type = pt.freight_payment_type
                    
                    # فقط اگر نوع کرایه "پرداخت به راننده" باشد، حساب بانکی را ثبت می‌کنیم
                    if freight_payment_type == 'pay_to_driver':
                        account_number = data.get('account', '').strip()
                        sheba_number = data.get('sheba', '').strip()
                        
                        if account_number or sheba_number:
                            # دریافت یا ایجاد FinancialBanking برای راننده
                            financial_banking, created = FinancialBanking.objects.get_or_create(
                                person=driver
                            )
                            
                            # جستجوی حساب بانکی موجود با این شماره حساب و شبا
                            # ابتدا سعی می‌کنیم با هر دو فیلد پیدا کنیم
                            bank_account = None
                            if account_number and sheba_number:
                                bank_account = BankAccount.objects.filter(
                                    financial_banking=financial_banking,
                                    account_number=account_number,
                                    shaba_number=sheba_number
                                ).first()
                            
                            # اگر پیدا نشد، با شماره حساب جستجو می‌کنیم
                            if not bank_account and account_number:
                                bank_account = BankAccount.objects.filter(
                                    financial_banking=financial_banking,
                                    account_number=account_number
                                ).first()
                            
                            # اگر هنوز پیدا نشد، با شماره شبا جستجو می‌کنیم
                            if not bank_account and sheba_number:
                                bank_account = BankAccount.objects.filter(
                                    financial_banking=financial_banking,
                                    shaba_number=sheba_number
                                ).first()
                            
                            # اگر حساب بانکی وجود نداشت، یکی بساز
                            if not bank_account:
                                bank_account = BankAccount.objects.create(
                                    financial_banking=financial_banking,
                                    account_number=account_number if account_number else None,
                                    shaba_number=sheba_number if sheba_number else None,
                                    bank_name=None  # می‌تواند بعداً پر شود
                                )
                                bug_logger.info(f"حساب بانکی جدید برای راننده {driver.name} ایجاد شد - حساب: {account_number}, شبا: {sheba_number}")
                            else:
                                bug_logger.info(f"حساب بانکی موجود برای راننده {driver.name} پیدا شد - حساب: {bank_account.account_number}")
                            
                            pt.driver_bank_account = bank_account
                        else:
                            pt.driver_bank_account = None
                    else:
                        # در غیر این صورت، آن را None می‌کنیم
                        pt.driver_bank_account = None
                    
                    # ثبت زمان ورود خودرو (GateEntryTime)
                    today_jalali = jdatetime.date.today()
                    pt.actual_arrival_date = today_jalali
                    pt.save()
                    
                    bug_logger.info(f"اطلاعات راننده و زمان ورود برای حمل {transport_number} ثبت شد")
                    
                    # تغییر وضعیت به "در انتظار تخلیه"
                    pt.status = Transport.STATUS_AWAITING_UNLOADING
                    pt.save()
                    bug_logger.info(f"وضعیت حمل {transport_number} به 'در انتظار تخلیه' تغییر یافت")
                    
                    # تغییر وضعیت سفارش خرید به "در انتظار تحویل بار"
                    po = pt.purchase_order
                    if po and po.status == Order.STATUS_AWAITING_VEHICLE_ENTRY:
                        try:
                            po.transition(Order.STATUS_AWAITING_DELIVERY, user=request.user, note='ورود خودرو ثبت شد')
                            bug_logger.info(f"وضعیت سفارش {po.order_number} به 'در انتظار تحویل بار' تغییر یافت")
                            audit_logger.info(f"وضعیت سفارش {po.order_number} به دنبال ورود خودرو به‌روزرسانی شد")
                        except Exception as order_transition_err:
                            bug_logger.warning(f"خطا در تغییر وضعیت سفارش {po.order_number}: {order_transition_err}")
                            # اگر transition ناموفق بود، به صورت مستقیم تغییر می‌دهیم
                            po.status = Order.STATUS_AWAITING_DELIVERY
                            po.save()
                    
                    audit_logger.info(f"ورود خودرو ثبت شد - حمل: {transport_number} - راننده: {driver.name} - پلاک: {pt.plate_number}")
                    
                messages.success(request, 'اطلاعات راننده ثبت شد و ورود خودرو ثبت گردید.')
                return redirect(reverse('supply:carentrance'))
            except Exception as e:
                bug_logger.error(f"خطا در ثبت راننده برای حمل {transport_number}: {e}", exc_info=True)
                messages.error(request, f'خطا در ثبت اطلاعات راننده: {str(e)}')
        else:
            bug_logger.warning(f"فرم ثبت راننده نامعتبر برای حمل {transport_number}: {form.errors}")
            audit_logger.activity(f"فرم نامعتبر برای ثبت راننده حمل {transport_number}")
    else:
        # prefill if driver exists
        initial = {}
        # همیشه پلاک را از حمل بخوان (حتی اگر راننده وجود نداشته باشد)
        if pt.plate_number:
            initial['plate_number'] = pt.plate_number
        
        # پیش‌پر کردن وزن بارنامه
        if pt.waybill_weight:
            initial['waybill_weight'] = pt.waybill_weight
        
        if pt.driver:
            initial['phone'] = pt.driver.phone_number
            initial['name'] = pt.driver.name
            initial['national_id'] = getattr(pt.driver, 'national_id', '')
            # اگر پلاک در حمل وجود نداشت ولی در راننده وجود دارد، از آن استفاده کن
            if not pt.plate_number:
                initial['plate_number'] = pt.plate_number
            # اگر حساب بانکی در حمل وجود دارد، از آن استفاده کن
            if pt.driver_bank_account:
                initial['account'] = pt.driver_bank_account.account_number or ''
                initial['sheba'] = pt.driver_bank_account.shaba_number or ''
            else:
                # اگر حساب بانکی در حمل وجود نداشت، از حساب بانکی راننده استفاده کن
                financial_banking = FinancialBanking.objects.filter(person=pt.driver).first()
                if financial_banking:
                    bank_account = BankAccount.objects.filter(financial_banking=financial_banking).first()
                    if bank_account:
                        initial['account'] = bank_account.account_number or ''
                        initial['sheba'] = bank_account.shaba_number or ''
        # دریافت freight_payment_type از سفارش خرید (نه از transport)
        freight_payment_type = None
        if pt.allocation and pt.allocation.order and pt.allocation.order.freight_payment_type:
            freight_payment_type = pt.allocation.order.freight_payment_type
        elif pt.freight_payment_type:
            freight_payment_type = pt.freight_payment_type
        
        # ارسال freight_payment_type و driver به فرم برای تعیین required بودن فیلدهای حساب و شبا
        form = CarEntranceDriverForm(initial=initial, freight_payment_type=freight_payment_type, driver=pt.driver)

    # لیست مواد اولیه که در این ماشین (transport) هستند
    transport_raw_materials_list = []
    try:
        # دریافت مواد اولیه از RawMaterialInfo های این transport
        raw_material_infos = pt.raw_material_infos.select_related('raw_material').all()
        for rmi in raw_material_infos:
            if rmi.raw_material:
                # ساخت یک object ساده برای template
                class SimpleRawMaterial:
                    def __init__(self, raw_material_id, raw_material_name, allocated_quantity, weight_unit):
                        self.id = raw_material_id
                        self.name = raw_material_name
                        self.allocated_quantity = allocated_quantity
                        self.weight_unit = weight_unit
                
                # دریافت واحد وزن (نمایشی)
                try:
                    weight_unit_display = rmi.get_weight_unit_display()
                except:
                    weight_unit_display = rmi.weight_unit or 'کیلوگرم'
                
                transport_raw_materials_list.append(
                    SimpleRawMaterial(
                        rmi.raw_material.id,
                        rmi.raw_material.name,
                        rmi.allocated_quantity,
                        weight_unit_display
                    )
                )
    except Exception as e:
        bug_logger.error(f"خطا در خواندن raw_material_infos برای حمل {transport_number}: {e}", exc_info=True)
        transport_raw_materials_list = []
    
    # لیست کل سفارش (برای نمایش در بخش جداگانه)
    all_order_items_list = []
    purchase_order = pt.purchase_order  # استفاده از property
    if purchase_order:
        try:
            # استفاده از values برای انتخاب فقط فیلدهای مورد نیاز
            order_items_data = purchase_order.order_items.filter(
                raw_material__isnull=False
            ).values('id', 'raw_material__id', 'raw_material__name')
            
            # ساخت یک list ساده از داده‌ها برای template
            class SimpleOrderItem:
                def __init__(self, raw_material_id, raw_material_name):
                    self.raw_material = type('RawMaterial', (), {'id': raw_material_id, 'name': raw_material_name})()
            
            all_order_items_list = [
                SimpleOrderItem(item_data['raw_material__id'], item_data['raw_material__name'])
                for item_data in order_items_data
            ]
        except Exception as e:
            bug_logger.error(f"خطا در خواندن order_items برای حمل {transport_number}: {e}", exc_info=True)
            # در صورت خطا، list خالی برمی‌گردانیم
            all_order_items_list = []

    context = {
        'form': form,
        'pt': pt,
        'transport_raw_materials_list': transport_raw_materials_list,  # مواد اولیه این ماشین
        'all_order_items_list': all_order_items_list,  # کل سفارش
        'accessible_transport_fields': accessible_transport_fields,
        'accessible_po_fields': accessible_po_fields,
        'accessible_raw_material_fields': accessible_raw_material_fields,
        'accessible_person_fields': accessible_person_fields,
    }
    return render(request, 'car_entrance_register.html', context)




@login_required
def driver_lookup_api(request):
    """API برای جستجوی راننده با شماره تلفن (برای autofill)"""
    audit_logger.info("جستجوی راننده با شماره تلفن از طریق API")
    phone = request.GET.get('phone')
    if not phone:
        audit_logger.alert("درخواست جستجوی راننده بدون شماره تلفن")
        return JsonResponse({'error': 'phone_required'}, status=400)
    
    try:
        driver = Person.objects.filter(phone_number=phone, type='driver').first()
        if not driver:
            return JsonResponse({'found': False})
        
        # دریافت حساب بانکی راننده (اولین حساب بانکی)
        account_number = ''
        sheba_number = ''
        financial_banking = FinancialBanking.objects.filter(person=driver).first()
        if financial_banking:
            bank_account = BankAccount.objects.filter(financial_banking=financial_banking).first()
            if bank_account:
                account_number = bank_account.account_number or ''
                sheba_number = bank_account.shaba_number or ''
        
        data = {
            'found': True,
            'driver_id': driver.pk,
            'name': driver.name or '',
            'national_id': getattr(driver, 'national_id', '') or '',
            'phone': driver.phone_number or '',
            'account_number': account_number,
            'sheba_number': sheba_number,
        }
        
        bug_logger.debug(f"Driver lookup successful for phone {phone}: {data.get('name')}")
        return JsonResponse(data)
    except Exception as e:
        bug_logger.error(f"Driver lookup error for phone {phone}: {e}", exc_info=True)
        return JsonResponse({'error': 'lookup_failed'}, status=500)


@login_required
def get_driver_bank_accounts_api(request, driver_id):
    """API endpoint برای دریافت حساب‌های بانکی راننده"""
    from django.http import JsonResponse
    
    audit_logger.info(f"دریافت حساب‌های بانکی راننده از طریق API - ID: {driver_id}")
    try:
        driver = get_object_or_404(Person, pk=int(driver_id), type='driver')
        
        # دریافت FinancialBanking برای این راننده
        financial_banking = FinancialBanking.objects.filter(person=driver).first()
        
        accounts_data = []
        if financial_banking:
            bank_accounts = BankAccount.objects.filter(financial_banking=financial_banking).all()
            for account in bank_accounts:
                accounts_data.append({
                    'id': account.pk,
                    'account_number': account.account_number or '',
                    'shaba_number': account.shaba_number or '',
                    'bank_name': account.bank_name or '',
                    'display': f"{account.bank_name or 'بدون نام'} - {account.account_number or 'بدون شماره حساب'}"
                })
        
        return JsonResponse({
            'success': True,
            'accounts': accounts_data,
        })
    except (ValueError, TypeError) as e:
        bug_logger.error(f"Get driver bank accounts API error: {e}")
        return JsonResponse({'error': 'شناسه راننده نامعتبر است'}, status=400)
    except Exception as e:
        bug_logger.error(f"Get driver bank accounts API error: {e}", exc_info=True)
        return JsonResponse({'error': f'خطا در دریافت حساب‌های بانکی: {str(e)}'}, status=400)


class CarExitTable(TransportTable):
    """جدول برای خودروهای در انتظار تخلیه"""
    raw_materials = tables.Column(
        verbose_name='نام مواد اولیه',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if accessible_fields:
            if hasattr(self.base_columns, 'raw_materials'):
                self.base_columns['raw_materials'].visible = accessible_fields.get('purchase_order', False)
    
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
    
    def render_actions(self, record):
        """نمایش دکمه خروج ماشین - فقط برای حمل‌های تکمیل شده فعال است"""
        # خروج خودرو فقط بعد از تکمیل تحویل انبار (وضعیت completed) فعال است
        if record.status == Transport.STATUS_COMPLETED:
            exit_url = reverse('supply:carexit_mark_exited', args=[record.transport_number])
            return format_html(
                '<a href="{}" class="btn btn-warning btn-sm">خروج ماشین</a>',
                exit_url
            )
        else:
            return format_html(
                '<span class="badge badge-secondary" style="font-size:0.7rem">در انتظار تحویل انبار</span>'
            )
    
    class Meta(TransportTable.Meta):
        sequence = ('transport_number', 'vehicle_type', 'raw_materials', 'created_at', 'status', 'actions')
        fields = ('transport_number', 'vehicle_type', 'raw_materials', 'created_at', 'status', 'actions')


@login_required
def car_exit_list_view(request):
    """صفحه لیست خودروهای در انتظار تخلیه مخصوص نگهبان - خودروهایی که وارد شده‌اند و در حال فرآیند تخلیه هستند."""
    audit_logger.info("مشاهده صفحه خودروهای در انتظار تخلیه (نگهبان)")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_DRIVER.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه خروج خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_carentrance(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_carentrance(request.user)
    accessible_person_fields = get_accessible_person_fields_for_carentrance(request.user)
    
    try:
        # نمایش فقط حمل‌هایی که در وضعیت "در انتظار تخلیه" هستند
        # این حمل‌ها پس از ثبت ورود خودرو وارد این لیست می‌شوند
        # باید جهت ورودی داشته باشند (direction='inbound' یا transport_type='inbound')
        transports = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_UNLOADING
        ).filter(
            Q(direction='inbound') | Q(transport_type='inbound')
        ).select_related('allocation__order', 'allocation__order__customer', 'driver').order_by('-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های در انتظار تخلیه: {transports.count()}")
        
        table = CarExitTable(transports, prefix='exit-', accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 20}).configure(table)
        
        context = {
            'table': table,
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
        }
        return render(request, 'car_exit_list.html', context)
    except Exception as e:
        bug_logger.error(f"Car exit list error: {e}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست خودروهای در انتظار تخلیه.')
        return render(request, 'car_exit_list.html', {
            'table': CarExitTable([], prefix='exit-'),
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
        })


@login_required
def mark_vehicle_exited_view(request, transport_number):
    """ثبت خروج خودرو از کارخانه - فقط برای حمل‌های تکمیل شده"""
    audit_logger.info(f"ثبت خروج خودرو برای حمل {transport_number}")
    pt = get_object_or_404(Transport, transport_number=transport_number)
    
    # فقط حمل‌های تکمیل شده می‌توانند خارج شوند
    if pt.status != Transport.STATUS_COMPLETED:
        audit_logger.activity(f"تلاش برای خروج خودرو با وضعیت نامعتبر - حمل {transport_number}: وضعیت {pt.status}")
        messages.error(request, 'این خودرو هنوز آماده خروج نیست. باید ابتدا فرآیند تحویل انبار تکمیل شود.')
        return redirect(reverse('supply:carexit'))
    
    try:
        with transaction.atomic():
            # ثبت زمان خروج
            today_jalali = jdatetime.date.today()
            pt.delivery_date = today_jalali  # استفاده از delivery_date برای ثبت زمان خروج نهایی
            pt.save(update_fields=['delivery_date'])
            
            bug_logger.info(f"زمان خروج خودرو برای حمل {transport_number} ثبت شد")
            audit_logger.info(f"خروج خودرو ثبت شد - حمل: {transport_number} - راننده: {pt.driver.name if pt.driver else 'نامشخص'} - پلاک: {pt.plate_number or 'ثبت نشده'}")
            
        messages.success(request, f'خروج خودرو با شماره حمل {transport_number} ثبت شد.')
    except Exception as e:
        bug_logger.error(f"خطا در ثبت خروج خودرو برای حمل {transport_number}: {e}")
        messages.error(request, 'خطا در ثبت خروج خودرو.')
    
    return redirect(reverse('supply:carexit'))
