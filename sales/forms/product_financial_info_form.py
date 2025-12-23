from django import forms
from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo
from core.ProductFolder.ProductModel import Product
from django_jalali.forms.widgets import jDateTimeInput, jDateInput
from django_jalali.forms import jDateField, jDateTimeField
from core.helpers import check_field_access_prefer_edit
from django.utils import timezone
from datetime import timedelta
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
                'step': '1',
                'placeholder': 'قیمت به ریال'
            }),
            'deadline': jDateTimeInput(attrs={
                'class': 'form-control jalali-datetime',
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
        labels = {
            'price': 'قیمت فی (ریال)',
            'deadline': 'مهلت اعتبار قیمت',
            'condition': 'شرط',
            'loading_date': 'مدت زمان بارگیری',
            'condition_description': 'توضیحات شرایط',
            'description': 'توضیحات',
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
        
        # تنظیم فیلد deadline به صورت jDateTimeField با تقویم شمسی
        if 'deadline' in self.fields:
            self.fields['deadline'] = jDateTimeField(
                required=True,
                label='مهلت اعتبار قیمت (تاریخ و ساعت)',
                widget=jDateTimeInput(attrs={
                    'class': 'form-control jalali-datetime',
                    'placeholder': 'مهلت اعتبار قیمت',
                    'dir': 'ltr'
                })
            )
            
        # اضافه کردن فیلد مخفی برای تاریخ بینهایت
        self.fields['infinite_deadline'] = forms.BooleanField(
            required=False,
            label='تاریخ بینهایت',
            widget=forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'infinite_deadline_checkbox'
            })
        )
        
        # تنظیم فیلدهای اجباری
        required_fields = ['product', 'price', 'condition', 'condition_description']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # deadline فقط زمانی اجباری است که infinite_deadline فعال نباشد
        if 'deadline' in self.fields:
            self.fields['deadline'].required = False  # چک می‌شود در clean
        
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
        
        # بررسی محدودیت منطقی قیمت (حداکثر 10 میلیارد ریال)
        if price > 10000000000:
            raise forms.ValidationError('قیمت وارد شده بیش از حد مجاز است. لطفاً قیمت معتبر وارد کنید.')
        
        return price
    
    def clean_deadline(self):
        """اعتبارسنجی deadline - تاریخ و ساعت شمسی"""
        # ابتدا infinite_deadline را از data خام بخوان (قبل از clean)
        infinite_deadline = self.data.get('infinite_deadline', False)
        if isinstance(infinite_deadline, str):
            infinite_deadline = infinite_deadline.lower() in ('true', 'on', '1')
        
        deadline = self.cleaned_data.get('deadline')
        
        # اگر تاریخ بینهایت انتخاب شده، تاریخ 99 سال بعد را ست می‌کنیم
        if infinite_deadline:
            # استفاده از timezone.now() برای گرفتن datetime با timezone
            now = timezone.now()
            # تبدیل به jdatetime
            now_jalali = jdatetime.datetime.fromgregorian(datetime=now)
            # تاریخ 99 سال بعد
            infinite_jalali = jdatetime.datetime(now_jalali.year + 99, 12, 29, 23, 59, 59)
            # تبدیل به gregorian datetime با timezone
            infinite_gregorian = infinite_jalali.togregorian()
            # اضافه کردن timezone
            infinite_aware = timezone.make_aware(infinite_gregorian)
            return infinite_aware
        
        if deadline:
            try:
                # deadline از jDateTimeField می‌آید
                # تبدیل به timezone-aware datetime
                if isinstance(deadline, jdatetime.datetime):
                    # تبدیل jdatetime به datetime
                    deadline_gregorian = deadline.togregorian()
                    deadline = timezone.make_aware(deadline_gregorian)
                elif not timezone.is_aware(deadline):
                    deadline = timezone.make_aware(deadline)
                
                # بررسی اینکه تاریخ در گذشته نباشد
                now = timezone.now()
                if deadline < now:
                    raise forms.ValidationError('تاریخ مهلت اعتبار نمی‌تواند در گذشته باشد. لطفاً تاریخ امروز یا آینده را انتخاب کنید.')
                
                # بررسی محدودیت منطقی (حداکثر 10 سال در آینده برای تاریخ های عادی)
                ten_years_later = now + timedelta(days=365 * 10)
                if deadline > ten_years_later:
                    raise forms.ValidationError('تاریخ مهلت اعتبار نمی‌تواند بیش از 10 سال در آینده باشد. برای تاریخ بینهایت از گزینه مربوطه استفاده کنید.')
                
                return deadline
            except forms.ValidationError:
                raise
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
        
        # بررسی deadline یا infinite_deadline
        # ابتدا از data خام بخوان (قبل از clean)
        infinite_deadline_raw = self.data.get('infinite_deadline', False)
        if isinstance(infinite_deadline_raw, str):
            infinite_deadline = infinite_deadline_raw.lower() in ('true', 'on', '1')
        else:
            infinite_deadline = bool(infinite_deadline_raw)
        
        deadline = cleaned_data.get('deadline')
        
        # اگر infinite_deadline فعال است، deadline باید از clean_deadline آمده باشد
        # اگر infinite_deadline فعال نیست و deadline هم نیست، خطا بده
        if not infinite_deadline and not deadline:
            self.add_error('deadline', 'لطفاً تاریخ مهلت اعتبار را وارد کنید یا گزینه "بینهایت" را انتخاب کنید.')
        
        # بررسی اینکه سایر فیلدهای اجباری پر شده‌اند
        required_fields = ['price', 'condition', 'condition_description']
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
        
        # deadline از clean_deadline به صورت timezone-aware datetime برمی‌گردد
        # Django ORM به صورت خودکار آن را ذخیره می‌کند
        if 'deadline' in self.cleaned_data and self.cleaned_data['deadline']:
            instance.deadline = self.cleaned_data['deadline']
        
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

