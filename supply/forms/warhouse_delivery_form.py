import logging
from core.logging_levels import *
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

from core.TransportFolder.TransportModel import Transport
from django.utils.html import format_html
from core.WarehouseFolder.WarehouseModel import Warehouse
from django import forms

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
