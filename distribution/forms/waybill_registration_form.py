from django import forms
from django_jalali import forms as jforms
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TransportAttachmentModel import TransportAttachment


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
            'required': True,
            'readonly': True
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
    
    waybill_date = jforms.jDateField(
        required=True,
        label='تاریخ بارنامه',
        widget=jforms.jDateInput(attrs={
            'class': 'form-control',
            'required': True
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

