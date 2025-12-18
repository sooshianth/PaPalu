from django import forms
from django.forms import ModelForm
from core.TransportFolder.TransportModel import Transport


class UploadFarePaymentDocForm(ModelForm):
    """فرم بارگذاری اسناد پرداخت کرایه"""
    
    class Meta:
        model = Transport
        fields = ['freight_payment_document']
        labels = {
            'freight_payment_document': 'سند پرداخت کرایه',
        }
        widgets = {
            'freight_payment_document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['freight_payment_document'].required = True

