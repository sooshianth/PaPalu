from django import forms
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from core.PersonFolder import BankAccount, Person


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
            'transfer_time',
        ]
        widgets = {
            'accounting_document_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'inquiry_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
            'transfer_time': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
        }

    # فیلدهای dropdown برای حساب بانکی
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.none(),
        required=True,
        label='حساب بانکی',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='حساب بانکی را انتخاب کنید'
    )
    
    # فیلد dropdown برای نام استعلام گرفته شده
    inquiry_name = forms.ChoiceField(
        choices=[],
        required=True,
        label='نام استعلام گرفته شده',
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_inquiry_name_select'}),
        help_text='نام استعلام گرفته شده را انتخاب کنید'
    )
    
    # فیلد اختیاری برای وارد کردن نام دستی (وقتی "سایر" انتخاب شود)
    inquiry_name_other = forms.CharField(
        required=False,
        label='نام استعلام گرفته شده (سایر)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'id_inquiry_name_other', 'style': 'display: none;'}),
        help_text='در صورت انتخاب "سایر"، نام را وارد کنید'
    )

    def __init__(self, *args, **kwargs):
        self.settlement = kwargs.pop('settlement', None)
        self.document = kwargs.pop('document', None)  # سند تراکنش که باید تأیید شود
        super().__init__(*args, **kwargs)

        # اگر document داده شده، instance را تنظیم کن
        if self.document:
            self.instance = self.document

        # تنظیم queryset برای bank_account بر اساس مشتری سفارش
        if self.settlement and self.settlement.order and self.settlement.order.customer:
            customer = self.settlement.order.customer
            # گرفتن حساب‌های بانکی مشتری
            bank_accounts = BankAccount.objects.filter(
                financial_banking__person=customer
            ).select_related('financial_banking')
            self.fields['bank_account'].queryset = bank_accounts
            
            # اگر document موجود است و حساب بانکی دارد، مقدار پیش‌فرض را تنظیم کن
            if self.document and self.document.source_account:
                try:
                    # سعی کن حساب بانکی را از source_account پیدا کنی
                    matching_account = bank_accounts.filter(
                        account_number=self.document.source_account.account_number
                    ).first()
                    if matching_account:
                        self.fields['bank_account'].initial = matching_account.id
                except:
                    pass
            
            # تنظیم choices برای inquiry_name - نام مشتری به عنوان گزینه اول
            customer_name = customer.name or 'مشتری'
            inquiry_name_choices = [
                (customer_name, customer_name),
                ('other', 'سایر (وارد کنید)'),
            ]
            self.fields['inquiry_name'].choices = inquiry_name_choices
            
            # تنظیم مقدار پیش‌فرض
            if not self.document or not self.document.inquiry_name:
                # اگر سند جدید است یا inquiry_name ندارد، نام مشتری را انتخاب کن
                self.fields['inquiry_name'].initial = customer_name
            elif self.document.inquiry_name == customer_name:
                # اگر نام مشتری است، آن را انتخاب کن
                self.fields['inquiry_name'].initial = customer_name
            else:
                # اگر نام دیگری است
                existing_choices = [choice[0] for choice in inquiry_name_choices]
                if self.document.inquiry_name in existing_choices:
                    # اگر نام در choices موجود است، آن را انتخاب کن
                    self.fields['inquiry_name'].initial = self.document.inquiry_name
                else:
                    # اگر نام در choices نیست، "سایر" را انتخاب کن و نام را در inquiry_name_other بگذار
                    self.fields['inquiry_name'].initial = 'other'
                    self.fields['inquiry_name_other'].initial = self.document.inquiry_name
        else:
            self.fields['bank_account'].queryset = BankAccount.objects.none()
            self.fields['inquiry_name'].choices = [('', 'لطفاً مشتری را انتخاب کنید')]

        # ذخیره مقدار اصلی document_amount برای بررسی تطابق (بدون پیش‌پرکردن فیلد)
        # مقدار inquiry_amount نباید پیش‌پر شود - کاربر باید آن را وارد کند
        
        # حذف فیلدهای قدیمی source_bank, approval_account_number, shaba_number
        # چون از bank_account استفاده می‌کنیم
        if 'source_bank' in self.fields:
            del self.fields['source_bank']
        if 'approval_account_number' in self.fields:
            del self.fields['approval_account_number']
        if 'shaba_number' in self.fields:
            del self.fields['shaba_number']
        
        # همه فیلدها اجباری هستند (به جز inquiry_name_other که اختیاری است)
        for field in self.fields:
            if field != 'inquiry_name_other':
                self.fields[field].required = True

    def clean(self):
        cleaned_data = super().clean()
        
        # پر کردن فیلدهای source_bank, approval_account_number, shaba_number از bank_account
        bank_account = cleaned_data.get('bank_account')
        if bank_account:
            cleaned_data['source_bank'] = bank_account.bank_name or ''
            cleaned_data['approval_account_number'] = bank_account.account_number or ''
            cleaned_data['shaba_number'] = bank_account.shaba_number or ''
        
        # اگر "سایر" انتخاب شده، از inquiry_name_other استفاده کن
        inquiry_name = cleaned_data.get('inquiry_name')
        if inquiry_name == 'other':
            inquiry_name_other = cleaned_data.get('inquiry_name_other')
            if not inquiry_name_other:
                raise forms.ValidationError({
                    'inquiry_name_other': 'لطفاً نام استعلام گرفته شده را وارد کنید.'
                })
            cleaned_data['inquiry_name'] = inquiry_name_other
        
        # بررسی تطابق inquiry_amount با document_amount (برای اطمینان از صحت)
        if self.document and self.document.document_amount:
            inquiry_amount = cleaned_data.get('inquiry_amount')
            if inquiry_amount:
                from decimal import Decimal
                document_amount = Decimal(str(self.document.document_amount))
                submitted_amount = Decimal(str(inquiry_amount))
                if abs(submitted_amount - document_amount) > Decimal('0.01'):
                    # فرمت کردن مبالغ برای نمایش در پیام خطا
                    document_amount_formatted = f"{document_amount:,.0f}"
                    submitted_amount_formatted = f"{submitted_amount:,.0f}"
                    raise forms.ValidationError({
                        'inquiry_amount': f'مبلغ استعلام گرفته شده با مبلغ سند تطابق ندارد. مبلغ واقعی سند: {document_amount_formatted} ریال، مبلغ وارد شده: {submitted_amount_formatted} ریال. لطفاً مبلغ را بررسی کنید و در صورت نیاز تراکنش را رد کنید.'
                    })
        
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
                
                from decimal import Decimal
                total_existing = existing_documents.aggregate(total=Sum('inquiry_amount'))['total'] or 0
                total_with_new = Decimal(str(total_existing)) + Decimal(str(inquiry_amount))
                orig = Decimal(str(self.settlement.original_document_amount))
                if total_with_new > orig:
                    remaining = orig - Decimal(str(total_existing))
                    raise forms.ValidationError({
                        'inquiry_amount': f'مجموع مبالغ استعلام ({total_with_new}) نمی‌تواند از مبلغ کل تسویه ({self.settlement.original_document_amount}) بیشتر باشد. باقیمانده: {remaining} ریال'
                    })
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # پر کردن فیلدهای source_bank, approval_account_number, shaba_number از bank_account
        bank_account = self.cleaned_data.get('bank_account')
        if bank_account:
            instance.source_bank = bank_account.bank_name or ''
            instance.approval_account_number = bank_account.account_number or ''
            instance.shaba_number = bank_account.shaba_number or ''
            instance.approval_status = 'approved'
            instance.rejection_reason = None
        
        if commit:
            instance.save()
        return instance


class TransactionRejectionForm(forms.Form):
    """
    فرم رد تراکنش
    """
    REJECTION_REASON_CHOICES = [
        ('name_mismatch', 'عدم تطابق نام'),
        ('amount_mismatch', 'عدم تطابق مبلغ'),
        ('account_mismatch', 'عدم تطابق حساب'),
    ]

    rejection_reason = forms.ChoiceField(
        choices=REJECTION_REASON_CHOICES,
        required=True,
        label='دلیل رد',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='لطفاً دلیل رد تراکنش را انتخاب کنید'
    )

