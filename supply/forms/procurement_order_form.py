from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm, inlineformset_factory, BaseInlineFormSet
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal, ROUND_HALF_UP
from core.logging_levels import *

from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.PersonFolder.PersonModel import Person
from core.RawMaterialFolder.RawMaterialModel import RawMaterial

class ProcurementPurchaseOrderForm(ModelForm):
    class Meta:
        model = Order
        fields = [
            'customer', 'freight_payment_type',
            'subtotal_without_freight', 'freight_cost',
            'external_system_id', 'ordered_at'
        ]
        labels = {
            'customer': 'تأمین‌کننده',
            'freight_payment_type': 'نوع پرداخت کرایه',
            'subtotal_without_freight': 'جمع بدون کرایه',
            'freight_cost': 'هزینه کرایه',
            'external_system_id': 'شناسه یکتا در سیستم دامپروش/کی‌اچ/انبار/لبه‌ژنت',
            'ordered_at': "تاریخ خرید"
        }
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.Select(attrs={'class': 'form-control'}),
            'subtotal_without_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'readonly': True}),
            'freight_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'external_system_id': forms.TextInput(attrs={'class': 'form-control'}),
            'ordered_at': forms.DateInput(attrs={'class': 'form-control jalali-date', 'type': 'text', 'placeholder': '####/##/##', 'data-jdp': ''}),
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

        # اگر instance وجود دارد و ordered_at دارد، مقدار initial را تنظیم کن
        if instance and instance.pk and instance.ordered_at:
            if 'initial' not in kwargs:
                kwargs['initial'] = {}
            # تنظیم ordered_at به صورت رشته‌ای با فرمت گریگوریان
            kwargs['initial']['ordered_at'] = instance.ordered_at.strftime('%Y-%m-%d')
        
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
        
        # تبدیل ordered_at به jalali date picker
        # Handle initial value from instance or form data
        initial_date = None
        
        # First try to get from form data
        if hasattr(self, 'data') and self.data:
            initial_date = self.data.get('ordered_at', None)
        
        # If not found, try to get from instance
        if not initial_date and instance and instance.ordered_at:
            initial_date = instance.ordered_at.strftime('%Y-%m-%d')
        
        # Create the field with appropriate attributes
        self.fields['ordered_at'] = forms.CharField(
            required=True,
            label='تاریخ خرید',
            widget=forms.TextInput(attrs={
                'class': 'form-control jalali-date',
                'placeholder': '####/##/##',
                'autocomplete': 'off',
                'data-jdp': '',
                'data-gdate': initial_date if initial_date else ''
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
        
        # نوع پرداخت کرایه: فقط در ایجاد قابل ویرایش است، در ویرایش readonly
        if self.instance and self.instance.pk:
            # ویرایش - readonly
            if 'freight_payment_type' in self.fields:
                self.fields['freight_payment_type'].widget.attrs['readonly'] = True
                self.fields['freight_payment_type'].widget.attrs['disabled'] = True
                self.fields['freight_payment_type'].widget.attrs['style'] = 'background-color: #f5f5f5; cursor: not-allowed;'
    
    def clean(self):
        cleaned_data = super().clean()
        # تبدیل supplier_id به customer
        ordered_at = cleaned_data.get('ordered_at')
        # Get the raw date string from form data
        raw_ordered_at = self.data.get('ordered_at', '').strip()
        print("wqdqwqd ",raw_ordered_at)
        if not ordered_at and raw_ordered_at:
            try:
                import jdatetime
                from django.utils.dateparse import parse_date
                
                # Parse the Gregorian string (YYYY-MM-DD)
                g_date = parse_date(raw_ordered_at)
                if g_date:
                    # Convert Gregorian date to Jalali date object
                    # This ensures compatibility with jDateTimeField
                    cleaned_data['ordered_at'] = jdatetime.date.fromgregorian(date=g_date)
            except Exception as e:
                print(f"Date conversion error: {e}")

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
        
        # نرمال‌سازی فیلدهای پولی با ۰ رقم اعشار (مدل Order: decimal_places=0)
        for field_name in ('subtotal_without_freight', 'freight_cost'):
            val = cleaned_data.get(field_name)
            if val is not None and val != '':
                try:
                    d = Decimal(str(val))
                    cleaned_data[field_name] = d.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                except (ValueError, TypeError, Exception):
                    pass
        
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
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'total_purchase_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'readonly': True}),
            'vat_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
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
        
        # واحد به صورت dropdown - واحدها فقط از ماده اولیه (JavaScript پر می‌کند)
        self.fields['weight_unit'].widget = forms.Select(attrs={'class': 'form-control material-unit-select'})
        self.fields['weight_unit'].choices = OrderItem.WEIGHT_UNIT_CHOICES
    
    def clean_weight_unit(self):
        """تبدیل display name به value - واحدها از RawMaterial"""
        weight_unit = self.cleaned_data.get('weight_unit')
        if not weight_unit:
            return weight_unit
        
        display_to_value = {
            'گرم': 'gr', 'کیلوگرم': 'kg', 'تن': 'ton',
            'متر مکعب': 'm3', 'لیتر': 'ltr', 'میلی لیتر': 'cc',
            'کیسه': 'bag', 'عدد': 'piece',
        }
        if weight_unit in display_to_value:
            return display_to_value[weight_unit]
        valid_values = ['gr', 'kg', 'ton', 'm3', 'ltr', 'cc', 'bag', 'piece']
        if weight_unit in valid_values:
            return weight_unit
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
        
        # اعتبارسنجی واحد - واحدها فقط از تعریف ماده اولیه
        if raw_material and weight_unit:
            allowed_order_item_units = []
            if raw_material.primary_unit:
                if raw_material.primary_unit not in allowed_order_item_units:
                    allowed_order_item_units.append(raw_material.primary_unit)
            if raw_material.secondary_unit:
                if raw_material.secondary_unit not in allowed_order_item_units:
                    allowed_order_item_units.append(raw_material.secondary_unit)
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
            
            # گرد کردن به عدد صحیح (۰ رقم اعشار) برای مطابقت با محدودیت فیلد مدل
            calculated_total = calculated_total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            cleaned_data['total_purchase_cost'] = calculated_total
            if total_purchase_cost and abs(Decimal(str(total_purchase_cost)) - calculated_total) > Decimal('1'):
                # فقط هشدار می‌دهیم، مقدار را اصلاح می‌کنیم
                pass
        
        # نرمال‌سازی فیلدهای پولی با ۰ رقم اعشار (مدل decimal_places=0)
        for field_name in ('unit_price', 'total_purchase_cost', 'freight_cost'):
            val = cleaned_data.get(field_name)
            if val is not None and val != '':
                try:
                    d = Decimal(str(val))
                    cleaned_data[field_name] = d.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                except (ValueError, TypeError, Exception):
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
