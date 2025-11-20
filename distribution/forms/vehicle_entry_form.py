from django import forms
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TruckInfoModel import TruckInfo
import re


class VehicleEntryForm(forms.Form):
    """فرم ثبت ورود خودرو"""
    
    # فیلدهای اجباری راننده
    driver_national_id = forms.CharField(
        required=True,
        label='شماره ملی راننده',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره ملی راننده',
            'maxlength': '10',
            'pattern': '[0-9]{10}',
            'required': True
        })
    )
    
    driver_name = forms.CharField(
        required=True,
        label='نام راننده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام راننده',
            'required': True
        })
    )
    
    driver_mobile = forms.CharField(
        required=True,
        label='شماره همراه راننده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09XXXXXXXXX',
            'type': 'tel',
            'pattern': '09[0-9]{9}',
            'required': True
        })
    )
    
    # فیلدهای پلاک (اجباری)
    plate_part1 = forms.CharField(
        required=True,
        label='بخش اول پلاک',
        max_length=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': 'ایران 99',
            'maxlength': '2',
            'required': True
        })
    )
    
    plate_part2 = forms.CharField(
        required=True,
        label='بخش دوم پلاک (عدد + حرف)',
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': '123ب',
            'maxlength': '5',
            'required': True
        })
    )
    
    plate_part3 = forms.CharField(
        required=True,
        label='بخش سوم پلاک',
        max_length=2,
        widget=forms.TextInput(attrs={
            'class': 'form-control plate-input',
            'placeholder': '21',
            'maxlength': '2',
            'required': True
        })
    )
    
    # فیلدهای اختیاری
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
    
    driver_description = forms.CharField(
        required=False,
        label='توضیحات شخص',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'توضیحات شخص',
            'rows': 3
        })
    )
    
    # فایل کارت ملی (اجباری)
    national_card_file = forms.FileField(
        required=True,
        label='کارت ملی',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf',
            'capture': 'environment',
            'required': True
        })
    )
    
    def clean_driver_national_id(self):
        driver_national_id = self.cleaned_data.get('driver_national_id')
        if driver_national_id:
            # بررسی فرمت شماره ملی (10 رقم)
            if not re.match(r'^\d{10}$', driver_national_id):
                raise forms.ValidationError('شماره ملی باید 10 رقم باشد.')
        return driver_national_id
    
    def clean_driver_mobile(self):
        driver_mobile = self.cleaned_data.get('driver_mobile')
        if driver_mobile:
            # بررسی فرمت شماره همراه (09XXXXXXXXX)
            if not re.match(r'^09\d{9}$', driver_mobile):
                raise forms.ValidationError('شماره همراه باید با فرمت 09XXXXXXXXX باشد.')
        return driver_mobile
    
    def clean_national_card_file(self):
        national_card_file = self.cleaned_data.get('national_card_file')
        if national_card_file:
            # بررسی فرمت فایل
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
            file_name = national_card_file.name.lower()
            if '.' in file_name:
                file_extension = '.' + file_name.split('.')[-1]
            else:
                file_extension = ''
            if file_extension not in allowed_extensions:
                raise forms.ValidationError('فرمت فایل کارت ملی باید JPG، PNG یا PDF باشد.')
            
            # بررسی اندازه فایل (حداکثر 5 مگابایت)
            if national_card_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError('حجم فایل کارت ملی نباید بیشتر از 5 مگابایت باشد.')
        
        return national_card_file
    
    def clean(self):
        cleaned_data = super().clean()
        plate_part1 = cleaned_data.get('plate_part1')
        plate_part2 = cleaned_data.get('plate_part2')
        plate_part3 = cleaned_data.get('plate_part3')
        
        # بررسی اینکه همه بخش‌های پلاک پر شده باشند
        if not all([plate_part1, plate_part2, plate_part3]):
            raise forms.ValidationError('تمام بخش‌های پلاک الزامی است.')
        
        return cleaned_data

