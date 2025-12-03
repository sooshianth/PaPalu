from django import forms
from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo
from core.ProductFolder.ProductModel import Product
from django_jalali.forms.widgets import jDateTimeInput, jDateInput
from django_jalali.forms import jDateField
from core.helpers import check_field_access_prefer_edit
import jdatetime


class ProductFinancialInfoForm(forms.ModelForm):
    """
    فرم اطلاعات مالی محصول - قیمت و شرایط فروش
    """
    
    class Meta:
        model = ProductFinancialInfo
        fields = ['price', 'deadline', 'condition', 'loading_date', 'condition_description', 'description']
        widgets = {
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
            'loading_date': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مدت زمان بارگیری (متن)'
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
        
        # اضافه کردن فیلد product به صورت CharField برای autocomplete (قبل از اعمال محدودیت‌ها)
        # چون product در Meta نیست، باید دستی اضافه شود
        if accessible_fields is None or accessible_fields.get('product', True):
            self.fields['product'] = forms.CharField(
                required=True,
                label='محصول',
                widget=forms.TextInput(attrs={
                    'class': 'form-control product-autocomplete',
                    'placeholder': 'جستجوی محصول...',
                    'autocomplete': 'off'
                })
            )
            
            # اضافه کردن فیلد مخفی برای ذخیره ID محصول
            self.fields['product_id'] = forms.CharField(
                required=False,
                widget=forms.HiddenInput()
            )
            
            # اگر instance موجود است و product دارد، مقدار اولیه را تنظیم کن
            if self.instance and self.instance.pk and self.instance.product:
                self.fields['product'].initial = f"{self.instance.product.code} - {self.instance.product.name}"
                self.fields['product_id'].initial = self.instance.product.id
        
        # اعمال محدودیت‌های دسترسی فیلدی
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            fields_to_remove = []
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    fields_to_remove.append(field_name)
            
            for field_name in fields_to_remove:
                del self.fields[field_name]
        
        # تنظیم فیلد deadline به صورت jDateField با تقویم شمسی
        if 'deadline' in self.fields:
            self.fields['deadline'] = jDateField(
                required=True,
                label='مهلت اعتبار قیمت',
                widget=jDateInput(attrs={
                    'class': 'form-control jalali-date',
                    'placeholder': 'مهلت اعتبار قیمت',
                    'dir': 'ltr'
                })
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
    
    def clean_deadline(self):
        """اعتبارسنجی deadline - تاریخ شمسی"""
        deadline = self.cleaned_data.get('deadline')
        
        if deadline:
            # deadline از jDateField می‌آید و خودش jdatetime.date است
            # بررسی اینکه تاریخ در گذشته نباشد (اختیاری - می‌توانید حذف کنید)
            # یا می‌توانید بررسی کنید که تاریخ از امروز کمتر نباشد
            try:
                # اگر نیاز به اعتبارسنجی خاصی دارید، اینجا اضافه کنید
                return deadline
            except Exception as e:
                raise forms.ValidationError(f'خطا در اعتبارسنجی تاریخ: {str(e)}')
        
        return deadline
    
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        
        # تبدیل product_id به product
        product_id = cleaned_data.get('product_id', '').strip()
        product_text = cleaned_data.get('product', '').strip()
        
        # اگر product_id وجود ندارد اما متن وارد شده، سعی کن از متن استخراج کن
        if not product_id and product_text:
            # استخراج ID از متن (فرمت: "کد - نام" یا فقط ID)
            import re
            # اگر متن به صورت "ID - نام" است
            match = re.match(r'^(\d+)', product_text)
            if match:
                product_id = match.group(1)
                cleaned_data['product_id'] = product_id
        
        if not product_id:
            self.add_error('product', 'لطفاً یک محصول را از لیست انتخاب کنید.')
            return cleaned_data
        
        if product_id:
            try:
                # تبدیل به عدد در صورت نیاز
                product_id_int = int(product_id)
                product = Product.objects.get(id=product_id_int)
                # ذخیره product برای استفاده در save
                self._product = product
                # حذف product از cleaned_data تا Django سعی نکند آن را اختصاص دهد
                if 'product' in cleaned_data:
                    del cleaned_data['product']
            except Product.DoesNotExist:
                self.add_error('product', 'محصول انتخاب شده یافت نشد.')
            except (ValueError, TypeError):
                self.add_error('product', 'شناسه محصول معتبر نیست.')
        
        # بررسی اینکه همه فیلدهای اجباری پر شده‌اند
        required_fields = ['price', 'deadline', 'condition', 'condition_description']
        for field_name in required_fields:
            if field_name not in cleaned_data or not cleaned_data.get(field_name):
                if field_name in self.fields:
                    self.add_error(field_name, f'فیلد {self.fields[field_name].label} الزامی است.')
        
        return cleaned_data
    
    def save(self, commit=True):
        """ذخیره فرم - تنظیم product از clean"""
        instance = super().save(commit=False)
        
        # تنظیم product از clean
        if hasattr(self, '_product'):
            instance.product = self._product
        
        # deadline از jDateField مستقیماً jdatetime.date است، نیازی به تبدیل نیست
        # اما برای اطمینان بررسی می‌کنیم
        if 'deadline' in self.cleaned_data and self.cleaned_data['deadline']:
            deadline = self.cleaned_data['deadline']
            # اگر deadline یک jdatetime.date است، مستقیماً استفاده می‌کنیم
            if isinstance(deadline, jdatetime.date):
                instance.deadline = deadline
            elif hasattr(deadline, 'date'):  # اگر datetime باشد
                # تبدیل از datetime به jdatetime.date
                jdate = jdatetime.date.fromgregorian(date=deadline.date())
                instance.deadline = jdate
        
        if commit:
            instance.save()
        
        return instance


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
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}

    # استفاده از سیستم جدید FieldPermission
    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            ProductFinancialInfo,
            model_field_name,
        )

    return accessible_fields

