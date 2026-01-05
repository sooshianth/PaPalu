from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm, inlineformset_factory, BaseInlineFormSet
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from decimal import Decimal, ROUND_HALF_UP
import logging
from core.logging_levels import *
from django_tables2 import RequestConfig

from core.OrderFolder.OrderModel import Order, OrderStatusLog
from core.OrderFolder.OrderItemModel import OrderItem
from core.PersonFolder.PersonModel import Person
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from django.contrib.auth import get_user_model

User = get_user_model()

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_procurement_purchase_order_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل Order (سفارش خرید)"""
    return {
        'order_number': user_can_access_field(user, Order, 'order_number', 'view'),
        'customer': user_can_access_field(user, Order, 'customer', 'view'),  # supplier در Order به نام customer است
        'status': user_can_access_field(user, Order, 'status', 'view'),
        'freight_payment_type': user_can_access_field(user, Order, 'freight_payment_type', 'view'),
        'subtotal_without_freight': user_can_access_field(user, Order, 'subtotal_without_freight', 'view'),
        'freight_cost': user_can_access_field(user, Order, 'freight_cost', 'view'),
        'vat_percentage': user_can_access_field(user, Order, 'vat_percentage', 'view'),
        'payment_confirmed': user_can_access_field(user, Order, 'payment_confirmed', 'view'),
        'external_system_id': user_can_access_field(user, Order, 'external_system_id', 'view'),
        'registered_by': user_can_access_field(user, Order, 'registered_by', 'view'),
        'created_at': user_can_access_field(user, Order, 'created_at', 'view'),
        'updated_at': user_can_access_field(user, Order, 'updated_at', 'view'),
    }


def get_accessible_procurement_purchase_order_material_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل OrderItem"""
    return {
        'raw_material': user_can_access_field(user, OrderItem, 'raw_material', 'view'),
        'quantity': user_can_access_field(user, OrderItem, 'quantity', 'view'),
        'weight_unit': user_can_access_field(user, OrderItem, 'weight_unit', 'view'),
        'notes': user_can_access_field(user, OrderItem, 'notes', 'view'),
        'unit_price': user_can_access_field(user, OrderItem, 'unit_price', 'view'),
        'total_purchase_cost': user_can_access_field(user, OrderItem, 'total_purchase_cost', 'view'),
        'vat_percent': user_can_access_field(user, OrderItem, 'vat_percent', 'view'),
        'freight_cost': user_can_access_field(user, OrderItem, 'freight_cost', 'view'),
        'total_purchase_cost': user_can_access_field(user, OrderItem, 'total_purchase_cost', 'view'),
        'external_allocation_id': user_can_access_field(user, OrderItem, 'external_allocation_id', 'view'),
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
        model = Order
        fields = [
            'customer', 'freight_payment_type',
            'subtotal_without_freight', 'freight_cost',
            'external_system_id'
        ]
        labels = {
            'customer': 'تأمین‌کننده',
            'freight_payment_type': 'نوع پرداخت کرایه',
            'subtotal_without_freight': 'جمع بدون کرایه',
            'freight_cost': 'هزینه کرایه',
            'external_system_id': 'شناسه یکتا در سیستم دامپروش/کی‌اچ/انبار/لبه‌ژنت',
        }
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.Select(attrs={'class': 'form-control'}),
            'subtotal_without_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'freight_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'external_system_id': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # استخراج instance قبل از super().__init__
        instance = kwargs.get('instance', None)
        
        # اگر instance وجود دارد و customer دارد، مقدار initial را تنظیم کن
        if instance and instance.pk and instance.customer:
            # تنظیم initial قبل از super().__init__ تا Django از آن استفاده کند
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            kwargs['initial']['customer'] = f"{instance.customer.name} ({instance.customer.national_id})"
            kwargs['initial']['supplier_id'] = instance.customer.national_id
        
        # حذف customer از fields قبل از super().__init__ تا Django آن را از instance نگیرد
        # این کار را با تغییر Meta.fields انجام می‌دهیم
        original_fields = self._meta.fields if hasattr(self, '_meta') else None
        
        super().__init__(*args, **kwargs)
        
        # تبدیل customer (supplier) به autocomplete
        self.fields['customer'] = forms.CharField(
            required=True,
            label='تأمین‌کننده',
            widget=forms.TextInput(attrs={
                'class': 'form-control supplier-autocomplete',
                'placeholder': 'جستجوی تأمین‌کننده...',
                'autocomplete': 'off'
            })
        )
        
        # اضافه کردن فیلد مخفی برای ذخیره ID تأمین‌کننده
        self.fields['supplier_id'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput()
        )
        
        # اگر instance وجود دارد (ویرایش)، مقدار اولیه را تنظیم کن
        if instance and instance.pk and instance.customer:
            customer_display = f"{instance.customer.name} ({instance.customer.national_id})"
            # تنظیم initial برای نمایش در فرم
            self.initial['customer'] = customer_display
            self.initial['supplier_id'] = instance.customer.national_id
            # همچنین مقدار value را مستقیماً تنظیم کن
            self.fields['customer'].initial = customer_display
            self.fields['supplier_id'].initial = instance.customer.national_id
        
        # Lock financial fields if payment confirmed
        if self.instance and self.instance.payment_confirmed:
            for f in ['subtotal_without_freight', 'freight_cost']:
                if f in self.fields:
                    self.fields[f].disabled = True
        
        # هزینه کرایه همیشه read-only است
        if 'freight_cost' in self.fields:
            self.fields['freight_cost'].widget.attrs['readonly'] = True
            self.fields['freight_cost'].widget.attrs['style'] = 'background-color: #f5f5f5; cursor: not-allowed;'
    
    def clean(self):
        cleaned_data = super().clean()
        # تبدیل supplier_id به customer
        supplier_id = cleaned_data.get('supplier_id', '').strip()
        supplier_text = cleaned_data.get('customer', '').strip()
        
        # اگر supplier_id در cleaned_data نیست، از data اصلی بگیر
        if not supplier_id and hasattr(self, 'data'):
            supplier_id = self.data.get('supplier_id', '').strip()
            if supplier_id:
                cleaned_data['supplier_id'] = supplier_id
        
        # اگر supplier_id وجود ندارد اما متن وارد شده، سعی کن از متن استخراج کن
        if not supplier_id and supplier_text:
            # استخراج کد ملی از متن (فرمت: "نام (کد ملی)")
            import re
            match = re.search(r'\((\d+)\)', supplier_text)
            if match:
                supplier_id = match.group(1)
                cleaned_data['supplier_id'] = supplier_id
        
        if not supplier_id:
            self.add_error('customer', 'لطفاً یک تأمین‌کننده را از لیست انتخاب کنید.')
            return cleaned_data
        
        try:
            supplier = Person.objects.get(national_id=supplier_id, type='supplier')
            cleaned_data['customer'] = supplier
        except Person.DoesNotExist:
            self.add_error('customer', 'تأمین‌کننده انتخاب شده یافت نشد.')
        
        return cleaned_data


class ProcurementPurchaseOrderMaterialForm(ModelForm):
    class Meta:
        model = OrderItem
        fields = [
            'raw_material', 'quantity', 'weight_unit', 'notes',
            'unit_price', 'total_purchase_cost',
            'vat_percent', 'freight_cost',
            'total_purchase_cost', 'external_allocation_id'
        ]
        labels = {
            'raw_material': 'ماده اولیه',
            'quantity': 'مقدار',
            'weight_unit': 'واحد',
            'notes': 'توضیحات',
            'unit_price': 'قیمت واحد',
            'total_purchase_cost': 'قیمت کل',
            'vat_percent': 'مالیات بر ارزش افزوده',
            'freight_cost': 'بهای تمام شده کرایه خرید',
            'external_allocation_id': 'شناسه تخصیص',
        }
        widgets = {
            'raw_material': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'weight_unit': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_purchase_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': True}),
            'vat_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'external_allocation_id': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
        }

    def __init__(self, *args, **kwargs):
        # استخراج instance قبل از super().__init__
        instance = kwargs.get('instance', None)
        
        # اگر instance وجود دارد و raw_material دارد، مقدار initial را تنظیم کن
        if instance and instance.pk and instance.raw_material:
            # تنظیم initial قبل از super().__init__ تا Django از آن استفاده کند
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            kwargs['initial']['raw_material'] = f"{instance.raw_material.raw_material_id or ''} - {instance.raw_material.name}"
            kwargs['initial']['raw_material_id'] = str(instance.raw_material.id)
        
        super().__init__(*args, **kwargs)
        
        # تبدیل raw_material به autocomplete
        self.fields['raw_material'] = forms.CharField(
            required=False,  # در clean بررسی می‌کنیم که آیا فرم خالی است یا نه
            label='ماده اولیه',
            widget=forms.TextInput(attrs={
                'class': 'form-control raw-material-autocomplete',
                'placeholder': 'جستجوی ماده اولیه...',
                'autocomplete': 'off'
            })
        )
        
        # اضافه کردن فیلد مخفی برای ذخیره ID ماده اولیه
        self.fields['raw_material_id'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput()
        )
        
        # اگر instance وجود دارد (ویرایش)، مقدار اولیه را تنظیم کن
        if instance and instance.pk and instance.raw_material:
            raw_material_display = f"{instance.raw_material.raw_material_id or ''} - {instance.raw_material.name}"
            # تنظیم initial برای نمایش در فرم
            self.initial['raw_material'] = raw_material_display
            self.initial['raw_material_id'] = str(instance.raw_material.id)
            # همچنین مقدار value را مستقیماً تنظیم کن
            self.fields['raw_material'].initial = raw_material_display
            self.fields['raw_material_id'].initial = str(instance.raw_material.id)
        
        # کرایه تمام شده همیشه read-only است
        if 'freight_cost' in self.fields:
            self.fields['freight_cost'].widget.attrs['readonly'] = True
            self.fields['freight_cost'].widget.attrs['style'] = 'background-color: #f5f5f5; cursor: not-allowed;'
        
        # واحد به صورت dropdown که بعداً با JavaScript پر می‌شود
        self.fields['weight_unit'].widget = forms.Select(attrs={'class': 'form-control material-unit-select'})
        # اجازه دادن به تمام choices ممکن (هم value و هم display name)
        # این کار را در clean_weight_unit انجام می‌دهیم
        self.fields['weight_unit'].choices = OrderItem.WEIGHT_UNIT_CHOICES + [
            ('کیلوگرم', 'کیلوگرم'),
            ('تن', 'تن'),
            ('کیسه', 'کیسه'),
            ('عدد', 'عدد'),
        ]
    
    def clean_weight_unit(self):
        """تبدیل display name به value قبل از validation"""
        weight_unit = self.cleaned_data.get('weight_unit')
        if not weight_unit:
            return weight_unit
        
        # mapping display name به value
        display_to_value = {
            'کیلوگرم': 'kg',
            'تن': 'ton',
            'کیسه': 'bag',
            'عدد': 'piece',
        }
        
        # اگر display name است، به value تبدیل کن
        if weight_unit in display_to_value:
            return display_to_value[weight_unit]
        
        # اگر value است، همان را برگردان
        if weight_unit in ['kg', 'ton', 'bag', 'piece']:
            return weight_unit
        
        # اگر هیچکدام نبود، خطا بده
        return weight_unit
    
    def clean(self):
        """اعتبارسنجی: واحد باید با واحد اصلی یا فرعی ماده اولیه مطابقت داشته باشد"""
        cleaned_data = super().clean()
        
        # بررسی اینکه آیا فرم برای حذف علامت خورده است
        if self.cleaned_data.get('DELETE', False):
            return cleaned_data
        
        # دریافت raw_material_id مستقیماً از POST data
        raw_material_id = None
        raw_material_text = None
        
        if hasattr(self, 'data') and self.data:
            # استفاده از add_prefix برای ساخت نام کامل فیلد
            if hasattr(self, 'add_prefix'):
                field_name = self.add_prefix('raw_material_id')
                raw_material_id = self.data.get(field_name, '').strip() or None
            
            # اگر پیدا نشد، با prefix دستی امتحان کن
            if not raw_material_id and hasattr(self, 'prefix') and self.prefix:
                field_name = f'{self.prefix}-raw_material_id'
                raw_material_id = self.data.get(field_name, '').strip() or None
            
            # اگر هنوز پیدا نشد، همه key های مربوط را بررسی کن
            if not raw_material_id:
                for key in self.data.keys():
                    if key.endswith('-raw_material_id'):
                        if hasattr(self, 'prefix') and self.prefix:
                            if key.startswith(self.prefix + '-'):
                                raw_material_id = self.data.get(key, '').strip() or None
                                if raw_material_id:
                                    break
                        else:
                            raw_material_id = self.data.get(key, '').strip() or None
                            if raw_material_id:
                                break
            
            # دریافت raw_material_text برای fallback
            if hasattr(self, 'add_prefix'):
                field_name = self.add_prefix('raw_material')
                raw_material_text = self.data.get(field_name, '').strip() or None
        
        # اگر raw_material_id نداریم، از cleaned_data بگیر
        if not raw_material_id:
            raw_material_id_value = cleaned_data.get('raw_material_id', '')
            raw_material_id = raw_material_id_value.strip() if isinstance(raw_material_id_value, str) and raw_material_id_value.strip() else None
        
        # اگر هنوز raw_material_id نداریم و instance وجود دارد، از instance بگیر
        if not raw_material_id and self.instance and self.instance.pk and self.instance.raw_material:
            raw_material_id = str(self.instance.raw_material.id)
        
        # اگر raw_material_text نداریم، از cleaned_data بگیر
        if not raw_material_text:
            raw_material_value = cleaned_data.get('raw_material', '')
            raw_material_text = raw_material_value.strip() if isinstance(raw_material_value, str) and raw_material_value.strip() else None
        
        # اگر raw_material_text نداریم و instance وجود دارد، از instance بگیر
        if not raw_material_text and self.instance and self.instance.pk and self.instance.raw_material:
            raw_material_text = f"{self.instance.raw_material.raw_material_id or ''} - {self.instance.raw_material.name}"
        
        weight_unit = cleaned_data.get('weight_unit')
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        total_purchase_cost = cleaned_data.get('total_purchase_cost')
        
        # اگر فرم خالی است (بدون raw_material و quantity)، آن را نادیده بگیر
        if not raw_material_text and not raw_material_id and not quantity:
            cleaned_data = {}
            return cleaned_data
        
        # تبدیل raw_material_id به raw_material
        if not raw_material_id and raw_material_text:
            # استخراج ID از متن
            import re
            # سعی کن ID عددی را از ابتدای متن پیدا کن
            match = re.match(r'^(\d+)', raw_material_text)
            if match:
                potential_id = match.group(1)
                try:
                    test_rm = RawMaterial.objects.get(id=potential_id, status='active')
                    raw_material_id = str(test_rm.id)
                except (RawMaterial.DoesNotExist, ValueError):
                    pass
            
            # اگر هنوز پیدا نشد، سعی کن از raw_material_id در متن پیدا کن
            if not raw_material_id:
                raw_id_match = re.search(r'RM-\d+-\d+', raw_material_text)
                if raw_id_match:
                    try:
                        test_rm = RawMaterial.objects.get(raw_material_id=raw_id_match.group(0), status='active')
                        raw_material_id = str(test_rm.id)
                    except (RawMaterial.DoesNotExist, ValueError):
                        pass
        
        # اگر هنوز raw_material_id نداریم
        if not raw_material_id:
            if not raw_material_text and not quantity:
                cleaned_data = {}
                return cleaned_data
            self.add_error('raw_material', 'لطفاً یک ماده اولیه را از لیست انتخاب کنید.')
            return cleaned_data
        
        # تبدیل raw_material_id به RawMaterial object
        try:
            raw_material = RawMaterial.objects.get(id=raw_material_id, status='active')
            # حذف raw_material از cleaned_data اگر string است و جایگزین با object
            cleaned_data['raw_material'] = raw_material
            cleaned_data['raw_material_id'] = raw_material_id
        except (RawMaterial.DoesNotExist, ValueError):
            self.add_error('raw_material', 'ماده اولیه انتخاب شده یافت نشد.')
            return cleaned_data
        
        # اعتبارسنجی واحد - weight_unit قبلاً در clean_weight_unit به value تبدیل شده است
        # حالا فقط بررسی می‌کنیم که آیا با واحدهای ماده اولیه مطابقت دارد یا نه
        if raw_material and weight_unit:
            # Get allowed units from raw material (به value تبدیل شده)
            allowed_order_item_units = []  # لیست واحدهای OrderItem که مجاز هستند
            # تبدیل واحدهای RawMaterial به واحد OrderItem
            raw_to_order_mapping = {
                'gr': 'kg',   # گرم به کیلوگرم
                'm3': 'kg',   # متر مکعب به کیلوگرم
                'ltr': 'kg',  # لیتر به کیلوگرم
                'cc': 'kg',   # میلی لیتر به کیلوگرم
                'kg': 'kg',
                'ton': 'ton',
                'bag': 'bag',
                'piece': 'piece',
            }
            
            if raw_material.primary_unit:
                raw_unit = raw_material.primary_unit
                order_unit = raw_to_order_mapping.get(raw_unit, 'kg')
                if order_unit not in allowed_order_item_units:
                    allowed_order_item_units.append(order_unit)
                    
            if raw_material.secondary_unit:
                raw_unit = raw_material.secondary_unit
                order_unit = raw_to_order_mapping.get(raw_unit, 'kg')
                if order_unit not in allowed_order_item_units:
                    allowed_order_item_units.append(order_unit)
            
            # اگر هیچ واحدی وجود نداشت، پیش‌فرض کیلوگرم
            if not allowed_order_item_units:
                allowed_order_item_units = ['kg']
            
            # بررسی اینکه weight_unit (که حالا value است) در لیست مجاز است یا نه
            if weight_unit not in allowed_order_item_units:
                # نمایش display name برای خطا
                primary_display = raw_material.get_primary_unit_display() if raw_material.primary_unit else ''
                secondary_display = raw_material.get_secondary_unit_display() if raw_material.secondary_unit else ''
                allowed_display = [d for d in [primary_display, secondary_display] if d]
                if not allowed_display:
                    allowed_display = ['کیلوگرم']
                self.add_error('weight_unit', f'واحد انتخاب شده برای ماده اولیه "{raw_material.name}" معتبر نیست. واحدهای مجاز: {" یا ".join(allowed_display)}')
            else:
                # اطمینان از اینکه weight_unit در cleaned_data است
                cleaned_data['weight_unit'] = weight_unit
        
        # Validate total price calculation
        if quantity and unit_price:
            calculated_total = quantity * unit_price
            
            # اضافه کردن مالیات به قیمت کل (اگر مالیات وجود داشته باشد)
            vat_percent = cleaned_data.get('vat_percent')
            # اگر در cleaned_data نبود، از data اصلی بگیر
            if not vat_percent and hasattr(self, 'data') and self.data:
                if hasattr(self, 'add_prefix'):
                    field_name = self.add_prefix('vat_percent')
                    vat_value = self.data.get(field_name, '').strip() or None
                    if vat_value:
                        try:
                            vat_percent = Decimal(str(vat_value))
                        except (ValueError, TypeError):
                            vat_percent = None
            
            if vat_percent:
                try:
                    vat_percent_decimal = Decimal(str(vat_percent))
                    if vat_percent_decimal > 0:
                        vat_amount = (calculated_total * vat_percent_decimal) / Decimal('100')
                        calculated_total = calculated_total + vat_amount
                except (ValueError, TypeError):
                    # اگر مالیات معتبر نبود، فقط قیمت کل را بدون مالیات محاسبه کن
                    pass
            
            # گرد کردن به 2 رقم اعشار برای مطابقت با محدودیت فیلد
            calculated_total = calculated_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            cleaned_data['total_purchase_cost'] = calculated_total
            if total_purchase_cost and abs(float(total_purchase_cost) - float(calculated_total)) > 0.01:
                # فقط هشدار می‌دهیم، مقدار را اصلاح می‌کنیم
                pass
        
        # اگر quantity required است و وجود ندارد، خطا بده
        if not quantity:
            self.add_error('quantity', 'این فیلد لازم است.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """ذخیره فرم با تبدیل raw_material_id به raw_material"""
        # اطمینان از اینکه raw_material یک RawMaterial object است
        raw_material = self.cleaned_data.get('raw_material')
        if not isinstance(raw_material, RawMaterial):
            # اگر raw_material یک string است یا نیست، از raw_material_id استفاده کن
            raw_material_id_value = self.cleaned_data.get('raw_material_id', '')
            raw_material_id = raw_material_id_value.strip() if isinstance(raw_material_id_value, str) else ''
            if raw_material_id:
                try:
                    self.cleaned_data['raw_material'] = RawMaterial.objects.get(id=raw_material_id, status='active')
                except (RawMaterial.DoesNotExist, ValueError):
                    # اگر پیدا نشد، خطا بده
                    from django.core.exceptions import ValidationError
                    raise ValidationError('ماده اولیه انتخاب شده یافت نشد.')
        
        return super().save(commit=commit)


class MaterialFormSetBase(BaseInlineFormSet):
    """FormSet سفارشی که فرم‌های خالی را نادیده می‌گیرد"""
    
    def clean(self):
        """حذف فرم‌های خالی از اعتبارسنجی"""
        if any(self.errors):
            return
        
        # حذف فرم‌های خالی از cleaned_data
        for form in self.forms:
            if form in self.deleted_forms:
                continue
            
            cleaned_data = form.cleaned_data
            if cleaned_data:
                # اگر فرم دارای id است (یعنی instance موجود است)، آن را نگه دار
                if cleaned_data.get('id'):
                    continue
                
                # بررسی اینکه آیا فرم خالی است
                raw_material_id_value = cleaned_data.get('raw_material_id', '')
                raw_material_id = raw_material_id_value.strip() if isinstance(raw_material_id_value, str) else ''
                raw_material_value = cleaned_data.get('raw_material', '')
                raw_material_text = raw_material_value.strip() if isinstance(raw_material_value, str) else ''
                quantity = cleaned_data.get('quantity')
                
                # اگر همه فیلدهای اصلی خالی هستند، فرم را خالی در نظر بگیر
                if not raw_material_id and not raw_material_text and not quantity:
                    # حذف این فرم از cleaned_data
                    form.cleaned_data = {}
        
        super().clean()


MaterialFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=ProcurementPurchaseOrderMaterialForm,
    formset=MaterialFormSetBase,
    fields=[
        'raw_material', 'quantity', 'weight_unit', 'notes',
        'unit_price', 'total_purchase_cost',
        'vat_percent', 'freight_cost',
        'external_allocation_id'
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
    
    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    supplier_filter = request.GET.get('supplier', '')
    
    try:
        from supply.tables import ProcurementPurchaseOrderTable
        open_orders = Order.objects.filter(
            order_type='purchase'
        ).exclude(
            status=Order.STATUS_COMPLETED
        ).select_related('customer', 'registered_by').prefetch_related(
            'order_items__raw_material'
        )
        
        completed_orders = Order.objects.filter(
            order_type='purchase',
            status=Order.STATUS_COMPLETED
        ).select_related('customer', 'registered_by').prefetch_related(
            'order_items__raw_material'
        )
        
        # اعمال جستجو
        if search_query:
            open_orders = open_orders.filter(
                Q(order_number__icontains=search_query) |
                Q(customer__name__icontains=search_query) |
                Q(registered_by__username__icontains=search_query)
            )
            completed_orders = completed_orders.filter(
                Q(order_number__icontains=search_query) |
                Q(customer__name__icontains=search_query) |
                Q(registered_by__username__icontains=search_query)
            )
        
        # اعمال فیلتر وضعیت
        if status_filter:
            open_orders = open_orders.filter(status=status_filter)
            completed_orders = completed_orders.filter(status=status_filter)
        
        # اعمال فیلتر تامین‌کننده
        if supplier_filter:
            open_orders = open_orders.filter(customer__national_id=supplier_filter)
            completed_orders = completed_orders.filter(customer__national_id=supplier_filter)
        
        open_orders = open_orders.order_by('-created_at')
        completed_orders = completed_orders.order_by('-created_at')
        
        # Prepare table accessible fields dict
        # materials_list requires both OrderItem and raw material access
        table_accessible_fields = {
            'order_number': accessible_po_fields.get('order_number', False),
            'status': accessible_po_fields.get('status', False),
            'materials_list': (
                accessible_po_material_fields.get('raw_material', False) and
                accessible_raw_material_fields.get('name', False)
            ),
            'supplier': (
                accessible_po_fields.get('customer', False) and
                accessible_person_fields.get('name', False)
            ),
            'created_by': accessible_po_fields.get('registered_by', False),
            'created_at': accessible_po_fields.get('created_at', False),
            'total_weight': (
                accessible_po_material_fields.get('quantity', False) and
                accessible_po_material_fields.get('weight_unit', False)
            ),
        }
        
        # Create tables
        open_table = ProcurementPurchaseOrderTable(open_orders, prefix='open-', accessible_fields=table_accessible_fields)
        completed_table = ProcurementPurchaseOrderTable(completed_orders, prefix='completed-', accessible_fields=table_accessible_fields)
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 15}).configure(open_table)
        RequestConfig(request, paginate={'per_page': 15}).configure(completed_table)
        
        # دریافت لیست تامین‌کنندگان برای dropdown
        from core.PersonFolder.PersonModel import Person
        suppliers = Person.objects.filter(type='supplier').order_by('name')
        
        context = {
            'open_table': open_table,
            'completed_table': completed_table,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
            'search_query': search_query,
            'status_filter': status_filter,
            'supplier_filter': supplier_filter,
            'suppliers': suppliers,
        }
        return render(request, 'purchase/procurement_order_list.html', context)
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
            'total_weight': False,
        }
        open_table = ProcurementPurchaseOrderTable([], prefix='open-', accessible_fields=table_accessible_fields)
        completed_table = ProcurementPurchaseOrderTable([], prefix='completed-', accessible_fields=table_accessible_fields)
        return render(request, 'purchase/procurement_order_list.html', {
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
        'customer': user_can_access_field(request.user, Order, 'customer', 'edit'),
        'freight_payment_type': user_can_access_field(request.user, Order, 'freight_payment_type', 'edit'),
        'subtotal_without_freight': user_can_access_field(request.user, Order, 'subtotal_without_freight', 'edit'),
        'freight_cost': user_can_access_field(request.user, Order, 'freight_cost', 'edit'),
        'external_system_id': user_can_access_field(request.user, Order, 'external_system_id', 'edit'),
    }
    
    accessible_po_material_fields = {
        'raw_material': user_can_access_field(request.user, OrderItem, 'raw_material', 'edit'),
        'quantity': user_can_access_field(request.user, OrderItem, 'quantity', 'edit'),
        'weight_unit': user_can_access_field(request.user, OrderItem, 'weight_unit', 'edit'),
        'notes': user_can_access_field(request.user, OrderItem, 'notes', 'edit'),
        'unit_price': user_can_access_field(request.user, OrderItem, 'unit_price', 'edit'),
        'total_purchase_cost': user_can_access_field(request.user, OrderItem, 'total_purchase_cost', 'edit'),
        'vat_percent': user_can_access_field(request.user, OrderItem, 'vat_percent', 'edit'),
        'freight_cost': user_can_access_field(request.user, OrderItem, 'freight_cost', 'edit'),
        'external_allocation_id': user_can_access_field(request.user, OrderItem, 'external_allocation_id', 'edit'),
    }
    
    try:
        if request.method == 'POST':
            form = ProcurementPurchaseOrderForm(request.POST, request.FILES)
            if form.is_valid():
                with transaction.atomic():
                    po = form.save(commit=False)
                    po.order_type = 'purchase'
                    po.status = Order.STATUS_DRAFT  # تنظیم وضعیت به پیش‌نویس
                    po.registered_by = request.user
                    
                    # محاسبه خودکار subtotal_without_freight از مجموع total_purchase_cost اقلام
                    material_formset = MaterialFormSet(request.POST, prefix='mat')
                    if material_formset.is_valid():
                        # محاسبه مجموع قبل از ذخیره
                        total_subtotal = Decimal('0')
                        for material_form in material_formset:
                            if material_form.cleaned_data and not material_form.cleaned_data.get('DELETE', False):
                                # بررسی اینکه آیا فرم خالی است
                                raw_material_id_value = material_form.cleaned_data.get('raw_material_id', '')
                                raw_material_id = raw_material_id_value.strip() if isinstance(raw_material_id_value, str) else ''
                                raw_material_value = material_form.cleaned_data.get('raw_material', '')
                                raw_material_text = raw_material_value.strip() if isinstance(raw_material_value, str) else ''
                                quantity = material_form.cleaned_data.get('quantity')
                                
                                # اگر فرم خالی است، آن را نادیده بگیر
                                if not raw_material_id and not raw_material_text and not quantity:
                                    continue
                                
                                total_purchase_cost = material_form.cleaned_data.get('total_purchase_cost')
                                if total_purchase_cost:
                                    total_subtotal += Decimal(str(total_purchase_cost))
                        
                        po.subtotal_without_freight = total_subtotal
                        po.save()  # triggers order_number generation, status defaults to DRAFT
                        
                        # Create initial status log for DRAFT
                        OrderStatusLog.objects.create(
                            order=po,
                            old_status='',
                            new_status=po.status,
                            changed_by=request.user,
                            note='ایجاد سفارش خرید'
                        )
                        
                        material_formset.instance = po
                        material_formset.save()
                        
                        # تغییر وضعیت به "در انتظار تعریف حمل" بعد از ذخیره مواد اولیه
                        if po.status == Order.STATUS_DRAFT:
                            po.transition(Order.STATUS_AWAITING_TRANSPORT_DEFINITION, user=request.user, note='مواد اولیه ثبت شد')
                    else:
                        bug_logger.warning(f"Material formset invalid on create: {material_formset.errors}")
                        messages.error(request, 'مواد اولیه تکراری یا نامعتبر هستند. لطفاً خطاهای فرم را بررسی و اصلاح کنید.')
                        # Rollback parent creation to avoid orphan PO
                        try:
                            po.delete()
                        except Exception:
                            pass
                        return render(request, 'purchase/create_procurement_order.html', {
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
        return render(request, 'purchase/create_procurement_order.html', {
            'form': form,
            'material_formset': material_formset,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        })
    except Exception as e:
        bug_logger.error(f"Create procurement PO error: {e}")
        messages.error(request, 'خطا در ایجاد سفارش خرید.')
        return render(request, 'purchase/create_procurement_order.html', {
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
    from core.TransportFolder.TransportModel import Transport
    
    # ابتدا سعی می‌کنیم سفارش را با order_type='purchase' پیدا کنیم
    try:
        po = Order.objects.get(order_number=order_number, order_type='purchase')
    except Order.DoesNotExist:
        # اگر پیدا نشد، سعی می‌کنیم بدون فیلتر order_type پیدا کنیم
        try:
            po = Order.objects.get(order_number=order_number)
            # اگر order_type null است یا purchase نیست، خطا می‌دهیم
            if po.order_type is None:
                bug_logger.warning(f"سفارش {order_number} دارای order_type null است")
                messages.error(request, f'سفارش {order_number} دارای نوع سفارش مشخصی نیست. لطفاً نوع سفارش را تنظیم کنید.')
                return redirect('supply:purchase_transport_list')
            elif po.order_type != 'purchase':
                bug_logger.warning(f"سفارش {order_number} از نوع {po.order_type} است نه purchase")
                messages.error(request, f'سفارش {order_number} یک سفارش خرید نیست.')
                return redirect('supply:purchase_transport_list')
        except Order.DoesNotExist:
            # اگر اصلاً سفارش پیدا نشد
            bug_logger.error(f"سفارش {order_number} یافت نشد")
            messages.error(request, f'سفارش {order_number} یافت نشد.')
            return redirect('supply:purchase_transport_list')
    materials = po.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
    logs = po.status_logs.all().order_by('-changed_at')
    log_table = ProcurementPurchaseOrderStatusLogTable(logs)
    RequestConfig(request, paginate=False).configure(log_table)
    can_edit_financial = not po.payment_confirmed
    can_delete = po.can_delete()  # محاسبه مقدار can_delete برای استفاده در template
    
    # Get transports for this purchase order
    transports = Transport.objects.filter(allocation__order=po).order_by('-created_at')
    
    # Create tables for materials and transports
    from supply.tables import PurchaseOrderMaterialTable, PurchaseOrderTransportTable
    material_table = PurchaseOrderMaterialTable(materials)
    RequestConfig(request, paginate=False).configure(material_table)
    transport_table = PurchaseOrderTransportTable(transports)
    RequestConfig(request, paginate={'per_page': 10}).configure(transport_table)
    
    # Get allowed next statuses for workflow transitions
    allowed_next_statuses = po.WORKFLOW_ALLOWED.get(po.status, set())
    next_status_choices = [(code, label) for code, label in po.STATUS_CHOICES if code in allowed_next_statuses]
    
    return render(request, 'purchase/procurement_purchase_detail.html', {
        'po': po,
        'material_table': material_table,
        'logs': logs,
        'log_table': log_table,
        'can_edit_financial': can_edit_financial,
        'can_delete': can_delete,
        'next_status_choices': next_status_choices,
        'transport_table': transport_table,
    })


@login_required
def edit_procurement_purchase_order_view(request, order_number):
    """ویرایش سفارش خرید (فقط قبل از تایید پرداخت برای داده مالی)"""
    audit_logger.info(f"ویرایش سفارش خرید {order_number}")
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    if po.status == Order.STATUS_COMPLETED:
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
        return render(request, 'purchase/edit_procurement_order.html', {
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
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
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
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
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
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    if po.payment_confirmed:
        messages.info(request, 'پرداخت قبلاً تایید شده است.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        po.payment_confirmed = True
        po.save(update_fields=['payment_confirmed'])
        OrderStatusLog.objects.create(
            order=po,
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


@login_required
@require_http_methods(["GET"])
def supplier_search_api(request):
    """
    API endpoint برای جستجوی تامین‌کننده‌ها
    """
    audit_logger.info("جستجوی تامین‌کننده از طریق API")
    query = request.GET.get('q', '').strip()
    
    if not query:
        # اگر کوئری خالی است، 20 تامین‌کننده اخیر را برگردان
        suppliers = Person.objects.filter(
            type='supplier'
        ).order_by('name')[:20]
    else:
        # فیلتر کردن تامین‌کننده‌ها
        suppliers = Person.objects.filter(
            type='supplier'
        ).filter(
            Q(name__icontains=query) | Q(national_id__icontains=query)
        ).order_by('name')[:20]
    
    results = []
    for supplier in suppliers:
        results.append({
            'id': supplier.national_id,
            'text': f"{supplier.name} ({supplier.national_id})"
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def raw_material_search_api(request):
    """
    API endpoint برای جستجوی مواد اولیه
    """
    audit_logger.info("جستجوی مواد اولیه از طریق API")
    query = request.GET.get('q', '').strip()
    
    if not query:
        # اگر کوئری خالی است، 20 ماده اولیه فعال را برگردان
        raw_materials = RawMaterial.objects.filter(
            status='active'
        ).order_by('name')[:20]
    else:
        # فیلتر کردن مواد اولیه فعال
        raw_materials = RawMaterial.objects.filter(
            status='active'
        ).filter(
            Q(name__icontains=query) | Q(raw_material_id__icontains=query)
        ).order_by('name')[:20]
    
    results = []
    for rm in raw_materials:
        results.append({
            'id': rm.id,
            'text': f"{rm.raw_material_id or ''} - {rm.name}",
            'primary_unit': rm.primary_unit or '',
            'secondary_unit': rm.secondary_unit or '',
            'primary_unit_display': rm.get_primary_unit_display() if rm.primary_unit else '',
            'secondary_unit_display': rm.get_secondary_unit_display() if rm.secondary_unit else '',
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def raw_material_info_api(request, raw_material_id):
    """
    API endpoint برای دریافت اطلاعات کامل ماده اولیه شامل:
    - واحدهای اصلی و فرعی
    - آخرین استعلام قیمت
    - درصد مالیات بر ارزش افزوده از اطلاعات خرید
    """
    audit_logger.info(f"دریافت اطلاعات ماده اولیه از طریق API - شناسه: {raw_material_id}")
    if not raw_material_id:
        audit_logger.alert("درخواست اطلاعات ماده اولیه بدون شناسه")
        return JsonResponse({'error': 'شناسه ماده اولیه الزامی است'}, status=400)
    
    try:
        raw_material = RawMaterial.objects.get(id=raw_material_id, status='active')
        
        # دریافت آخرین استعلام قیمت
        from core.SupplyFolder.RawMaterialPriceInquiryModel import RawMaterialPriceInquiry
        latest_inquiry = RawMaterialPriceInquiry.objects.filter(
            raw_material=raw_material
        ).order_by('-inquiry_date', '-created_at').first()
        
        # دریافت اطلاعات خرید (برای vat_percentage)
        from core.RawMaterialFolder.RawMaterialPurchaseInfoModel import RawMaterialPurchaseInfo
        purchase_info = RawMaterialPurchaseInfo.objects.filter(
            raw_material=raw_material
        ).first()
        
        # ساخت لیست واحدهای قابل استفاده
        # استفاده از display name برای value چون unit در ProcurementPurchaseOrderMaterial یک CharField است
        available_units = []
        if raw_material.primary_unit:
            primary_display = raw_material.get_primary_unit_display()
            available_units.append({
                'value': primary_display,
                'display': primary_display,
                'is_main': True
            })
        if raw_material.secondary_unit:
            secondary_display = raw_material.get_secondary_unit_display()
            # فقط اگر با واحد اصلی متفاوت باشد اضافه کن
            if secondary_display != (raw_material.get_primary_unit_display() if raw_material.primary_unit else ''):
                available_units.append({
                    'value': secondary_display,
                    'display': secondary_display,
                    'is_main': False
                })
        
        # اگر هیچ واحدی وجود نداشت، پیش‌فرض کیلوگرم
        if not available_units:
            available_units.append({
                'value': 'کیلوگرم',
                'display': 'کیلوگرم',
                'is_main': True
            })
        
        data = {
            'primary_unit': raw_material.get_primary_unit_display() if raw_material.primary_unit else '',
            'secondary_unit': raw_material.get_secondary_unit_display() if raw_material.secondary_unit else '',
            'available_units': available_units,
            'latest_price': str(latest_inquiry.price) if latest_inquiry else None,
            'vat_percentage': f'{purchase_info.vat_percentage:.2f}' if purchase_info and purchase_info.vat_percentage is not None else '0.00',
        }
        
        return JsonResponse(data)
    except RawMaterial.DoesNotExist:
        return JsonResponse({'error': 'ماده اولیه یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در دریافت اطلاعات ماده اولیه {raw_material_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)