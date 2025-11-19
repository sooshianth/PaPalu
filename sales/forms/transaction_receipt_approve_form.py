from django import forms
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument


class TransactionApprovalForm(forms.ModelForm):
    """
    فرم تأیید تراکنش فروش (override فیلدهای TransactionDocument)
    فیلدهای اجباری:
        - accounting_document_number (شماره سند حسابداری)
        - inquiry_amount (مبلغ استعلام گرفته شده)
        - tracking_number (شماره پیگیری واریز)
        - source_bank (بانک مبدا)
        - approval_account_number (شماره حساب)
        - shaba_number (شماره شبا)
        - inquiry_name (نام استعلام شده)
        - transfer_time (ساعت واریز)
    """

    class Meta:
        model = TransactionDocument
        fields = [
            'accounting_document_number',
            'inquiry_amount',
            'tracking_number',
            'source_bank',
            'approval_account_number',
            'shaba_number',
            'inquiry_name',
            'transfer_time',
        ]
        widgets = {
            'accounting_document_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'inquiry_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'source_bank': forms.TextInput(attrs={'class': 'form-control'}),
            'approval_account_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'shaba_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'inquiry_name': forms.TextInput(attrs={'class': 'form-control'}),
            'transfer_time': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
        }

    def __init__(self, *args, **kwargs):
        self.settlement = kwargs.pop('settlement', None)
        self.document = kwargs.pop('document', None)  # سند تراکنش که باید تأیید شود
        super().__init__(*args, **kwargs)

        # اگر document داده شده، instance را تنظیم کن
        if self.document:
            self.instance = self.document

        # همه فیلدها اجباری هستند
        for field in self.fields:
            self.fields[field].required = True

    def clean(self):
        cleaned_data = super().clean()
        
        # بررسی اینکه مجموع مبالغ استعلام از مبلغ کل تسویه بیشتر نشود
        if self.settlement and self.settlement.original_document_amount:
            inquiry_amount = cleaned_data.get('inquiry_amount')
            if inquiry_amount:
                # محاسبه مجموع مبالغ استعلام موجود (بدون سند فعلی)
                from django.db.models import Sum
                existing_documents = self.settlement.transaction_documents.filter(
                    inquiry_amount__isnull=False
                )
                if self.instance and self.instance.pk:
                    # اگر در حال ویرایش هستیم، سند فعلی را از محاسبه حذف کنیم
                    existing_documents = existing_documents.exclude(pk=self.instance.pk)
                
                total_existing = existing_documents.aggregate(total=Sum('inquiry_amount'))['total'] or 0
                total_with_new = float(total_existing) + float(inquiry_amount)
                
                if total_with_new > float(self.settlement.original_document_amount):
                    remaining = float(self.settlement.original_document_amount) - float(total_existing)
                    raise forms.ValidationError({
                        'inquiry_amount': f'مجموع مبالغ استعلام ({total_with_new}) نمی‌تواند از مبلغ کل تسویه ({self.settlement.original_document_amount}) بیشتر باشد. باقیمانده: {remaining} ریال'
                    })
        
        return cleaned_data

