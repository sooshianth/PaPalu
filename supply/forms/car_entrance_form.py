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

class CarEntranceDriverForm(forms.Form):
    """فرم ثبت اطلاعات راننده برای ورود خودرو
    
    فیلدهای اجباری:
    - نام راننده
    - شماره تلفن راننده
    - پلاک
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
        required=False,
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
    waybill_gross_weight = forms.DecimalField(
        label='وزن پر بارنامه (کیلوگرم)',
        required=True,
        max_digits=15,
        decimal_places=3,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.000',
            'step': '0.001',
            'min': '0'
        }),
        help_text='وزن پر (ناخالص) که روی بارنامه ثبت شده - برای مقایسه با باسکول کارخانه'
    )
    waybill_date = forms.DateField(
        label='تاریخ بارنامه',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'text',
            'placeholder': '1403/09/15',
            'id': 'id_waybill_date',
            'autocomplete': 'off',
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
    
    def __init__(self, *args, freight_payment_type=None, driver=None, has_existing_waybill=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.freight_payment_type = freight_payment_type
        self.driver = driver
        self.has_existing_waybill = has_existing_waybill

        # اگر حمل از قبل تصویر بارنامه دارد، آپلود مجدد اجباری نیست
        if has_existing_waybill:
            self.fields['bill_of_lading_file'].required = False

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
