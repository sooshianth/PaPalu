from django import forms
from django.forms import BaseFormSet, formset_factory
from core.PersonFolder import Person
from core.PersonFolder.PersonModel import ActivityField
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.PurchasePreferenceModel import PurchasePreference
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from django.contrib.contenttypes.models import ContentType
from typing import Dict, Any, Optional
import re


def clean_empty_to_none(value):
    """تبدیل رشته خالی به None"""
    if value == '' or value is None:
        return None
    return value


class DeliveryAddressForm(forms.Form):
    """فرم آدرس تحویل"""
    
    def __init__(self, *args, **kwargs):
        accessible_fields: Optional[Dict[str, bool]] = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)
        
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    del self.fields[field_name]
    
    postal_code = forms.CharField(
        max_length=10,
        required=False,
        label='کد پستی تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    recipient_name = forms.CharField(
        max_length=100,
        required=False,
        label='نام تحویل گیرنده',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    recipient_national_id = forms.CharField(
        max_length=10,
        required=False,
        label='کد ملی تحویل گیرنده',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    unique_delivery_id = forms.CharField(
        max_length=50,
        required=False,
        label='شناسه یکتا تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    province = forms.CharField(
        max_length=50,
        required=False,
        label='استان تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    city = forms.CharField(
        max_length=50,
        required=False,
        label='شهر تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        required=False,
        label='آدرس پستی تحویل',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )
    delivery_landline = forms.CharField(
        max_length=11,
        required=False,
        label='شماره ثابت هماهنگی تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '02112345678', 'dir': 'ltr'})
    )
    delivery_mobile = forms.CharField(
        max_length=11,
        required=False,
        label='شماره همراه هماهنگی تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09123456789', 'dir': 'ltr'})
    )
    delivery_limit = forms.CharField(
        max_length=200,
        required=False,
        label='محدودیت تحویل',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    recipient_type = forms.ChoiceField(
        choices=[('', 'انتخاب کنید')] + DeliveryAddress.RECIPIENT_TYPE_CHOICES,
        required=False,
        label='نوع تحویل گیرنده',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class RepresentativeForm(forms.Form):
    """فرم نماینده"""
    
    def __init__(self, *args, **kwargs):
        accessible_fields: Optional[Dict[str, bool]] = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)
        
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    del self.fields[field_name]
    
    name = forms.CharField(
        max_length=100,
        required=False,
        label='نام نماینده',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    position = forms.CharField(
        max_length=100,
        required=False,
        label='سمت نماینده',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    mobile = forms.CharField(
        max_length=11,
        required=False,
        label='شماره موبایل نماینده',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '09123456789', 'dir': 'ltr'})
    )
    landline = forms.CharField(
        max_length=11,
        required=False,
        label='شماره ثابت نماینده',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '02112345678', 'dir': 'ltr'})
    )
    confirmation_letter = forms.FileField(
        required=False,
        label='نامه تایید نماینده',
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )


def build_delivery_address_formset(data=None, files=None, accessible_fields: Optional[Dict[str, bool]] = None, initial=None, instance=None):
    """سازنده فرم‌ست آدرس‌های تحویل"""
    DeliveryFormSet = formset_factory(
        form=DeliveryAddressForm,
        extra=1,
        can_delete=True
    )
    if data is None:
        if initial:
            return DeliveryFormSet(initial=initial, form_kwargs={'accessible_fields': accessible_fields})
        return DeliveryFormSet(form_kwargs={'accessible_fields': accessible_fields})
    return DeliveryFormSet(data, files, form_kwargs={'accessible_fields': accessible_fields})


def build_representative_formset(data=None, files=None, accessible_fields: Optional[Dict[str, bool]] = None, initial=None, instance=None):
    """سازنده فرم‌ست نمایندگان"""
    RepresentativeFormSet = formset_factory(
        form=RepresentativeForm,
        extra=1,
        can_delete=True
    )
    if data is None:
        if initial:
            return RepresentativeFormSet(initial=initial, form_kwargs={'accessible_fields': accessible_fields})
        return RepresentativeFormSet(form_kwargs={'accessible_fields': accessible_fields})
    return RepresentativeFormSet(data, files, form_kwargs={'accessible_fields': accessible_fields})


class BankAccountForm(forms.Form):
    """فرم حساب بانکی"""
    
    def __init__(self, *args, **kwargs):
        accessible_fields: Optional[Dict[str, bool]] = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)
        
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    del self.fields[field_name]
    
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    
    account_number = forms.CharField(
        max_length=50,
        required=False,
        label='شماره حساب بانکی',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    shaba_number = forms.CharField(
        max_length=50,
        required=False,
        label='شماره شبا',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    bank_name = forms.CharField(
        max_length=50,
        required=False,
        label='نام بانک',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


def build_bank_account_formset(data=None, files=None, accessible_fields: Optional[Dict[str, bool]] = None, initial=None, instance=None):
    """سازنده فرم‌ست حساب‌های بانکی"""
    BankAccountFormSet = formset_factory(
        form=BankAccountForm,
        extra=1,
        can_delete=True
    )
    if data is None:
        if initial:
            return BankAccountFormSet(initial=initial, form_kwargs={'accessible_fields': accessible_fields})
        return BankAccountFormSet(form_kwargs={'accessible_fields': accessible_fields})
    return BankAccountFormSet(data, files, form_kwargs={'accessible_fields': accessible_fields})


class CreateCustomerForm(forms.Form):
    """فرم ایجاد مشتری"""
    
    def __init__(self, *args, **kwargs):
        # پارامترهای سفارشی
        self.request_user = kwargs.pop('user', None)
        accessible_fields = kwargs.pop('accessible_fields', None)
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        
        # اگر map دسترسی‌ها داده شده، فیلدهای غیرمجاز را از فرم حذف کن
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    del self.fields[field_name]
    
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
    
    activity_fields = forms.ModelMultipleChoiceField(
        queryset=ActivityField.objects.all(),
        required=False,
        label='حیطه‌های فعالیت',
        widget=forms.CheckboxSelectMultiple()
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
        
        # بررسی تکراری نبودن (فقط در صورت ایجاد جدید)
        if not self.instance:
            if Person.objects.filter(national_id=national_id).exists():
                raise forms.ValidationError('این کد ملی قبلاً ثبت شده است.')
        else:
            # در حالت ویرایش، اگر کد ملی تغییر کرده و تکراری است، خطا بده
            if national_id != self.instance.national_id:
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
    
    def save_customer(self, user, update=False):
        """ذخیره اطلاعات مشتری"""
        
        # ایجاد یا به‌روزرسانی شخص
        national_id = self.cleaned_data.get('national_id')
        name = self.cleaned_data.get('name')
        nature = self.cleaned_data.get('nature')
        
        # اگر به دلیل عدم دسترسی، فیلدهای ضروری موجود نباشند، از ادامه جلوگیری کن
        if not national_id or not name or not nature:
            raise forms.ValidationError('شما دسترسی لازم برای ثبت تمامی فیلدهای ضروری را ندارید.')
        
        if update and self.instance:
            # به‌روزرسانی شخص موجود
            person = self.instance
            person.name = name
            person.nature = nature
            person.registration_number = clean_empty_to_none(self.cleaned_data.get('registration_number'))
            person.birth_date = clean_empty_to_none(self.cleaned_data.get('birth_date'))
            person.introducer = clean_empty_to_none(self.cleaned_data.get('introducer'))
            person.description = clean_empty_to_none(self.cleaned_data.get('description'))
            # sales_expert را تغییر نمی‌دهیم در حالت ویرایش
            person.save()
            
            # مدیریت حیطه‌های فعالیت
            activity_fields = self.cleaned_data.get('activity_fields', [])
            if activity_fields:
                person.activity_fields.set(activity_fields)
            else:
                person.activity_fields.clear()
            
            # اگر کد ملی تغییر کرده باشد
            if national_id != person.national_id:
                # حذف شماره تلفن‌های قدیمی
                person_content_type = ContentType.objects.get_for_model(Person)
                try:
                    old_national_id_int = int(person.national_id)
                except (ValueError, TypeError):
                    old_national_id_int = person.national_id
                PhoneNumber.objects.filter(
                    content_type=person_content_type,
                    object_id=old_national_id_int
                ).delete()
                # تغییر کد ملی
                old_national_id = person.national_id
                person.national_id = national_id
                person.save()
        else:
            # ایجاد شخص جدید
            person = Person.objects.create(
                national_id=national_id,
                name=name,
                nature=nature,
                type='customer',  # نوع شخص مشتری
                registration_number=clean_empty_to_none(self.cleaned_data.get('registration_number')),
                birth_date=clean_empty_to_none(self.cleaned_data.get('birth_date')),
                introducer=clean_empty_to_none(self.cleaned_data.get('introducer')),
                description=clean_empty_to_none(self.cleaned_data.get('description')),
                sales_expert=user.username  # کارشناس فروش فعلی
            )
        
        # مدیریت حیطه‌های فعالیت
        activity_fields = self.cleaned_data.get('activity_fields', [])
        if activity_fields:
            person.activity_fields.set(activity_fields)
        else:
            person.activity_fields.clear()
        
        # ایجاد یا به‌روزرسانی شماره موبایل
        person_content_type = ContentType.objects.get_for_model(Person)
        mobile_number = self.cleaned_data.get('mobile_number')
        
        # تبدیل national_id به عدد برای استفاده در object_id
        try:
            person_national_id_int = int(person.national_id)
        except (ValueError, TypeError):
            person_national_id_int = person.national_id
        
        if update:
            # در حالت ویرایش، شماره‌های قدیمی را حذف و جدید را اضافه می‌کنیم
            PhoneNumber.objects.filter(
                content_type=person_content_type,
                object_id=person_national_id_int,
                phone_type='mobile'
            ).delete()
            PhoneNumber.objects.filter(
                content_type=person_content_type,
                object_id=person_national_id_int,
                phone_type='landline'
            ).delete()
        
        if not mobile_number:
            # اگر دسترسی به فیلد موبایل نبوده، ثبت مشتری بدون موبایل انجام شده است
            # (اجباری بودن فقط در صورت وجود فیلد بررسی می‌شود)
            pass
        else:
            PhoneNumber.objects.create(
                content_type=person_content_type,
                object_id=person_national_id_int,
                phone_type='mobile',
                number=mobile_number,
                is_primary=True
            )
        
        # ایجاد شماره ثابت (در صورت وجود)
        if self.cleaned_data.get('landline_number'):
            PhoneNumber.objects.create(
                content_type=person_content_type,
                object_id=person_national_id_int,
                phone_type='landline',
                number=self.cleaned_data['landline_number'],
                is_primary=False
            )
        
        # اطلاعات مالیاتی و آدرس تحویل و نماینده در view ذخیره می‌شوند
        
        # ایجاد آدرس تحویل (در صورت وجود کد پستی) - این بخش دیگر استفاده نمی‌شود
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

