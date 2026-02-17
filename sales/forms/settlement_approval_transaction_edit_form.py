# -*- coding: utf-8 -*-
"""
فرم ویرایش تراکنش در صفحه تایید تسویه کامل (فقط مدیر - ارجاع‌شده)
"""
from django import forms
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument


class SettlementApprovalTransactionEditForm(forms.ModelForm):
    """فرم ویرایش سند تراکنش توسط مدیر در صفحه تایید تسویه کامل."""

    class Meta:
        model = TransactionDocument
        fields = [
            'payment_type',
            'document_amount',
            'due_date',
            'tracking_number',
            'accounting_document_number',
            'discrepancy_type',
        ]
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-control'}),
            'document_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'placeholder': 'مبلغ (ریال)',
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'tracking_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره پیگیری',
            }),
            'accounting_document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره سند حسابداری',
            }),
            'discrepancy_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.settlement = kwargs.pop('settlement', None)
        super().__init__(*args, **kwargs)
        self.fields['payment_type'].label = 'نوع پرداخت'
        self.fields['document_amount'].label = 'مبلغ (ریال)'
        self.fields['due_date'].label = 'تاریخ سررسید'
        self.fields['tracking_number'].label = 'شماره پیگیری'
        self.fields['accounting_document_number'].label = 'شماره سند حسابداری'
        self.fields['discrepancy_type'].label = 'نوع (کسری/سرک)'
        # برای تسویه فروش/کرایه فیلد نوع (کسری/سرک) را حذف کن تا ذخیره نشود
        if self.settlement and self.settlement.settlement_type != 'weight_discrepancy':
            self.fields.pop('discrepancy_type', None)

    def clean_document_amount(self):
        amount = self.cleaned_data.get('document_amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('مبلغ باید بزرگ‌تر از صفر باشد.')
        return amount
