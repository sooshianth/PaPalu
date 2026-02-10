from django import forms
from django.forms import ModelForm
from core.TransportFolder.TransportModel import Transport


class UploadFarePaymentDocForm(ModelForm):
    """فرم بارگذاری اسناد پرداخت کرایه (فایل‌ها در view با document_attachments ارسال می‌شوند)"""
    
    class Meta:
        model = Transport
        fields = []  # فایل‌ها جداگانه با نام document_attachments ارسال می‌شوند

