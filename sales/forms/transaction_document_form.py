from django import forms
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from core.PersonFolder import BankAccount


class TransactionDocumentForm(forms.ModelForm):
    """
    فرم ثبت سند تراکنش برای تسویه یک سفارش
    فیلدهای اجباری:
        - payment_type (نوع تسویه: نقدی بازارگاه/بانکی/چک)
        - document_amount (مبلغ سند)
        - due_date (تاریخ سررسید)
        - source_account (حساب مبدا)
        - پیوست سند: از طریق فیلد چندگانه document_attachments در view (حداقل یک فایل)
    فیلدهای اختیاری:
        - payment_status (وضعیت وصول)
        - check_receipt_date (تاریخ وصول)
    """

    class Meta:
        model = TransactionDocument
        fields = [
            'payment_type',
            'document_amount',
            'due_date',
            'source_account',
            'document_attachment',
            'payment_status',
            'check_receipt_date',
        ]
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-control'}),
            'document_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'due_date': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'source_account': forms.Select(attrs={'class': 'form-control'}),
            'document_attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'payment_status': forms.Select(attrs={'class': 'form-control'}),
            'check_receipt_date': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
        }

    def __init__(self, *args, **kwargs):
        # دریافت customer از kwargs برای فیلتر کردن حساب‌های بانکی
        customer = kwargs.pop('customer', None)
        
        super().__init__(*args, **kwargs)

        # فیلدهای اجباری (پیوست سند در view با getlist('document_attachments') اعتبارسنجی می‌شود؛ در ویرایش document_attachment اختیاری است)
        self.fields['payment_type'].required = True
        self.fields['document_amount'].required = True
        self.fields['due_date'].required = True
        self.fields['source_account'].required = True
        # در ویرایش سند، پیوست اختیاری است (اگر خالی بماند فایل قبلی حفظ می‌شود)
        self.fields['document_attachment'].required = False

        # فیلدهای اختیاری
        self.fields['payment_status'].required = False
        self.fields['check_receipt_date'].required = False
        
        # فیلتر کردن حساب‌های بانکی بر اساس مشتری
        if customer:
            self.fields['source_account'].queryset = BankAccount.objects.filter(
                financial_banking__person=customer
            ).select_related('financial_banking', 'financial_banking__person')
        else:
            # اگر customer داده نشد، همه حساب‌ها را نمایش بده (برای سازگاری با کدهای قدیمی)
            self.fields['source_account'].queryset = BankAccount.objects.all().select_related('financial_banking', 'financial_banking__person')


