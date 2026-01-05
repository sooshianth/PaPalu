from django import forms
from core.OrderFolder.InvoiceModel import Invoice
from core.OrderFolder.OrderModel import Order
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.helpers import check_field_access_prefer_edit
import jdatetime


class CreateInvoiceForm(forms.ModelForm):
    """
    فرم ایجاد/ویرایش فاکتور
    """
    
    class Meta:
        model = Invoice
        fields = ['tax_invoice_number', 'customer_tax_type', 'issue_date', 'invoice_file', 'description']
        widgets = {
            'tax_invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره صورتحساب مالیاتی'
            }),
            'customer_tax_type': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'نوع مالیاتی مشتری'
            }),
            'issue_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'تاریخ صدور فاکتور'
            }),
            'invoice_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'توضیحات (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('user', None)
        accessible_fields = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)
        
        # ذخیره company_display برای استفاده در تمپلیت
        self.company_display = None
        
        # اعمال محدودیت‌های دسترسی فیلدی
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            fields_to_remove = []
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    fields_to_remove.append(field_name)
            
            for field_name in fields_to_remove:
                del self.fields[field_name]
        
        # تنظیم فیلد order به صورت TextInput برای autocomplete
        self.fields['order'] = forms.CharField(
            required=True,
            label='سفارش',
            widget=forms.TextInput(attrs={
                'class': 'form-control order-autocomplete',
                'placeholder': 'جستجوی سفارش خرید با شماره...',
                'autocomplete': 'off'
            })
        )
        
        # اضافه کردن فیلد مخفی برای ذخیره شماره سفارش
        self.fields['order_id'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput()
        )
        
        # تنظیم فیلد customer به صورت readonly (پر می‌شود بعد از انتخاب سفارش)
        self.fields['customer'] = forms.CharField(
            required=True,
            label='مشتری',
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'بعد از انتخاب سفارش تکمیل می‌شود',
                'readonly': True,
                'style': 'background-color: #e9ecef;'
            })
        )
        
        # اضافه کردن فیلد مخفی برای ذخیره ID تامین‌کننده
        self.fields['customer_id'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput()
        )
        
        # تنظیم فیلد company - شرکت خودمان (تامین نهاده سیمرغ)
        if 'company' in self.fields:
            # دریافت یا ایجاد شرکت تامین نهاده سیمرغ
            company = self._get_or_create_company()
            if company:
                # استفاده از HiddenInput برای company تا مقدار در POST ارسال شود
                self.fields['company'] = forms.ModelChoiceField(
                    queryset=Person.objects.filter(pk=company.pk),
                    required=True,
                    label='شرکت',
                    widget=forms.HiddenInput(),
                    initial=company
                )
                # مقدار اولیه را تنظیم می‌کنیم
                self.initial['company'] = company
                # ذخیره company برای استفاده در تمپلیت
                self.company_display = company
        
        # تنظیم فیلدهای اجباری
        required_fields = ['order', 'tax_invoice_number', 'customer_tax_type', 'issue_date', 'customer', 'company']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # تنظیم فیلدهای اختیاری
        optional_fields = ['description', 'order_id', 'customer_id', 'invoice_file']
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
    
    def _get_or_create_company(self):
        """
        دریافت یا ایجاد شرکت تامین نهاده سیمرغ
        """
        company_name = 'تامین نهاده سیمرغ'
        
        # جستجو برای پیدا کردن شرکت
        company = Person.objects.filter(name=company_name).first()
        
        if not company:
            # اگر شرکت پیدا نشد، ایجاد می‌کنیم
            try:
                company = Person.objects.create(
                    national_id='0000000000',
                    name=company_name,
                    type='supplier',
                    nature='legal'
                )
            except Exception as e:
                # اگر national_id تکراری بود، سعی می‌کنیم پیدا کنیم
                company = Person.objects.filter(name__icontains='تامین نهاده').first()
                if not company:
                    pass
        
        return company
    
    def clean_issue_date(self):
        """اعتبارسنجی تاریخ صدور فاکتور"""
        issue_date = self.cleaned_data.get('issue_date')
        
        if issue_date:
            # بررسی اینکه تاریخ در گذشته نباشد (می‌تواند امروز یا آینده باشد)
            today = jdatetime.date.today()
            # می‌توانیم اجازه دهیم که تاریخ در گذشته هم باشد (برای فاکتورهای قدیمی)
            # اگر می‌خواهید فقط تاریخ امروز و آینده را بپذیرید، این خط را uncomment کنید:
            # if issue_date < today:
            #     raise forms.ValidationError('تاریخ صدور فاکتور نمی‌تواند در گذشته باشد.')
        
        return issue_date
    
    def clean_customer(self):
        """
        بررسی کامل بودن اطلاعات تامین‌کننده
        توجه: customer در اینجا یک رشته است، نه شیء Person
        بررسی واقعی در clean() انجام می‌شود
        """
        customer = self.cleaned_data.get('customer')
        return customer
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        
        # پردازش order_id و تبدیل به order
        order_id = cleaned_data.get('order_id', '').strip()
        order_text = cleaned_data.get('order', '').strip()
        
        if not order_id and order_text:
            # اگر order_id وجود ندارد اما متن وارد شده، سعی کن شماره سفارش را استخراج کن
            import re
            match = re.search(r'(\d+)', order_text)
            if match:
                order_id = match.group(1)
                cleaned_data['order_id'] = order_id
        
        if not order_id:
            self.add_error('order', 'لطفاً یک سفارش را از لیست انتخاب کنید.')
            return cleaned_data
        
        # پیدا کردن سفارش - فقط سفارش‌های فروش که پرداخت انجام شده
        try:
            order = Order.objects.get(order_number=order_id, order_type='sale')
            self._order = order
            
            # بررسی اینکه پرداخت انجام شده باشد (وضعیت باید بعد از pending_accounting_approval باشد)
            allowed_statuses = [
                'pending_accounting_approval',
                'pending_allocation',
                'pending_allocation_approval',
                'pending_factory',
                'pending_unloading_approval',
                'pending_settlement',
                'pending_settlement_approval',
                'archived',
            ]
            
            if order.status in ['cancelled', 'archived']:
                self.add_error('order', 'برای سفارش‌های لغو شده یا بایگانی شده نمی‌توان فاکتور صادر کرد.')
                return cleaned_data
            
            if order.status not in allowed_statuses:
                self.add_error('order', 'برای این سفارش هنوز نمی‌توان فاکتور صادر کرد. پرداخت باید تایید شده باشد.')
                return cleaned_data
            
        except Order.DoesNotExist:
            self.add_error('order', 'سفارش انتخاب شده یافت نشد یا نوع آن فروش نیست.')
            return cleaned_data
        
        # پردازش customer_id
        customer_id = cleaned_data.get('customer_id', '').strip()
        
        if not customer_id:
            # اگر customer_id وجود ندارد، از تامین‌کننده سفارش استفاده کن
            if order.customer:
                customer_id = order.customer.national_id
                cleaned_data['customer_id'] = customer_id
            else:
                self.add_error('customer', 'سفارش انتخاب شده مشتری ندارد.')
                return cleaned_data
        
        # پیدا کردن مشتری
        try:
            customer = Person.objects.get(national_id=customer_id)
            self._customer = customer
            
        except Person.DoesNotExist:
            self.add_error('customer', 'مشتری یافت نشد.')
            return cleaned_data
        
        # تنظیم company - اگر در cleaned_data نباشد، از _get_or_create_company استفاده می‌کنیم
        if 'company' not in cleaned_data or not cleaned_data.get('company'):
            company = self._get_or_create_company()
            if company:
                cleaned_data['company'] = company
                self._company = company
        
        return cleaned_data
    
    def save(self, commit=True):
        """ذخیره فرم"""
        instance = super().save(commit=False)
        
        # تنظیم order از clean
        if hasattr(self, '_order'):
            instance.order = self._order
        
        # تنظیم customer از clean
        if hasattr(self, '_customer'):
            instance.customer = self._customer
        
        # تنظیم company - اول از _company (که در clean تنظیم شده)، سپس از cleaned_data، در نهایت از _get_or_create_company
        if not instance.company:
            if hasattr(self, '_company'):
                instance.company = self._company
            else:
                cleaned_data = getattr(self, 'cleaned_data', {})
                if 'company' in cleaned_data and cleaned_data['company']:
                    instance.company = cleaned_data['company']
                else:
                    company = self._get_or_create_company()
                    if company:
                        instance.company = company
        
        if commit:
            instance.save()
        
        return instance


def get_accessible_invoice_fields(user, invoice_form: CreateInvoiceForm = None):
    """
    محاسبه دسترسی فیلدهای فرم فاکتور برای ایجاد/ویرایش
    
    Args:
        user: کاربر
        invoice_form: فرم فاکتور (اختیاری)
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که در فرم نمایش داده می‌شوند
    invoice_field_mapping = {
        'order': ('Invoice', 'order'),
        'order_id': None,  # فیلد مخفی، همیشه دسترسی دارد
        'tax_invoice_number': ('Invoice', 'tax_invoice_number'),
        'customer_tax_type': ('Invoice', 'customer_tax_type'),
        'issue_date': ('Invoice', 'issue_date'),
        'customer': ('Invoice', 'customer'),
        'customer_id': None,  # فیلد مخفی، همیشه دسترسی دارد
        'company': ('Invoice', 'company'),
        'invoice_file': ('Invoice', 'invoice_file'),
        'description': ('Invoice', 'description'),
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in invoice_field_mapping.keys()}

    # استفاده از سیستم جدید FieldPermission
    accessible_fields = {}
    for display_name, mapping_value in invoice_field_mapping.items():
        if mapping_value is None:
            # فیلدهایی که نیازی به بررسی دسترسی ندارند (مثل order_id, customer_id)
            accessible_fields[display_name] = True
        else:
            model_name, model_field_name = mapping_value
            accessible_fields[display_name] = check_field_access_prefer_edit(
                user,
                Invoice,
                model_field_name,
            )

    return accessible_fields

