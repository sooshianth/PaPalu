from django import forms
from core.PersonFolder import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.PurchasePreferenceModel import PurchasePreference
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from django.contrib.contenttypes.models import ContentType
import re


def clean_empty_to_none(value):
    """تبدیل رشته خالی به None"""
    if value == '' or value is None:
        return None
    return value


class CreateCustomerForm(forms.Form):
    """فرم ایجاد مشتری"""
    
    # فیلدهای اجباری
    national_id = forms.CharField(
        max_length=10,
        required=True,
        label='شناسه ملی/کد ملی شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: 1234567890',
            'dir': 'ltr'
        })
    )
    
    name = forms.CharField(
        max_length=50,
        required=True,
        label='نام شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام کامل شخص یا شرکت'
        })
    )
    
    nature = forms.ChoiceField(
        choices=Person.NATURE_CHOICES,
        required=True,
        label='نوع (حقوقی/حقیقی)',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    mobile_number = forms.CharField(
        max_length=11,
        required=True,
        label='شماره همراه شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09123456789',
            'pattern': '[0-9]{11}',
            'dir': 'ltr'
        })
    )
    
    # فیلدهای اختیاری - اطلاعات پایه
    registration_number = forms.CharField(
        max_length=50,
        required=False,
        label='شماره ثبت شرکت شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr'
        })
    )
    
    landline_number = forms.CharField(
        max_length=11,
        required=False,
        label='شماره ثابت شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '02112345678',
            'dir': 'ltr'
        })
    )
    
    birth_date = forms.CharField(
        required=False,
        label='تاریخ تولد شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1370/01/01',
            'dir': 'ltr'
        })
    )
    
    introducer = forms.CharField(
        max_length=100,
        required=False,
        label='معرف',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    user_type = forms.ChoiceField(
        choices=[('', 'انتخاب کنید')] + Person.USER_TYPE_CHOICES,
        required=False,
        label='نوع کاربری شخص',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    description = forms.CharField(
        required=False,
        label='توضیحات شخص',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        })
    )
    
    # فیلدهای اختیاری - اطلاعات مالیاتی
    economic_code = forms.CharField(
        max_length=50,
        required=False,
        label='کد اقتصادی شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr'
        })
    )
    
    tax_postal_code = forms.CharField(
        max_length=10,
        required=False,
        label='کد پستی مالیاتی شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr'
        })
    )
    
    tax_province = forms.CharField(
        max_length=50,
        required=False,
        label='استان مالیاتی شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    tax_city = forms.CharField(
        max_length=50,
        required=False,
        label='شهر مالیاتی شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    tax_address = forms.CharField(
        required=False,
        label='آدرس پستی مالیاتی شخص',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2
        })
    )
    
    # فیلدهای اختیاری - آدرس تحویل
    delivery_postal_code = forms.CharField(
        max_length=10,
        required=False,
        label='کد پستی تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr'
        })
    )
    
    recipient_name = forms.CharField(
        max_length=100,
        required=False,
        label='نام تحویل گیرنده شخص',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    recipient_national_id = forms.CharField(
        max_length=10,
        required=False,
        label='کد ملی تحویل گیرنده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr'
        })
    )
    
    unique_delivery_id = forms.CharField(
        max_length=50,
        required=False,
        label='شناسه یکتا تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr'
        })
    )
    
    delivery_province = forms.CharField(
        max_length=50,
        required=False,
        label='استان تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    delivery_city = forms.CharField(
        max_length=50,
        required=False,
        label='شهر تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    delivery_address = forms.CharField(
        required=False,
        label='آدرس پستی تحویل',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2
        })
    )
    
    delivery_landline = forms.CharField(
        max_length=11,
        required=False,
        label='شماره ثابت هماهنگی تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '02112345678',
            'dir': 'ltr'
        })
    )
    
    delivery_mobile = forms.CharField(
        max_length=11,
        required=False,
        label='شماره همراه هماهنگی تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09123456789',
            'dir': 'ltr'
        })
    )
    
    delivery_limit = forms.CharField(
        max_length=200,
        required=False,
        label='محدودیت تحویل',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    recipient_type = forms.ChoiceField(
        choices=[('', 'انتخاب کنید')] + DeliveryAddress.RECIPIENT_TYPE_CHOICES,
        required=False,
        label='نوع تحویل گیرنده',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    # فیلدهای اختیاری - نماینده
    representative_name = forms.CharField(
        max_length=100,
        required=False,
        label='نام نماینده',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    representative_position = forms.CharField(
        max_length=100,
        required=False,
        label='سمت نماینده',
        widget=forms.TextInput(attrs={
            'class': 'form-control'
        })
    )
    
    representative_mobile = forms.CharField(
        max_length=11,
        required=False,
        label='شماره موبایل نماینده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09123456789',
            'dir': 'ltr'
        })
    )
    
    representative_landline = forms.CharField(
        max_length=11,
        required=False,
        label='شماره ثابت نماینده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '02112345678',
            'dir': 'ltr'
        })
    )
    
    representative_confirmation_letter = forms.FileField(
        required=False,
        label='نامه تایید نماینده',
        widget=forms.FileInput(attrs={
            'class': 'form-control'
        })
    )
    
    def clean_national_id(self):
        """اعتبارسنجی کد ملی"""
        national_id = self.cleaned_data.get('national_id')
        
        if not national_id:
            raise forms.ValidationError('کد ملی الزامی است.')
        
        # بررسی طول
        if len(national_id) != 10:
            raise forms.ValidationError('کد ملی باید 10 رقم باشد.')
        
        # بررسی عددی بودن
        if not national_id.isdigit():
            raise forms.ValidationError('کد ملی باید فقط شامل اعداد باشد.')
        
        # بررسی تکراری نبودن
        if Person.objects.filter(national_id=national_id).exists():
            raise forms.ValidationError('این کد ملی قبلاً ثبت شده است.')
        
        return national_id
    
    def clean_mobile_number(self):
        """اعتبارسنجی شماره همراه"""
        mobile = self.cleaned_data.get('mobile_number')
        
        if not mobile:
            raise forms.ValidationError('شماره همراه الزامی است.')
        
        # بررسی فرمت شماره همراه ایرانی
        if not re.match(r'^09\d{9}$', mobile):
            raise forms.ValidationError('شماره همراه باید با 09 شروع شود و 11 رقم باشد.')
        
        return mobile
    
    def clean_landline_number(self):
        """اعتبارسنجی شماره ثابت"""
        landline = self.cleaned_data.get('landline_number')
        
        if landline and not re.match(r'^0\d{10}$', landline):
            raise forms.ValidationError('شماره ثابت باید با 0 شروع شود و 11 رقم باشد.')
        
        return landline
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        nature = cleaned_data.get('nature')
        registration_number = cleaned_data.get('registration_number')
        
        # برای شخص حقوقی، شماره ثبت الزامی است
        if nature == 'legal' and not registration_number:
            self.add_error('registration_number', 'برای شخص حقوقی، شماره ثبت شرکت الزامی است.')
        
        return cleaned_data
    
    def save_customer(self, user):
        """ذخیره اطلاعات مشتری"""
        
        # ایجاد شخص
        person = Person.objects.create(
            national_id=self.cleaned_data['national_id'],
            name=self.cleaned_data['name'],
            nature=self.cleaned_data['nature'],
            type='customer',  # نوع شخص مشتری
            registration_number=clean_empty_to_none(self.cleaned_data.get('registration_number')),
            birth_date=clean_empty_to_none(self.cleaned_data.get('birth_date')),
            user_type=clean_empty_to_none(self.cleaned_data.get('user_type')),
            introducer=clean_empty_to_none(self.cleaned_data.get('introducer')),
            description=clean_empty_to_none(self.cleaned_data.get('description')),
            sales_expert=user.username  # کارشناس فروش فعلی
        )
        
        # ایجاد شماره موبایل
        person_content_type = ContentType.objects.get_for_model(Person)
        PhoneNumber.objects.create(
            content_type=person_content_type,
            object_id=person.national_id,
            phone_type='mobile',
            number=self.cleaned_data['mobile_number'],
            is_primary=True
        )
        
        # ایجاد شماره ثابت (در صورت وجود)
        if self.cleaned_data.get('landline_number'):
            PhoneNumber.objects.create(
                content_type=person_content_type,
                object_id=person.national_id,
                phone_type='landline',
                number=self.cleaned_data['landline_number'],
                is_primary=False
            )
        
        # ایجاد اطلاعات مالیاتی (در صورت وجود هر یک از فیلدها)
        if any([
            self.cleaned_data.get('economic_code'),
            self.cleaned_data.get('tax_postal_code'),
            self.cleaned_data.get('tax_province'),
            self.cleaned_data.get('tax_city'),
            self.cleaned_data.get('tax_address')
        ]):
            FinancialBanking.objects.create(
                person=person,
                economic_code=clean_empty_to_none(self.cleaned_data.get('economic_code')),
                tax_postal_code=clean_empty_to_none(self.cleaned_data.get('tax_postal_code')),
                tax_province=clean_empty_to_none(self.cleaned_data.get('tax_province')),
                tax_city=clean_empty_to_none(self.cleaned_data.get('tax_city')),
                tax_address=clean_empty_to_none(self.cleaned_data.get('tax_address'))
            )
        
        # ایجاد آدرس تحویل (در صورت وجود کد پستی)
        if self.cleaned_data.get('delivery_postal_code'):
            delivery_address = DeliveryAddress.objects.create(
                person=person,
                postal_code=self.cleaned_data['delivery_postal_code'],
                recipient_name=self.cleaned_data.get('recipient_name', person.name),
                recipient_national_id=clean_empty_to_none(self.cleaned_data.get('recipient_national_id')),
                unique_delivery_id=clean_empty_to_none(self.cleaned_data.get('unique_delivery_id')),
                province=self.cleaned_data.get('delivery_province', ''),
                city=self.cleaned_data.get('delivery_city', ''),
                address=self.cleaned_data.get('delivery_address', ''),
                delivery_limit=clean_empty_to_none(self.cleaned_data.get('delivery_limit')),
                recipient_type=clean_empty_to_none(self.cleaned_data.get('recipient_type'))
            )
            
            # اضافه کردن شماره‌های تماس آدرس تحویل
            delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
            
            if self.cleaned_data.get('delivery_mobile'):
                PhoneNumber.objects.create(
                    content_type=delivery_content_type,
                    object_id=delivery_address.postal_code,
                    phone_type='mobile',
                    number=self.cleaned_data['delivery_mobile'],
                    is_primary=True
                )
            
            if self.cleaned_data.get('delivery_landline'):
                PhoneNumber.objects.create(
                    content_type=delivery_content_type,
                    object_id=delivery_address.postal_code,
                    phone_type='landline',
                    number=self.cleaned_data['delivery_landline'],
                    is_primary=False
                )
        
        # ایجاد نماینده (در صورت وجود نام)
        if self.cleaned_data.get('representative_name'):
            representative = Representative.objects.create(
                person=person,
                name=self.cleaned_data['representative_name'],
                position=self.cleaned_data.get('representative_position') or '',
                confirmation_letter=self.cleaned_data.get('representative_confirmation_letter')
            )
            
            # اضافه کردن شماره‌های تماس نماینده
            rep_content_type = ContentType.objects.get_for_model(Representative)
            
            if self.cleaned_data.get('representative_mobile'):
                PhoneNumber.objects.create(
                    content_type=rep_content_type,
                    object_id=representative.name,
                    phone_type='mobile',
                    number=self.cleaned_data['representative_mobile'],
                    is_primary=True
                )
            
            if self.cleaned_data.get('representative_landline'):
                PhoneNumber.objects.create(
                    content_type=rep_content_type,
                    object_id=representative.name,
                    phone_type='landline',
                    number=self.cleaned_data['representative_landline'],
                    is_primary=False
                )
        
        return person

