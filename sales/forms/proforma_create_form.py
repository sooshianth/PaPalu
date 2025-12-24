from django import forms
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.OrderModel import Order
from core.PersonFolder.PersonModel import Person
from core.helpers import check_field_access_prefer_edit
import jdatetime


class CreateProformaForm(forms.ModelForm):
    """
    فرم ایجاد/ویرایش پیش فاکتور
    """
    
    class Meta:
        model = Proforma
        fields = ['proforma_number', 'validity_date', 'company', 'description']
        widgets = {
            'proforma_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره سریال پیش فاکتور'
            }),
            'validity_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'تاریخ اعتبار سریال'
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
        
        # تنظیم فیلد order به صورت TextInput برای autocomplete
        self.fields['order'] = forms.CharField(
                required=True,
                label='سفارش',
            widget=forms.TextInput(attrs={
                'class': 'form-control order-autocomplete',
                'placeholder': 'جستجوی سفارش با شماره یا نام مشتری...',
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
        
        # اضافه کردن فیلد مخفی برای ذخیره ID مشتری
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
        
        # شماره پیش فاکتور باید خالی باشد تا بعد از انتخاب سفارش پر شود
        # تولید خودکار در JavaScript انجام می‌شود
        
        # تنظیم فیلدهای اجباری
        required_fields = ['order', 'proforma_number', 'validity_date', 'customer', 'company']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # تنظیم فیلدهای اختیاری
        optional_fields = ['description', 'order_id', 'customer_id']
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
    
    def _generate_proforma_number(self, order_number=None):
        """
        تولید خودکار شماره پیش فاکتور
        فرمت: PF + 4 رقم آخر سفارش + 2 رقم رندوم
        مثال: سفارش 1000123 → PF012373
        """
        import random
        
        if order_number:
            # تبدیل به رشته
            order_str = str(order_number)
            
            # استخراج 4 رقم آخر از شماره سفارش
            if len(order_str) >= 4:
                last_four = order_str[-4:]
            else:
                last_four = order_str.zfill(4)
        else:
            # اگر شماره سفارش نداریم، از تاریخ استفاده می‌کنیم
            import jdatetime
            now = jdatetime.datetime.now()
            last_four = now.strftime('%m%d')
        
        # تولید 2 رقم رندوم (10 تا 99)
        random_two = random.randint(10, 99)
        
        # فرمت نهایی: PF + 4 رقم آخر + 2 رقم رندوم
        return f"PF{last_four}{random_two}"
    
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
        """
        بررسی کامل بودن اطلاعات مشتری
        توجه: customer در اینجا یک رشته است، نه شیء Person
        بررسی واقعی در clean() انجام می‌شود
        """
        customer = self.cleaned_data.get('customer')
        # این فیلد فقط برای نمایش است، validation واقعی در clean() انجام می‌شود
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
        
        # پیدا کردن سفارش
        try:
            order = Order.objects.get(order_number=order_id, order_type='sale')
            self._order = order
            
            # تولید خودکار شماره پیش فاکتور اگر خالی باشد
            if not cleaned_data.get('proforma_number'):
                cleaned_data['proforma_number'] = self._generate_proforma_number(order_id)
        except Order.DoesNotExist:
            self.add_error('order', 'سفارش انتخاب شده یافت نشد یا نوع آن فروش نیست.')
            return cleaned_data
        
        # پردازش customer_id
        customer_id = cleaned_data.get('customer_id', '').strip()
        
        if not customer_id:
            # اگر customer_id وجود ندارد، از مشتری سفارش استفاده کن
            if order.customer:
                customer_id = order.customer.national_id
                cleaned_data['customer_id'] = customer_id
            else:
                self.add_error('customer', 'سفارش انتخاب شده مشتری ندارد.')
                return cleaned_data
        
        # پیدا کردن مشتری
        try:
            customer = Person.objects.get(national_id=customer_id, type='customer')
            self._customer = customer
            
            # بررسی کامل بودن اطلاعات مشتری
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
                self.add_error('customer', error_message)
                # ذخیره اطلاعات مشتری و فیلدهای ناقص برای استفاده در تمپلیت
                self._customer_id = customer_id
                self._missing_fields = missing_fields
                self._customer_obj = customer
                return cleaned_data
            
        except Person.DoesNotExist:
            self.add_error('customer', 'مشتری یافت نشد.')
            return cleaned_data
        
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
    proforma_field_mapping = {
        'order': ('Proforma', 'order'),
        'order_id': None,  # فیلد مخفی، همیشه دسترسی دارد
        'proforma_number': ('Proforma', 'proforma_number'),
        'validity_date': ('Proforma', 'validity_date'),
        'customer': ('Proforma', 'customer'),
        'customer_id': None,  # فیلد مخفی، همیشه دسترسی دارد
        'company': ('Proforma', 'company'),
        'description': ('Proforma', 'description'),
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in proforma_field_mapping.keys()}

    # استفاده از سیستم جدید FieldPermission
    accessible_fields = {}
    for display_name, mapping_value in proforma_field_mapping.items():
        if mapping_value is None:
            # فیلدهایی که نیازی به بررسی دسترسی ندارند (مثل order_id, customer_id)
            accessible_fields[display_name] = True
        else:
            model_name, model_field_name = mapping_value
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            Proforma,
            model_field_name,
        )

    return accessible_fields

