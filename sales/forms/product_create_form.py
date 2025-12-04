from django import forms
from django.forms import BaseFormSet, formset_factory, modelformset_factory, inlineformset_factory
from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from core.WarehouseFolder.WarehouseModel import Warehouse
from django_jalali.db import models as jmodels
from core.helpers import check_field_access_prefer_edit


class CreateProductForm(forms.ModelForm):
    """
    فرم ایجاد محصول - فیلدهای اصلی محصول
    """

    class Meta:
        model = Product
        fields = [
            'code', 'name', 'category', 'subcategory', 'grade', 'physical_shape',
            'main_application', 'is_custom', 'full_description', 'main_unit',
            'secondary_unit', 'conversion_coefficient', 'expiration_date',
            'pellet_granule_diameter', 'image', 'lab_analysis', 
            'invoice_description', 'min_sales_amount', 'tax_percentage',
            'reserve_deposit', 'tax_code', 'accounting_code', 'min_inventory',
            'production_order_point', 'transport_conditions',
            'default_warehouse', 'storage_conditions'
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('user', None)
        accessible_fields = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)

        # اعمال محدودیت‌های دسترسی فیلدی - باید قبل از تنظیمات دیگر انجام شود
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            # فیلدهایی که دسترسی ندارند را حذف می‌کنیم
            fields_to_remove = []
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    fields_to_remove.append(field_name)
            
            # حذف فیلدها
            for field_name in fields_to_remove:
                del self.fields[field_name]

        # تنظیم فیلد physical_shape به صورت CharField (اگر دسترسی داشته باشد)
        if 'physical_shape' in self.fields:
            self.fields['physical_shape'] = forms.CharField(
                max_length=100,
                required=True,
                label='شکل فیزیکی',
                widget=forms.TextInput(attrs={
                    'class': 'form-control',
                    'placeholder': 'مثال: مش-پلت-کرامبل-آجیلی'
                })
            )

        # تنظیم فیلد main_application به ChoiceField (اگر دسترسی داشته باشد)
        if 'main_application' in self.fields:
            self.fields['main_application'] = forms.ChoiceField(
                choices=Product.PRODUCT_APPLICATION_CHOICES,
                required=True,
                label='کاربرد اصلی',
                widget=forms.Select(attrs={
                    'class': 'form-control'
                })
            )

        # تنظیم فیلدهای اجباری (فقط برای فیلدهایی که دسترسی دارند و هنوز در فرم هستند)
        required_fields = ['code', 'name', 'category', 'subcategory', 'grade', 
                          'physical_shape', 'main_application', 'full_description', 
                          'main_unit']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

        # تنظیم فیلدهای اختیاری (فقط برای فیلدهایی که دسترسی دارند و هنوز در فرم هستند)
        optional_fields = ['secondary_unit', 'conversion_coefficient', 
                          'pellet_granule_diameter', 'image', 'lab_analysis', 
                          'invoice_description', 'is_custom', 'expiration_date',
                          'min_sales_amount', 'tax_percentage', 'reserve_deposit',
                          'tax_code', 'accounting_code', 'min_inventory',
                          'production_order_point', 'transport_conditions',
                          'default_warehouse', 'storage_conditions']
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False

    # فیلدهای اجباری
    code = forms.CharField(
        max_length=100,
        required=True,
        label='شناسه محصول',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'dir': 'ltr',
            'placeholder': 'مثال: PRD-001'
        }),
    )

    name = forms.CharField(
        max_length=255,
        required=True,
        label='نام محصول',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'نام کامل محصول را وارد کنید'
        }),
    )

    category = forms.CharField(
        max_length=255,
        required=True,
        label='گروه محصول',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'گروه اصلی محصول'
        }),
    )

    subcategory = forms.CharField(
        max_length=255,
        required=True,
        label='زیر گروه محصول',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'زیر گروه محصول'
        }),
    )

    grade = forms.CharField(
        max_length=255,
        required=True,
        label='گرید',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'گرید محصول'
        }),
    )

    main_application = forms.CharField(
        max_length=255,
        required=True,
        label='کاربرد اصلی',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: جوجه گوشتی روز 1 تا 10'
        }),
    )

    is_custom = forms.BooleanField(
        required=False,
        initial=False,
        label='محصول سفارشی است؟',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
    )

    full_description = forms.CharField(
        required=True,
        label='شرح کامل محصول',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'توضیحات کامل در مورد محصول'
        }),
    )

    main_unit = forms.ChoiceField(
        choices=[
            ('', '-- انتخاب کنید --'),
            ('کیلوگرم', 'کیلوگرم'),
            ('گرم', 'گرم'),
            ('تن', 'تن'),
            ('عدد', 'عدد'),
            ('بسته', 'بسته'),
            ('کیسه', 'کیسه'),
            ('لیتر', 'لیتر'),
        ],
        required=True,
        label='واحد شمارش اصلی',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='واحد اصلی برای اندازه‌گیری محصول'
    )

    secondary_unit = forms.ChoiceField(
        choices=[
            ('', '-- انتخاب کنید --'),
            ('کیلوگرم', 'کیلوگرم'),
            ('گرم', 'گرم'),
            ('تن', 'تن'),
            ('عدد', 'عدد'),
            ('بسته', 'بسته'),
            ('کیسه', 'کیسه'),
            ('لیتر', 'لیتر'),
        ],
        required=False,
        label='واحد شمارش فرعی',
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
    )

    conversion_coefficient = forms.DecimalField(
        max_digits=10,
        decimal_places=4,
        required=False,
        label='ضریب تبدیل اصلی به فرعی',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.0001',
            'placeholder': 'مثال: 1000'
        }),
    )

    expiration_date = forms.CharField(
        max_length=100,
        required=False,
        label='مدت اعتبار',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: 2 سال، 6 ماه، 18 ماه'
        }),
        help_text='مدت زمان اعتبار محصول'
    )

    # فیلدهای اختیاری
    pellet_granule_diameter = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='قطر پلت یا کرامبل (میلی‌متر)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'مثال: 3.5'
        }),
        help_text='قطر به میلی‌متر'
    )

    image = forms.ImageField(
        required=False,
        label='تصویر محصول',
        widget=forms.FileInput(attrs={
            'class': 'form-control'
        }),
    )

    lab_analysis = forms.CharField(
        required=False,
        label='آنالیز آزمایشگاهی محصول',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'نتایج آزمایشگاهی'
        }),
    )

    invoice_description = forms.CharField(
        required=False,
        label='شرح محصول برای پیش فاکتور',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'شرح برای نمایش در پیش فاکتور'
        }),
    )
    
    # فیلدهای فروش و مالی
    min_sales_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='حداقل مقدار سفارش (کیلوگرم)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'حداقل مقدار سفارش'
        }),
    )
    
    tax_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        label='درصد مالیات بر ارزش افزوده',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'مثال: 9'
        }),
    )
    
    reserve_deposit = forms.CharField(
        max_length=255,
        required=False,
        label='احتیاطی سپرده مربوط',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'احتیاطی سپرده'
        }),
    )
    
    tax_code = forms.CharField(
        max_length=255,
        required=False,
        label='کد مالیاتی ماده',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد مالیاتی'
        }),
    )
    
    accounting_code = forms.CharField(
        max_length=255,
        required=False,
        label='کد حسابداری',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد حسابداری'
        }),
    )
    
    min_inventory = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='حداقل موجودی انبار (کیلوگرم)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'حداقل موجودی'
        }),
    )
    
    production_order_point = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='نقطه سفارش تولید (کیلوگرم)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'نقطه تولید'
        }),
    )
    
    transport_conditions = forms.CharField(
        required=False,
        label='شرایط حمل',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'شرایط حمل و نقل'
        }),
    )
    
    default_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all(),
        required=False,
        label='انبار پیش فرض',
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        help_text='انبار پیش‌فرض برای ذخیره این محصول'
    )
    
    storage_conditions = forms.CharField(
        required=False,
        label='شرایط نگهداری',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'شرایط نگهداری محصول'
        }),
    )

    def clean_code(self):
        """اعتبارسنجی کد محصول"""
        code = self.cleaned_data.get('code')

        if not code:
            raise forms.ValidationError('شناسه محصول الزامی است.')
        
        # بررسی طول کد
        if len(code.strip()) < 3:
            raise forms.ValidationError('شناسه محصول باید حداقل 3 کاراکتر باشد.')

        # بررسی تکراری نبودن کد (در صورت ایجاد محصول جدید)
        if not self.instance.pk:
            if Product.objects.filter(code=code).exists():
                raise forms.ValidationError('این کد محصول قبلاً ثبت شده است. لطفاً کد دیگری انتخاب کنید.')
        else:
            # در حالت ویرایش، بررسی کنیم که کد جدید با کد محصول دیگری تداخل نداشته باشد
            if Product.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError('این کد محصول قبلاً برای محصول دیگری ثبت شده است.')
        
        return code.strip()

    def clean_name(self):
        """اعتبارسنجی نام محصول"""
        name = self.cleaned_data.get('name')

        if not name:
            raise forms.ValidationError('نام محصول الزامی است.')
        
        # بررسی طول نام
        if len(name.strip()) < 3:
            raise forms.ValidationError('نام محصول باید حداقل 3 کاراکتر باشد.')

        return name.strip()

    def clean_category(self):
        """اعتبارسنجی گروه محصول"""
        category = self.cleaned_data.get('category')

        if not category:
            raise forms.ValidationError('گروه محصول الزامی است.')

        return category.strip()

    def clean_subcategory(self):
        """اعتبارسنجی زیر گروه محصول"""
        subcategory = self.cleaned_data.get('subcategory')

        if not subcategory:
            raise forms.ValidationError('زیر گروه محصول الزامی است.')

        return subcategory.strip()

    def clean_grade(self):
        """اعتبارسنجی گرید محصول"""
        grade = self.cleaned_data.get('grade')

        if not grade:
            raise forms.ValidationError('گرید محصول الزامی است.')

        return grade.strip()

    def clean_conversion_coefficient(self):
        """اعتبارسنجی ضریب تبدیل"""
        conversion_coefficient = self.cleaned_data.get('conversion_coefficient')
        secondary_unit = self.cleaned_data.get('secondary_unit')

        # اگر واحد فرعی وارد شده، ضریب تبدیل الزامی است
        if secondary_unit and not conversion_coefficient:
            raise forms.ValidationError(
                'در صورت وارد کردن واحد فرعی، ضریب تبدیل الزامی است.'
            )

        if conversion_coefficient and conversion_coefficient <= 0:
            raise forms.ValidationError('ضریب تبدیل باید بزرگتر از صفر باشد.')

        return conversion_coefficient

    def clean_pellet_granule_diameter(self):
        """اعتبارسنجی قطر پلت"""
        diameter = self.cleaned_data.get('pellet_granule_diameter')

        if diameter and diameter <= 0:
            raise forms.ValidationError('قطر پلت باید بزرگتر از صفر باشد.')

        return diameter

    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        secondary_unit = cleaned_data.get('secondary_unit')
        conversion_coefficient = cleaned_data.get('conversion_coefficient')

        # اگر واحد فرعی وارد شده، ضریب تبدیل الزامی است
        if secondary_unit and not conversion_coefficient:
            self.add_error(
                'conversion_coefficient',
                'در صورت وارد کردن واحد فرعی، ضریب تبدیل الزامی است.'
            )

        return cleaned_data


class ProductionInfoForm(forms.ModelForm):
    """
    فرم اطلاعات تولید محصول
    """

    class Meta:
        model = ProductionInfo
        fields = ['formula_id', 'min_batch_production', 'specific_production_instruction']
        widgets = {
            'formula_id': forms.TextInput(attrs={
                'class': 'form-control',
                'dir': 'ltr',
                'placeholder': 'شناسه فرمول'
            }),
            'min_batch_production': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'حداقل بچ تولید (کیلوگرم)'
            }),
            'specific_production_instruction': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'دستور العمل خاص تولید'
            }),
        }
        labels = {
            'formula_id': 'شناسه فرمول',
            'min_batch_production': 'حداقل بچ تولید (کیلوگرم)',
            'specific_production_instruction': 'دستور العمل خاص تولید',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تنظیم فیلدهای اجباری
        self.fields['formula_id'].required = False  # در formset، فیلدها اختیاری هستند
        self.fields['min_batch_production'].required = False
        self.fields['specific_production_instruction'].required = False

    def clean_min_batch_production(self):
        """اعتبارسنجی حداقل بچ تولید"""
        min_batch = self.cleaned_data.get('min_batch_production')

        if min_batch and min_batch <= 0:
            raise forms.ValidationError('حداقل بچ تولید باید بزرگتر از صفر باشد.')

        return min_batch

    def clean(self):
        """اعتبارسنجی کلی فرم ProductionInfo"""
        cleaned_data = super().clean()
        
        # بررسی اینکه آیا حداقل یک فیلد پر شده است
        has_data = any([
            cleaned_data.get('formula_id'),
            cleaned_data.get('min_batch_production'),
            cleaned_data.get('specific_production_instruction'),
        ])
        
        # اگر حداقل یک فیلد پر شده باشد، همه فیلدها باید پر شوند
        if has_data:
            if not cleaned_data.get('formula_id'):
                self.add_error('formula_id', 'شناسه فرمول الزامی است.')
            if not cleaned_data.get('min_batch_production'):
                self.add_error('min_batch_production', 'حداقل بچ تولید الزامی است.')
            if not cleaned_data.get('specific_production_instruction'):
                self.add_error('specific_production_instruction', 'دستور العمل خاص تولید الزامی است.')
        
        return cleaned_data


class BOMForm(forms.ModelForm):
    """
    فرم ماده اولیه (BOM)
    """

    class Meta:
        model = BOM
        fields = ['raw_material', 'quantity']
        widgets = {
            'raw_material': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'ماده اولیه'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'placeholder': 'مقدار (کیلوگرم)'
            }),
        }
        labels = {
            'raw_material': 'ماده اولیه',
            'quantity': 'مقدار ماده اولیه (کیلوگرم)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تنظیم فیلدهای اجباری - در formset، فیلدها اختیاری هستند
        self.fields['raw_material'].required = False
        self.fields['quantity'].required = False

    def clean_quantity(self):
        """اعتبارسنجی مقدار ماده اولیه"""
        quantity = self.cleaned_data.get('quantity')

        if quantity and quantity <= 0:
            raise forms.ValidationError('مقدار ماده اولیه باید بزرگتر از صفر باشد.')

        return quantity

    def clean(self):
        """اعتبارسنجی کلی فرم BOM"""
        cleaned_data = super().clean()
        
        # بررسی اینکه آیا حداقل یک فیلد پر شده است
        has_data = any([
            cleaned_data.get('raw_material'),
            cleaned_data.get('quantity'),
        ])
        
        # اگر حداقل یک فیلد پر شده باشد، همه فیلدها باید پر شوند
        if has_data:
            if not cleaned_data.get('raw_material'):
                self.add_error('raw_material', 'ماده اولیه الزامی است.')
            if not cleaned_data.get('quantity'):
                self.add_error('quantity', 'مقدار ماده اولیه الزامی است.')
        
        return cleaned_data


# ایجاد formset برای ProductionInfo (برای ایجاد)
ProductionInfoFormSet = formset_factory(
    ProductionInfoForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False
)

# ایجاد inlineformset برای BOM که به ProductionInfo لینک می‌شود
BOMInlineFormSet = inlineformset_factory(
    ProductionInfo,
    BOM,
    form=BOMForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False
)

# ایجاد modelformset برای ProductionInfo (برای ویرایش)
ProductionInfoModelFormSet = modelformset_factory(
    ProductionInfo,
    form=ProductionInfoForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False
)

# ایجاد modelformset برای BOM (برای ویرایش)
BOMModelFormSet = modelformset_factory(
    BOM,
    form=BOMForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False
)


def get_accessible_product_fields(user, product_form: CreateProductForm = None):
    """
    محاسبه دسترسی فیلدهای فرم محصول برای ایجاد/ویرایش
    
    Args:
        user: کاربر
        product_form: فرم محصول (اختیاری - اگر None باشد، از فیلدهای پیش‌فرض استفاده می‌شود)
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که در فرم نمایش داده می‌شوند
    display_fields = {
        'code': 'code',
        'name': 'name',
        'category': 'category',
        'subcategory': 'subcategory',
        'grade': 'grade',
        'physical_shape': 'physical_shape',
        'main_application': 'main_application',
        'is_custom': 'is_custom',
        'full_description': 'full_description',
        'main_unit': 'main_unit',
        'secondary_unit': 'secondary_unit',
        'conversion_coefficient': 'conversion_coefficient',
        'expiration_date': 'expiration_date',
        'pellet_granule_diameter': 'pellet_granule_diameter',
        'image': 'image',
        'lab_analysis': 'lab_analysis',
        'invoice_description': 'invoice_description',
        'min_sales_amount': 'min_sales_amount',
        'tax_percentage': 'tax_percentage',
        'reserve_deposit': 'reserve_deposit',
        'tax_code': 'tax_code',
        'accounting_code': 'accounting_code',
        'min_inventory': 'min_inventory',
        'production_order_point': 'production_order_point',
        'transport_conditions': 'transport_conditions',
        'default_warehouse': 'default_warehouse',
        'storage_conditions': 'storage_conditions',
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}

    # استفاده از سیستم جدید FieldPermission
    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            Product,
            model_field_name,
        )

    return accessible_fields
