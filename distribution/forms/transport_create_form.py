from django import forms
from core.TransportFolder.TransportModel import Transport


class TransportCreateForm(forms.ModelForm):
    """فرم ایجاد حمل جدید"""
    
    # فیلدهای اضافی برای پیوست‌ها
    national_card_file = forms.FileField(
        required=False,
        label='کارت ملی',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf'
        })
    )
    
    official_gazette_file = forms.FileField(
        required=False,
        label='روزنامه رسمی',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf'
        })
    )
    
    # فیلدهای راننده (اختیاری - برای ایجاد Person)
    driver_national_id = forms.CharField(
        required=False,
        label='شماره ملی راننده',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'شماره ملی راننده',
            'maxlength': '10'
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
            'placeholder': 'شماره همراه راننده',
            'type': 'tel'
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
    
    class Meta:
        model = Transport
        fields = [
            'waybill_number',
            'carrier_recruitment',
            'vehicle_type_official',
        ]
        widgets = {
            'waybill_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره بارنامه',
                'required': True
            }),
            'carrier_recruitment': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'باربری جذب',
                'required': True
            }),
            'vehicle_type_official': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['waybill_number'].required = True
        self.fields['carrier_recruitment'].required = True
        self.fields['vehicle_type_official'].required = True
    
    def clean_waybill_number(self):
        waybill_number = self.cleaned_data.get('waybill_number')
        if waybill_number:
            # بررسی تکراری نبودن شماره بارنامه
            if self.instance.pk:
                existing = Transport.objects.filter(waybill_number=waybill_number).exclude(pk=self.instance.pk)
            else:
                existing = Transport.objects.filter(waybill_number=waybill_number)
            
            if existing.exists():
                raise forms.ValidationError('شماره بارنامه تکراری است.')
        
        return waybill_number

