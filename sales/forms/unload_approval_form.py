from django import forms
from django_jalali.forms import jDateTimeField
from django_jalali.forms.widgets import jDateTimeInput


class UnloadApprovalForm(forms.Form):
    """فرم تایید تخلیه سفارش - زمان به صورت شمسی (jDateTimeField) مانند فرم قیمت‌گذاری"""
    
    unload_approval_time = jDateTimeField(
        label='زمان تایید تخلیه',
        required=True,
        widget=jDateTimeInput(attrs={
            'class': 'form-control jalali-datetime',
            'placeholder': 'زمان تایید تخلیه را انتخاب کنید',
            'dir': 'ltr',
        })
    )
    
    customer_feedback = forms.CharField(
        label='توضیحات فیدبک مشتری',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'توضیحات فیدبک مشتری (اختیاری)'
        })
    )

