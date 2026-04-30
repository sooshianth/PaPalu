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
    - پلاک
    - تصویر بارنامه
    - حداقل یکی از شماره حساب یا شماره شبا راننده (فقط اگر نوع کرایه "پرداخت به راننده" باشد)
    """
    phone = forms.CharField(
        label='شماره تلفن راننده',
        required=False,
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
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد ملی 10 رقمی',
            'maxlength': '10',
            'inputmode': 'numeric',
            'pattern': '\\d{0,10}'
        })
    )
    plate_number = forms.CharField(
        label='پلاک',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12الف34567'})
    )
    waybill_number = forms.CharField(
        label='شماره بارنامه',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره بارنامه'
        })
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

        # اگر نوع کرایه "پرداخت به راننده" باشد، حداقل یکی از شماره حساب یا شبا الزامی است (هر دو اجباری نیستند)
        if freight_payment_type == 'pay_to_driver':
            self.fields['account'].required = False
            self.fields['sheba'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        # اگر نوع کرایه "پرداخت به راننده" باشد، حداقل یکی از شماره حساب یا شبا باید پر شود
        if self.freight_payment_type == 'pay_to_driver':
            account = (cleaned_data.get('account') or '').strip()
            sheba = (cleaned_data.get('sheba') or '').strip()
            if not account and not sheba:
                self.add_error('account', 'برای نوع کرایه «پرداخت به راننده» حداقل یکی از شماره حساب یا شماره شبا را وارد کنید.')
                self.add_error('sheba', 'برای نوع کرایه «پرداخت به راننده» حداقل یکی از شماره حساب یا شماره شبا را وارد کنید.')
        return cleaned_data
