from django import forms
from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking


class SupplySettlementTransactionForm(forms.ModelForm):
    """
    فرم ثبت تراکنش برای تسویه سفارش خرید (تأمین)
    
    تفاوت با فروش (جهت پرداخت معکوس است):
    - در تأمین، سرک یعنی تأمین‌کننده بیشتر تحویل داده → ما باید مابه‌التفاوت را به تأمین‌کننده بزنیم (ما بدهکار)
    - در تأمین، کسری یعنی تأمین‌کننده کمتر تحویل داده → تأمین‌کننده باید مابه‌التفاوت را به ما برگرداند (تأمین‌کننده بدهکار)
    
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
                'class': 'form-control',
                'readonly': True,
                'disabled': True
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
        # دریافت difference_amount، supplier و settled_amount از kwargs
        difference_amount = kwargs.pop('difference_amount', None)
        supplier = kwargs.pop('supplier', None)
        settled_amount = kwargs.pop('settled_amount', None)
        
        super().__init__(*args, **kwargs)
        
        # ذخیره مقادیر برای استفاده در clean
        self.difference_amount = difference_amount
        self.settled_amount = settled_amount or 0
        
        # تنظیم discrepancy_type به صورت read-only و بر اساس difference_amount
        discrepancy_type_value = None
        if difference_amount is not None:
            if difference_amount > 0:
                discrepancy_type_value = 'surplus'  # سرک - بیشتر تحویل شده - ما پرداخت می‌کنیم
            elif difference_amount < 0:
                discrepancy_type_value = 'shortage'  # کسری - کمتر تحویل شده - تأمین‌کننده پرداخت می‌کند
        
        if discrepancy_type_value:
            self.fields['discrepancy_type'].initial = discrepancy_type_value
            # غیرفعال کردن فیلد discrepancy_type (read-only)
            self.fields['discrepancy_type'].widget.attrs['readonly'] = True
            self.fields['discrepancy_type'].widget.attrs['disabled'] = True
            self.fields['discrepancy_type'].required = False
        
        # دریافت یا ایجاد شرکت تامین نهاده سیمرغ
        company_name = 'تامین نهاده سیمرغ'
        company = Person.objects.filter(name=company_name).first()
        
        # تعیین نوع discrepancy
        is_surplus = difference_amount and difference_amount > 0
        is_shortage = difference_amount and difference_amount < 0
        
        # فیلتر کردن حساب‌های بانکی بر اساس نوع تسویه
        # در تأمین (خرید)، جهت پرداخت عکس فروش است:
        # سرک = بیشتر تحویل شده → ما باید پول بزنیم
        # کسری = کمتر تحویل شده → تأمین‌کننده باید پول بزند
        if is_surplus:
            # سرک: ما باید پول بزنیم (بابت جنس اضافه‌ای که گرفتیم) - حساب مبدا از حساب‌های تامین نهاده سیمرغ
            if company:
                company_financial_banking = FinancialBanking.objects.filter(person=company).first()
                if company_financial_banking:
                    self.fields['source_account'].queryset = BankAccount.objects.filter(
                        financial_banking=company_financial_banking
                    )
                else:
                    self.fields['source_account'].queryset = BankAccount.objects.none()
            else:
                self.fields['source_account'].queryset = BankAccount.objects.none()
        elif is_shortage:
            # کسری: تأمین‌کننده باید پول بزند (بابت جنسی که کم تحویل داده) - حساب مبدا از حساب‌های تأمین‌کننده
            if supplier:
                supplier_financial_banking = FinancialBanking.objects.filter(person=supplier).first()
                if supplier_financial_banking:
                    self.fields['source_account'].queryset = BankAccount.objects.filter(
                        financial_banking=supplier_financial_banking
                    )
                else:
                    self.fields['source_account'].queryset = BankAccount.objects.none()
            else:
                self.fields['source_account'].queryset = BankAccount.objects.none()
        else:
            # اگر difference_amount صفر باشد
            self.fields['source_account'].queryset = BankAccount.objects.none()
        
        # تنظیم فیلدهای اجباری
        required_fields = [
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
        if is_surplus:
            # سرک: ما پول می‌زنیم → مبدا = حساب شرکت، مقصد = حساب تأمین‌کننده
            self.fields['source_account'].label = 'حساب مبدا (حساب تامین نهاده سیمرغ)'
            self.fields['approval_account_number'].label = 'شماره حساب (حساب تأمین‌کننده)'
        elif is_shortage:
            # کسری: تأمین‌کننده پول می‌زند → مبدا = حساب تأمین‌کننده، مقصد = حساب شرکت
            self.fields['source_account'].label = 'حساب مبدا (حساب تأمین‌کننده)'
            self.fields['approval_account_number'].label = 'شماره حساب (حساب تامین نهاده سیمرغ)'
        else:
            self.fields['source_account'].label = 'حساب مبدا'
            self.fields['approval_account_number'].label = 'شماره حساب'
        self.fields['document_attachment'].label = 'پیوست سند'
        self.fields['accounting_document_number'].label = 'شماره سند حسابداری'
        self.fields['tracking_number'].label = 'شماره پیگیری واریز'
        self.fields['source_bank'].label = 'بانک مقصد'
        self.fields['shaba_number'].label = 'شماره شبا'
        self.fields['inquiry_name'].label = 'نام استعلام شده'
        self.fields['transfer_time'].label = 'ساعت واریز'
    
    def clean_discrepancy_type(self):
        """بازیابی discrepancy_type از initial value اگر disabled باشد"""
        # اگر فیلد disabled باشد، از initial value استفاده می‌کنیم
        if 'discrepancy_type' not in self.cleaned_data or not self.cleaned_data.get('discrepancy_type'):
            return self.fields['discrepancy_type'].initial
        return self.cleaned_data.get('discrepancy_type')
    
    def clean_document_amount(self):
        """اعتبارسنجی مبلغ سند"""
        amount = self.cleaned_data.get('document_amount')
        if amount and amount <= 0:
            raise forms.ValidationError('مبلغ سند باید بیشتر از صفر باشد.')
        
        # بررسی اینکه مجموع مبالغ تسویه شده از مبلغ اختلاف بیشتر نشود
        if self.difference_amount is not None and amount:
            from decimal import Decimal
            max_allowed = abs(Decimal(str(self.difference_amount)))
            new_total = Decimal(str(self.settled_amount)) + Decimal(str(amount))
            
            if new_total > max_allowed:
                remaining = max_allowed - Decimal(str(self.settled_amount))
                raise forms.ValidationError(
                    f'مجموع مبالغ تسویه شده نمی‌تواند از مبلغ اختلاف ({max_allowed:,.0f} ریال) بیشتر شود. '
                    f'حداکثر مبلغ قابل ثبت: {remaining:,.0f} ریال'
                )
        
        return amount
    
    def clean_approval_account_number(self):
        """اعتبارسنجی شماره حساب (بدون محدودیت طول)"""
        account_number = self.cleaned_data.get('approval_account_number')
        if account_number:
            # حذف فاصله‌ها و خط تیره
            account_number = account_number.replace(' ', '').replace('-', '').replace('_', '')
            # بررسی عددی بودن
            if not account_number.isdigit():
                raise forms.ValidationError('شماره حساب باید فقط شامل اعداد باشد.')
        return account_number
    
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
