from django import forms
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from core.PersonFolder.BankAccountModel import BankAccount


class SettlementTransactionForm(forms.ModelForm):
    """
    فرم ثبت تراکنش برای تسویه سفارش
    
    فیلدهای اجباری:
        - payment_type: نوع تسویه (نقدی بازارگاه، بانکی، چک)
        - document_amount: مبلغ سند
        - due_date: تاریخ سررسید
        - source_account: حساب مبدا
        - document_attachment: پیوست سند
        - accounting_document_number: شماره سند حسابداری
        - tracking_number: شماره پیگیری واریز
        - source_bank: بانک مبدا
        - approval_account_number: شماره حساب
        - shaba_number: شماره شبا
        - inquiry_name: نام استعلام شده
        - transfer_time: ساعت واریز
    """
    
    class Meta:
        model = TransactionDocument
        fields = [
            'discrepancy_type',
            'payment_type',
            'document_amount',
            'due_date',
            'source_account',
            'document_attachment',
            'accounting_document_number',
            'tracking_number',
            'source_bank',
            'approval_account_number',
            'shaba_number',
            'inquiry_name',
            'transfer_time',
        ]
        widgets = {
            'discrepancy_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'document_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'مبلغ سند'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'تاریخ سررسید'
            }),
            'source_account': forms.Select(attrs={
                'class': 'form-control'
            }),
            'document_attachment': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
            'accounting_document_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره سند حسابداری'
            }),
            'tracking_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره پیگیری واریز'
            }),
            'source_bank': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'بانک مقصد'
            }),
            'approval_account_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره حساب'
            }),
            'shaba_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره شبا (بدون IR)'
            }),
            'inquiry_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نام استعلام شده'
            }),
            'transfer_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'placeholder': 'ساعت واریز'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # تنظیم فیلدهای اجباری
        required_fields = [
            'discrepancy_type',
            'payment_type',
            'document_amount',
            'due_date',
            'source_account',
            'document_attachment',
            'accounting_document_number',
            'tracking_number',
            'source_bank',
            'approval_account_number',
            'shaba_number',
            'inquiry_name',
            'transfer_time',
        ]
        
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # تنظیم برچسب‌های فارسی
        self.fields['discrepancy_type'].label = 'نوع تسویه (کسری/سرک)'
        self.fields['payment_type'].label = 'نوع تسویه'
        self.fields['document_amount'].label = 'مبلغ سند'
        self.fields['due_date'].label = 'تاریخ سررسید'
        self.fields['source_account'].label = 'حساب مبدا'
        self.fields['document_attachment'].label = 'پیوست سند'
        self.fields['accounting_document_number'].label = 'شماره سند حسابداری'
        self.fields['tracking_number'].label = 'شماره پیگیری واریز'
        self.fields['source_bank'].label = 'بانک مقصد'
        self.fields['approval_account_number'].label = 'شماره حساب'
        self.fields['shaba_number'].label = 'شماره شبا'
        self.fields['inquiry_name'].label = 'نام استعلام شده'
        self.fields['transfer_time'].label = 'ساعت واریز'
    
    def clean_document_amount(self):
        """اعتبارسنجی مبلغ سند"""
        amount = self.cleaned_data.get('document_amount')
        if amount and amount <= 0:
            raise forms.ValidationError('مبلغ سند باید بیشتر از صفر باشد.')
        return amount
    
    def clean_shaba_number(self):
        """اعتبارسنجی شماره شبا"""
        shaba = self.cleaned_data.get('shaba_number')
        if shaba:
            # حذف فاصله‌ها و IR
            shaba = shaba.replace(' ', '').replace('IR', '').replace('ir', '')
            # بررسی طول
            if len(shaba) != 24:
                raise forms.ValidationError('شماره شبا باید 24 رقم باشد.')
            # بررسی عددی بودن
            if not shaba.isdigit():
                raise forms.ValidationError('شماره شبا باید فقط شامل اعداد باشد.')
        return shaba

