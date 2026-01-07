from django import forms
from django_jalali import forms as jforms
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TransportAttachmentModel import TransportAttachment
from datetime import datetime


class WaybillRegistrationForm(forms.Form):
    """فرم ثبت اطلاعات بارنامه"""
    
    # فیلدهای اجباری
    waybill_number = forms.CharField(
        required=True,
        label='شماره بارنامه',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره بارنامه',
            'required': True
        })
    )
    
    waybill_serial = forms.CharField(
        required=True,
        label='سریال بارنامه',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'سریال بارنامه',
            'required': True
        })
    )
    
    waybill_date = forms.CharField(
        required=True,
        label='تاریخ بارنامه',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'type': 'text',
            'placeholder': '1403/09/15',
            'id': 'id_waybill_date',
            'required': True,
            'dir': 'ltr'
        })
    )
    
    cardex_code = forms.CharField(
        required=True,
        label='کد کاردکس',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد کاردکس',
            'required': True
        })
    )
    
    contract_code = forms.CharField(
        required=True,
        label='کد قرارداد',
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد قرارداد',
            'required': True
        })
    )
    
    waybill_file = forms.FileField(
        required=True,
        label='پیوست بارنامه',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf',
            'required': True
        }),
        help_text='فایل بارنامه (تصویر یا PDF)'
    )
    
    # فیلدهای کرایه (اختیاری)
    fare_type = forms.CharField(
        required=False,
        label='نوع کرایه',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نوع کرایه'
        })
    )
    
    per_transport_fee = forms.DecimalField(
        required=False,
        label='فی حمل (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'فی حمل',
            'step': '0.01'
        })
    )
    
    initial_fare = forms.DecimalField(
        required=False,
        label='کرایه اولیه (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'کرایه اولیه',
            'step': '0.01'
        })
    )
    
    terminal_fee = forms.DecimalField(
        required=False,
        label='کارمزد پایانه (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'کارمزد پایانه',
            'step': '0.01'
        })
    )
    
    company_fee = forms.DecimalField(
        required=False,
        label='کارمزد شرکت (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'کارمزد شرکت',
            'step': '0.01'
        })
    )
    
    other_costs = forms.DecimalField(
        required=False,
        label='سایر هزینه‌ها (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'سایر هزینه‌ها',
            'step': '0.01'
        })
    )
    
    total_fare = forms.DecimalField(
        required=False,
        label='کرایه کل (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'کرایه کل',
            'step': '0.01'
        })
    )
    
    discount = forms.DecimalField(
        required=False,
        label='تخفیف (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'تخفیف',
            'step': '0.01'
        })
    )
    
    excess = forms.DecimalField(
        required=False,
        label='مازاد (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'مازاد',
            'step': '0.01'
        })
    )
    
    paid_fare = forms.DecimalField(
        required=False,
        label='کرایه پرداختی (ریال)',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'کرایه پرداختی',
            'step': '0.01'
        })
    )
    
    def clean_waybill_date(self):
        """تبدیل تاریخ از رشته به date object"""
        date_str = self.cleaned_data.get('waybill_date')
        if not date_str:
            raise forms.ValidationError('این فیلد لازم است.')
        
        # تبدیل تاریخ میلادی (YYYY-MM-DD) به date object
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return date_obj
        except ValueError:
            raise forms.ValidationError('فرمت تاریخ نامعتبر است.')

