from django import forms
from core.TransportFolder.ProductInfoModel import ProductInfo
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.WarehouseFolder.WarehouseModel import Warehouse
from django.contrib.contenttypes.models import ContentType
import re


class LoadingExitForm(forms.Form):
    """فرم ثبت خروج کالا"""
    
    # وزن پر اولیه (برای توزین مرحله‌ای)
    # این فیلد در template به صورت مستقیم اضافه می‌شود و در view از POST دریافت می‌شود
    
    # فیلدهای اجباری بسته‌بندی و انبار
    packaging_type = forms.ChoiceField(
        required=True,
        label='نوع بسته‌بندی',
        choices=ProductInfo.PACKAGING_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        })
    )
    
    origin_warehouse = forms.ModelChoiceField(
        required=False,  # دیگر از form استفاده نمی‌شود - در هر مرحله توزین انتخاب می‌شود
        label='انبار مبدأ',
        queryset=Warehouse.objects.filter(warehouse_type='secondary'),
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        empty_label='-- انتخاب انبار مبدأ --'
    )
    
    destination_warehouse = forms.ModelChoiceField(
        required=True,
        label='انبار مقصد',
        queryset=Warehouse.objects.none(),  # در ویو مقداردهی می‌شود
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        empty_label='-- انتخاب انبار مقصد --'
    )
    
    # شماره حساب راننده (اجباری - اما اگر راننده حساب نداشته باشد، اختیاری می‌شود)
    driver_account_number = forms.ChoiceField(
        required=False,  # در ویو بررسی می‌شود
        label='شماره حساب راننده',
        choices=[],  # در ویو مقداردهی می‌شود
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    # فیلدهای اختیاری - اطلاعات راننده (اگر خالی باشد)
    driver_national_id = forms.CharField(
        required=False,
        label='شماره ملی راننده',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره ملی راننده',
            'maxlength': '10',
            'pattern': '[0-9]{10}'
        })
    )
    
    driver_name = forms.CharField(
        required=False,
        label='نام راننده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام راننده'
        })
    )
    
    driver_mobile = forms.CharField(
        required=False,
        label='شماره همراه راننده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09XXXXXXXXX',
            'type': 'tel',
            'pattern': '09[0-9]{9}'
        })
    )
    
    driver_description = forms.CharField(
        required=False,
        label='توضیحات راننده',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'توضیحات راننده',
            'rows': 3
        })
    )
    
    # فیلدهای اختیاری - اطلاعات حمل
    plate_part1 = forms.CharField(
        required=False,
        label='بخش اول پلاک',
        max_length=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': 'ایران 99',
            'maxlength': '2'
        })
    )
    
    plate_part2 = forms.CharField(
        required=False,
        label='بخش دوم پلاک',
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': '123ب',
            'maxlength': '5'
        })
    )
    
    plate_part3 = forms.CharField(
        required=False,
        label='بخش سوم پلاک',
        max_length=1,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': 'ح',
            'maxlength': '1'
        })
    )
    
    plate_part4 = forms.CharField(
        required=False,
        label='بخش چهارم پلاک',
        max_length=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': '12',
            'maxlength': '2'
        })
    )
    
    vehicle_type = forms.ChoiceField(
        required=False,
        label='نوع ماشین',
        choices=TruckInfo.VEHICLE_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    loading_type = forms.ChoiceField(
        required=False,
        label='نوع بارگیر',
        choices=TruckInfo.LOADING_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def clean_driver_national_id(self):
        driver_national_id = self.cleaned_data.get('driver_national_id')
        if driver_national_id:
            if not re.match(r'^\d{10}$', driver_national_id):
                raise forms.ValidationError('شماره ملی باید 10 رقم باشد.')
        return driver_national_id
    
    def clean_driver_mobile(self):
        driver_mobile = self.cleaned_data.get('driver_mobile')
        if driver_mobile:
            if not re.match(r'^09\d{9}$', driver_mobile):
                raise forms.ValidationError('شماره همراه باید با فرمت 09XXXXXXXXX باشد.')
        return driver_mobile
    
    def clean_new_shaba_number(self):
        shaba_number = self.cleaned_data.get('new_shaba_number', '').strip()
        if shaba_number:
            # فرمت شبا: IR + 24 رقم
            if not re.match(r'^IR\d{24}$', shaba_number):
                raise forms.ValidationError('شماره شبا باید با فرمت IR123456789012345678901234 باشد (IR + 24 رقم).')
        return shaba_number
    
    def clean(self):
        cleaned_data = super().clean()
        # اعتبارسنجی وزن‌ها در view انجام می‌شود (بعد از پردازش مراحل تخلیه)
        return cleaned_data

