from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm, inlineformset_factory, BaseInlineFormSet
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from decimal import Decimal
import logging
from core.logging_levels import *
from django_tables2 import RequestConfig

from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from django.contrib.auth import get_user_model


class RawMaterialInfoForm(ModelForm):
    """فرم برای انتخاب و تخصیص مواد اولیه به حمل"""
    
    # فیلد سفارشی برای نمایش نام ماده اولیه
    raw_material_display = forms.CharField(
        required=False,
        label='ماده اولیه',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True,
            'style': 'background-color: #f5f5f5;'
        })
    )
    
    class Meta:
        model = RawMaterialInfo
        fields = ['order_item', 'raw_material', 'allocated_quantity', 'weight_unit', 'packaging_type', 'number_of_packages', 'notes']
        labels = {
            'order_item': 'قلم سفارش',
            'raw_material': 'ماده اولیه',
            'allocated_quantity': 'مقدار تخصیص یافته',
            'weight_unit': 'واحد',
            'packaging_type': 'نوع بسته‌بندی',
            'number_of_packages': 'تعداد بسته',
            'notes': 'یادداشت',
        }
        widgets = {
            'order_item': forms.HiddenInput(),
            'raw_material': forms.HiddenInput(),
            'allocated_quantity': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'decimal', 'pattern': '[0-9]+(\\.[0-9]{1,2})?'}),
            'weight_unit': forms.Select(attrs={'class': 'form-control', 'readonly': True}),
            'packaging_type': forms.Select(attrs={'class': 'form-control'}),
            'number_of_packages': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # اگر instance موجود است، مقادیر اولیه را تنظیم کن
        if self.instance and self.instance.pk:
            if self.instance.raw_material:
                self.fields['raw_material_display'].initial = self.instance.raw_material.name
                self.fields['weight_unit'].initial = self.instance.weight_unit
    
    def clean_allocated_quantity(self):
        """تبدیل مقدار به Decimal بدون از دست دادن دقت"""
        allocated_quantity = self.cleaned_data.get('allocated_quantity')
        if allocated_quantity is None or allocated_quantity == '':
            return None
        
        # تبدیل مستقیم به Decimal از string برای حفظ دقت
        # اگر از float آمده باشد، ابتدا به string تبدیل می‌کنیم
        if isinstance(allocated_quantity, (int, float)):
            # استفاده از str برای جلوگیری از خطاهای float precision
            return Decimal(str(allocated_quantity))
        elif isinstance(allocated_quantity, Decimal):
            return allocated_quantity
        else:
            # اگر string است، مستقیماً به Decimal تبدیل می‌کنیم
            try:
                # حذف فاصله‌ها و تبدیل به string
                value_str = str(allocated_quantity).strip()
                if not value_str:
                    return None
                return Decimal(value_str)
            except (ValueError, TypeError) as e:
                raise forms.ValidationError(f'مقدار وارد شده نامعتبر است: {str(e)}')
    
    def clean(self):
        cleaned_data = super().clean()
        
        # بررسی اینکه آیا فرم برای حذف علامت خورده است
        if self.cleaned_data.get('DELETE', False):
            return cleaned_data
        
        order_item = cleaned_data.get('order_item')
        allocated_quantity = cleaned_data.get('allocated_quantity')
        
        # اگر فرم خالی است، آن را نادیده بگیر
        if not order_item and not allocated_quantity:
            return cleaned_data
        
        if not order_item:
            self.add_error('order_item', 'این فیلد الزامی است.')
            return cleaned_data
        
        # تبدیل مقدار به Decimal با حفظ دقت
        if allocated_quantity is not None:
            if isinstance(allocated_quantity, (int, float)):
                allocated_quantity = Decimal(str(allocated_quantity))
            elif not isinstance(allocated_quantity, Decimal):
                try:
                    allocated_quantity = Decimal(str(allocated_quantity))
                except (ValueError, TypeError):
                    pass
            cleaned_data['allocated_quantity'] = allocated_quantity
        
        if not allocated_quantity or allocated_quantity <= 0:
            self.add_error('allocated_quantity', 'مقدار تخصیص یافته باید بیشتر از صفر باشد.')
            return cleaned_data
        
        # بررسی که مقدار تخصیص یافته بیشتر از مقدار باقیمانده نباشد
        remaining = order_item.get_remaining_quantity()
        
        # اگر در حال ویرایش هستیم، مقدار فعلی را به باقیمانده اضافه کن
        if self.instance and self.instance.pk:
            remaining += self.instance.allocated_quantity
        
        if allocated_quantity > remaining:
            self.add_error(
                'allocated_quantity',
                f'مقدار تخصیص یافته ({allocated_quantity}) نمی‌تواند بیشتر از مقدار باقیمانده ({remaining}) باشد.'
            )
        
        # تنظیم raw_material از order_item
        if order_item and order_item.raw_material:
            cleaned_data['raw_material'] = order_item.raw_material
            # تنظیم واحد از order_item
            cleaned_data['weight_unit'] = order_item.weight_unit
        
        return cleaned_data


class RawMaterialInfoFormSetBase(BaseInlineFormSet):
    """FormSet سفارشی برای مدیریت مواد اولیه در حمل"""
    
    def clean(self):
        """اعتبارسنجی کلی formset"""
        if any(self.errors):
            return
        
        # بررسی اینکه حداقل یک ماده اولیه وارد شده باشد
        valid_forms = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                order_item = form.cleaned_data.get('order_item')
                allocated_quantity = form.cleaned_data.get('allocated_quantity')
                if order_item and allocated_quantity and allocated_quantity > 0:
                    valid_forms += 1
        
        if valid_forms == 0:
            raise forms.ValidationError('حداقل یک ماده اولیه باید تخصیص داده شود.')


# ایجاد formset برای مواد اولیه
RawMaterialInfoFormSet = inlineformset_factory(
    Transport,
    RawMaterialInfo,
    form=RawMaterialInfoForm,
    formset=RawMaterialInfoFormSetBase,
    fields=['order_item', 'raw_material', 'allocated_quantity', 'weight_unit', 'packaging_type', 'number_of_packages', 'notes'],
    extra=1,
    can_delete=True
)


class TransportForm(ModelForm):
    """فرم ایجاد/ویرایش حمل خرید
    
    فیلدهای اجباری:
    - purchase_order (شماره سفارش) - به صورت custom field
    - vehicle_type (نوع ماشین)
    
    transport_type به صورت خودکار به 'inbound' تنظیم می‌شود.
    بقیه فیلدها اختیاری هستند.
    """
    purchase_order = forms.ModelChoiceField(
        queryset=Order.objects.none(),
        label='سفارش خرید',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Transport
        fields = [
            'allocation', 'vehicle_type',
            'plate_number', 'driver',
            'freight_payment_type', 'initial_freight', 'total_freight',
            'discount', 'surplus', 'freight_payment',
            'driver_bank_account', 'supplier_bank_account',
            'expected_arrival_date',
            'waybill_number', 'notes'
        ]
        labels = {
            'allocation': 'تخصیص',
            'vehicle_type': 'نوع ماشین',
            'plate_number': 'پلاک',
            'driver': 'راننده',
            'freight_payment_type': 'نوع کرایه',
            'initial_freight': 'کرایه اولیه',
            'total_freight': 'کرایه کل',
            'discount': 'تخفیف',
            'surplus': 'مازاد',
            'freight_payment': 'کرایه پرداختی',
            'driver_bank_account': 'حساب بانکی راننده',
            'supplier_bank_account': 'حساب بانکی تامین‌کننده',
            'expected_arrival_date': 'تاریخ پیش‌بینی ورود',
            'waybill_number': 'شماره بارنامه',
            'notes': 'یادداشت',
        }
        widgets = {
            'allocation': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.Select(attrs={'class': 'form-control', 'id': 'id_freight_payment_type'}),
            'initial_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'total_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'readonly': 'readonly', 'style': 'background-color: #f5f5f5; cursor: not-allowed;'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'surplus': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'freight_payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'readonly': 'readonly', 'style': 'background-color: #f5f5f5; cursor: not-allowed;'}),
            'driver_bank_account': forms.Select(attrs={'class': 'form-control'}),
            'supplier_bank_account': forms.Select(attrs={'class': 'form-control'}),
            'expected_arrival_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'text', 'placeholder': '1403/09/15'}),
            'waybill_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.PersonFolder.PersonModel import Person
        from core.AllocationFolder.AllocationModel import Allocation
        from core.OrderFolder.OrderModel import Order
        
        # فیلدهای اجباری
        self.fields['vehicle_type'].required = True
        
        # حذف فیلد transport_type از فرم (خودکار به inbound تنظیم می‌شود)
        if 'transport_type' in self.fields:
            del self.fields['transport_type']
        
        # Filter purchase orders that are not in draft or completed status
        self.fields['purchase_order'].queryset = Order.objects.filter(
            order_type='purchase'
        ).exclude(
            status__in=[
                Order.STATUS_DRAFT,
                Order.STATUS_COMPLETED
            ]
        ).order_by('-created_at')
        
        # اگر instance موجود است، purchase_order را از allocation تنظیم کن
        if self.instance and self.instance.pk and self.instance.allocation:
            self.fields['purchase_order'].initial = self.instance.allocation.order
        
        # allocation را مخفی کن (از purchase_order استفاده می‌کنیم)
        self.fields['allocation'].widget = forms.HiddenInput()
        self.fields['allocation'].required = False
        
        # تبدیل فیلد driver به text input برای autocomplete
        # یک hidden field برای driver_id اضافه می‌کنیم
        self.fields['driver'].widget = forms.HiddenInput()
        self.fields['driver'].required = False
        
        # تنظیم choices برای freight_payment_type
        self.fields['freight_payment_type'].choices = Order.FREIGHT_PAYMENT_CHOICES
        
        # نوع پرداخت کرایه: از سفارش خرید گرفته می‌شود و readonly است
        purchase_order = None
        if self.instance and self.instance.pk and self.instance.allocation and self.instance.allocation.order:
            purchase_order = self.instance.allocation.order
        elif 'purchase_order' in self.initial:
            purchase_order = self.initial['purchase_order']
        elif hasattr(self, 'data') and self.data and 'purchase_order' in self.data:
            try:
                purchase_order = Order.objects.get(pk=self.data['purchase_order'])
            except (Order.DoesNotExist, ValueError):
                pass
        
        if purchase_order and purchase_order.freight_payment_type:
            # تنظیم مقدار از سفارش خرید
            self.fields['freight_payment_type'].initial = purchase_order.freight_payment_type
            # readonly کردن فیلد
            self.fields['freight_payment_type'].widget.attrs['readonly'] = True
            self.fields['freight_payment_type'].widget.attrs['disabled'] = True
            self.fields['freight_payment_type'].widget.attrs['style'] = 'background-color: #f5f5f5; cursor: not-allowed;'
            self.fields['freight_payment_type'].required = False
        
        # تنظیم queryset برای حساب‌های بانکی راننده (اگر driver موجود است)
        if self.instance and self.instance.pk and self.instance.driver:
            try:
                financial_banking = FinancialBanking.objects.filter(person=self.instance.driver).first()
                if financial_banking:
                    self.fields['driver_bank_account'].queryset = BankAccount.objects.filter(
                        financial_banking=financial_banking
                    )
            except Exception:
                pass
        
        # تنظیم queryset برای حساب‌های بانکی تامین‌کننده (اگر purchase_order موجود است)
        if self.instance and self.instance.pk and self.instance.allocation and self.instance.allocation.order:
            try:
                supplier = self.instance.allocation.order.customer
                if supplier:
                    financial_banking = FinancialBanking.objects.filter(person=supplier).first()
                    if financial_banking:
                        self.fields['supplier_bank_account'].queryset = BankAccount.objects.filter(
                            financial_banking=financial_banking
                        )
            except Exception:
                pass
        
        # مخفی کردن فیلدهای حساب بانکی فقط در حالت ایجاد (در ویرایش به‌صورت Select نمایش داده می‌شوند)
        if not (self.instance and self.instance.pk):
            self.fields['driver_bank_account'].widget = forms.HiddenInput()
            self.fields['supplier_bank_account'].widget = forms.HiddenInput()
    
    def clean(self):
        cleaned_data = super().clean()
        purchase_order = cleaned_data.get('purchase_order')
        
        # وقتی از صفحه سفارش با ?order= می‌آییم، فیلد purchase_order غیرفعال است و در POST ارسال نمی‌شود.
        # در این حالت از مقدار اولیه استفاده کن تا allocation حتماً تنظیم شود (جلوگیری از خطای FK).
        if not purchase_order and self.initial.get('purchase_order'):
            purchase_order = self.initial['purchase_order']
            cleaned_data['purchase_order'] = purchase_order
        
        if purchase_order:
            # پیدا کردن یا ایجاد Allocation برای این Order
            from core.AllocationFolder.AllocationModel import Allocation
            import uuid
            
            # سعی کن Allocation موجود را پیدا کنی
            allocation = Allocation.objects.filter(order=purchase_order).first()
            
            # اگر Allocation وجود نداشت، یکی بساز
            if not allocation:
                allocation_number = f"ALLOC-{purchase_order.order_number}-{str(uuid.uuid4())[:8]}"
                allocation = Allocation.objects.create(
                    allocation_number=allocation_number,
                    order=purchase_order,
                    allocation_status='planned'
                )
            
            cleaned_data['allocation'] = allocation
            
            # تنظیم freight_payment_type از سفارش خرید (همیشه از سفارش گرفته می‌شود)
            if purchase_order.freight_payment_type:
                cleaned_data['freight_payment_type'] = purchase_order.freight_payment_type
        
        # اطمینان از اینکه FKهای اختیاری مقدار خالی/رشته خالی را به None تبدیل کنند (جلوگیری از خطای FK)
        for fk_field in ('driver_bank_account', 'supplier_bank_account'):
            if cleaned_data.get(fk_field) in (None, ''):
                cleaned_data[fk_field] = None
        
        # محاسبه خودکار کرایه کل و پرداختی
        initial_freight = cleaned_data.get('initial_freight') or 0
        discount = cleaned_data.get('discount') or 0
        surplus = cleaned_data.get('surplus') or 0
        
        # محاسبه: کرایه اولیه + مازاد - تخفیف
        total_freight = initial_freight + surplus - discount
        # حداقل 0
        total_freight = max(0, total_freight)
        
        # تنظیم کرایه کل
        cleaned_data['total_freight'] = total_freight
        
        # کرایه پرداختی همان کرایه کل است
        cleaned_data['freight_payment'] = total_freight
        
        return cleaned_data

