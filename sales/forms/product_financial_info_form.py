from django import forms
from django.contrib.contenttypes.models import ContentType
from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo
from core.ProductFolder.ProductModel import Product
from django_jalali.forms.widgets import jDateTimeInput, jDateInput


class ProductFinancialInfoForm(forms.ModelForm):
    """
    فرم اطلاعات مالی محصول - قیمت و شرایط فروش
    """
    
    class Meta:
        model = ProductFinancialInfo
        fields = ['product', 'price', 'deadline', 'condition', 'loading_date', 'condition_description', 'description']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'انتخاب محصول'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'قیمت محصول'
            }),
            'deadline': jDateInput(attrs={
                'class': 'form-control',
                'placeholder': 'مهلت اعتبار قیمت'
            }),
            'condition': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'شرط'
            }),
            'loading_date': jDateTimeInput(attrs={
                'class': 'form-control',
                'placeholder': 'زمان بارگیری'
            }),
            'condition_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'توضیحات شرایط'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'توضیحات (اختیاری)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('user', None)
        accessible_fields = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)
        
        # اعمال محدودیت‌های دسترسی فیلدی
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            fields_to_remove = []
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    fields_to_remove.append(field_name)
            
            for field_name in fields_to_remove:
                del self.fields[field_name]
        
        # تنظیم فیلد product به صورت SelectField
        if 'product' in self.fields:
            self.fields['product'] = forms.ModelChoiceField(
                queryset=Product.objects.all().order_by('code'),
                required=True,
                label='محصول',
                widget=forms.Select(attrs={
                    'class': 'form-control',
                    'placeholder': 'انتخاب محصول'
                }),
                empty_label='-- انتخاب محصول --'
            )
        
        # تنظیم فیلدهای اجباری
        required_fields = ['product', 'price', 'deadline', 'condition', 'condition_description']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # تنظیم فیلدهای اختیاری
        optional_fields = ['description', 'loading_date']
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
    
    def clean_price(self):
        """اعتبارسنجی قیمت"""
        price = self.cleaned_data.get('price')
        
        if price is None:
            raise forms.ValidationError('قیمت الزامی است.')
        
        if price <= 0:
            raise forms.ValidationError('قیمت باید بزرگتر از صفر باشد.')
        
        return price
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        
        # بررسی اینکه همه فیلدهای اجباری پر شده‌اند
        required_fields = ['product', 'price', 'deadline', 'condition', 'condition_description']
        for field_name in required_fields:
            if field_name not in cleaned_data or not cleaned_data.get(field_name):
                self.add_error(field_name, f'فیلد {self.fields[field_name].label} الزامی است.')
        
        return cleaned_data


def get_accessible_financial_info_fields(user, financial_info_form: ProductFinancialInfoForm = None):
    """
    محاسبه دسترسی فیلدهای فرم اطلاعات مالی محصول برای ایجاد/ویرایش
    
    Args:
        user: کاربر
        financial_info_form: فرم اطلاعات مالی محصول (اختیاری)
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که در فرم نمایش داده می‌شوند
    display_fields = {
        'product': 'product',
        'price': 'price',
        'deadline': 'deadline',
        'condition': 'condition',
        'loading_date': 'loading_date',
        'condition_description': 'condition_description',
        'description': 'description',
    }
    
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}
    
    from access.models.FieldAccessUserModel import FieldAccessRule
    from django.contrib.contenttypes.models import ContentType
    
    content_type = ContentType.objects.get_for_model(ProductFinancialInfo)
    accessible_fields = {}
    
    for display_name, model_field_name in display_fields.items():
        rule = FieldAccessRule.objects.filter(
            user=user,
            content_type=content_type,
            field_name=model_field_name,
            access_type='edit'
        ).first()
        
        if rule is None:
            accessible_fields[display_name] = True
        else:
            accessible_fields[display_name] = rule.allowed
    
    return accessible_fields

