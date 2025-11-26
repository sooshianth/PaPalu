from django import forms
from django_jalali.db import models as jmodels
from core.OrderFolder.OrderModel import Order
import jdatetime


class UnloadApprovalForm(forms.Form):
    """فرم تایید تخلیه سفارش"""
    
    unload_approval_time = forms.DateField(
        label='زمان تایید تخلیه',
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'زمان تایید تخلیه را انتخاب کنید'
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

