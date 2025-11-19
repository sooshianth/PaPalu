from django import forms
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.OrderModel import Order
from core.PersonFolder.PersonModel import Person
from access.helpers import check_field_access_prefer_edit
import jdatetime


class CreateProformaForm(forms.ModelForm):
    """
    فرم ایجاد/ویرایش پیش فاکتور
    """
    
    class Meta:
        model = Proforma
        fields = ['order', 'proforma_number', 'validity_date', 'customer', 'company', 'description']
        widgets = {
            'order': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب سفارش'
            }),
            'proforma_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره سریال پیش فاکتور'
            }),
            'validity_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'تاریخ اعتبار سریال'
            }),
            'customer': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب مشتری'
            }),
            'company': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'شرکت',
                'readonly': True
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
        
        # تنظیم فیلد order به صورت SelectField - فقط سفارش‌های نوع فروش
        if 'order' in self.fields:
            self.fields['order'] = forms.ModelChoiceField(
                queryset=Order.objects.filter(order_type='sale').select_related('customer').order_by('-created_at'),
                required=True,
                label='سفارش',
                widget=forms.Select(attrs={
                    'class': 'form-control',
                    'placeholder': 'انتخاب سفارش',
                    'onchange': 'updateCustomerFromOrder(this.value)'  # JavaScript برای انتخاب خودکار مشتری
                }),
                empty_label='-- انتخاب سفارش --'
            )
        
        # تنظیم فیلد customer به صورت SelectField - فقط مشتریان
        if 'customer' in self.fields:
            self.fields['customer'] = forms.ModelChoiceField(
                queryset=Person.objects.filter(type='customer').order_by('name'),
                required=True,
                label='مشتری',
                widget=forms.Select(attrs={
                    'class': 'form-control',
                    'placeholder': 'انتخاب مشتری'
                }),
                empty_label='-- انتخاب مشتری --'
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
        required_fields = ['order', 'proforma_number', 'validity_date', 'customer', 'company']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # تنظیم فیلدهای اختیاری
        optional_fields = ['description']
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
            # نیاز به یک national_id داریم - می‌توانیم از settings استفاده کنیم یا یک مقدار ثابت
            # برای اکنون، از یک national_id موقت استفاده می‌کنیم
            # در واقع باید این را از تنظیمات یا از admin دریافت کنیم
            try:
                company = Person.objects.create(
                    national_id='0000000000',  # این باید یک کد ملی معتبر باشد یا از settings بیاید
                    name=company_name,
                    type='supplier',  # یا نوع دیگری که مناسب باشد
                    nature='legal'
                )
            except Exception as e:
                # اگر national_id تکراری بود، سعی می‌کنیم پیدا کنیم
                company = Person.objects.filter(name__icontains='تامین نهاده').first()
                if not company:
                    # اگر هنوز پیدا نشد، یک national_id دیگر امتحان کنیم
                    # در واقع بهتر است این را در settings قرار دهیم
                    pass
        
        return company
    
    def clean_validity_date(self):
        """اعتبارسنجی تاریخ اعتبار"""
        validity_date = self.cleaned_data.get('validity_date')
        
        if validity_date:
            # بررسی اینکه تاریخ در آینده است
            today = jdatetime.date.today()
            if validity_date < today:
                raise forms.ValidationError('تاریخ اعتبار نمی‌تواند در گذشته باشد.')
        
        return validity_date
    
    def clean_customer(self):
        """بررسی کامل بودن اطلاعات مشتری"""
        customer = self.cleaned_data.get('customer')
        
        if customer:
            missing_fields = []
            
            # بررسی نام
            if not customer.name or customer.name.strip() == '':
                missing_fields.append('نام')
            
            # بررسی شماره ملی (این PK است پس همیشه هست، اما بررسی می‌کنیم)
            if not customer.national_id or customer.national_id.strip() == '':
                missing_fields.append('شماره ملی')
            
            # بررسی شماره ثبت شرکت (اگر نوع شخص حقوقی است)
            if customer.nature == 'legal' and (not customer.registration_number or customer.registration_number.strip() == ''):
                missing_fields.append('شماره ثبت شرکت')
            
            # بررسی شماره اقتصادی (از FinancialBanking)
            from core.PersonFolder.FinancialBankingModel import FinancialBanking
            financial_info = FinancialBanking.objects.filter(person=customer).first()
            if not financial_info or not financial_info.economic_code or financial_info.economic_code.strip() == '':
                missing_fields.append('شماره اقتصادی')
            
            # بررسی آدرس (از FinancialBanking یا DeliveryAddress)
            has_address = False
            if financial_info and financial_info.tax_address and financial_info.tax_address.strip() != '':
                has_address = True
            else:
                from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
                delivery_addresses = DeliveryAddress.objects.filter(person=customer)
                if delivery_addresses.exists():
                    for addr in delivery_addresses:
                        if addr.address and addr.address.strip() != '':
                            has_address = True
                            break
            if not has_address:
                missing_fields.append('آدرس')
            
            # بررسی کدپستی (از FinancialBanking یا DeliveryAddress)
            has_postal_code = False
            if financial_info and financial_info.tax_postal_code and financial_info.tax_postal_code.strip() != '':
                has_postal_code = True
            else:
                from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
                delivery_addresses = DeliveryAddress.objects.filter(person=customer)
                if delivery_addresses.exists():
                    for addr in delivery_addresses:
                        if addr.postal_code and addr.postal_code.strip() != '':
                            has_postal_code = True
                            break
            if not has_postal_code:
                missing_fields.append('کدپستی')
            
            # بررسی شماره تلفن
            from core.PersonFolder.PhoneNumberModel import PhoneNumber
            from django.contrib.contenttypes.models import ContentType
            person_content_type = ContentType.objects.get_for_model(customer)
            phone_numbers = PhoneNumber.objects.filter(
                content_type=person_content_type,
                object_id=customer.national_id
            )
            if not phone_numbers.exists():
                missing_fields.append('شماره تلفن')
            
            # اگر فیلدی ناقص است، خطا نمایش می‌دهیم
            if missing_fields:
                error_message = f'اطلاعات مشتری ناقص است. لطفاً فیلدهای زیر را تکمیل کنید: {", ".join(missing_fields)}'
                raise forms.ValidationError(error_message)
        
        return customer
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        
        # بررسی اینکه همه فیلدهای اجباری پر شده‌اند
        required_fields = ['order', 'proforma_number', 'validity_date', 'customer', 'company']
        for field_name in required_fields:
            if field_name not in cleaned_data or not cleaned_data.get(field_name):
                if field_name in self.fields:
                    self.add_error(field_name, f'فیلد {self.fields[field_name].label} الزامی است.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """ذخیره فرم"""
        instance = super().save(commit=False)
        
        # اگر company در cleaned_data نباشد اما در initial باشد
        if not instance.company and 'company' in self.initial:
            company = self._get_or_create_company()
            if company:
                instance.company = company
        
        if commit:
            instance.save()
        
        return instance


def get_accessible_proforma_fields(user, proforma_form: CreateProformaForm = None):
    """
    محاسبه دسترسی فیلدهای فرم پیش فاکتور برای ایجاد/ویرایش
    
    Args:
        user: کاربر
        proforma_form: فرم پیش فاکتور (اختیاری)
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که در فرم نمایش داده می‌شوند
    display_fields = {
        'order': 'order',
        'proforma_number': 'proforma_number',
        'validity_date': 'validity_date',
        'customer': 'customer',
        'company': 'company',
        'description': 'description',
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}

    # استفاده از سیستم جدید FieldPermission
    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            Proforma,
            model_field_name,
        )

    return accessible_fields

