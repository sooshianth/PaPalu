from django import forms
from django.forms import BaseFormSet, formset_factory
from django.contrib.contenttypes.models import ContentType
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.ProductFolder.ProductModel import Product
from core.RBACModel import user_has_field_access, get_accessible_fields, user_can_access_field
from decimal import Decimal
from typing import Dict, Any, Optional


class CreateOrderForm(forms.ModelForm):
    """
    فرم ایجاد سفارش
    - شامل اعمال محدودیت‌های دسترسی فیلدی
    - برخی فیلدها فقط نمایشی هستند
    """
    class Meta:
        model = Order
        fields = [
            'order_number',
            'order_type',
            'registration_source',
            'status',
            'freight_payment_type',
        ]
        widgets = {
            'order_number': forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'readonly': True}),
            'order_type': forms.Select(attrs={'class': 'form-control', 'readonly': True, 'disabled': True}),
            'registration_source': forms.Select(attrs={'class': 'form-control', 'readonly': True, 'disabled': True}),
            'status': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'freight_payment_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('user', None)
        accessible_fields: Optional[Dict[str, bool]] = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)

        # اضافه کردن فیلد customer به صورت TextInput برای autocomplete
        from core.PersonFolder.PersonModel import Person
        self.fields['customer'] = forms.CharField(
            required=True,
            label='مشتری',
            widget=forms.TextInput(attrs={
                'class': 'form-control customer-autocomplete',
                'placeholder': 'جستجوی مشتری...',
                'autocomplete': 'off'
            })
        )
        
        # اضافه کردن فیلد مخفی برای ذخیره ID مشتری
        self.fields['customer_id'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput()
        )

        # Set defaults for creation context
        self.fields['order_type'].required = False
        
        if not self.instance or not self.instance.pk:
            self.fields['order_type'].initial = 'sale'
        
        self.fields['registration_source'].required = False

        # حذف فیلد status چون باید توسط backend تنظیم شود
        if 'status' in self.fields:
            del self.fields['status']

        # Required fields
        self.fields['order_number'].required = True
        # تولید خودکار شماره سفارش
        if not self.instance or not self.instance.order_number:
            self.fields['order_number'].initial = Order.generate_order_number()
        
        self.fields['freight_payment_type'].required = True

        # Remove non-accessible fields if mapping provided
        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    del self.fields[field_name]

    def clean(self):
        cleaned_data = super().clean()
        # تبدیل customer_id به customer
        customer_id = cleaned_data.get('customer_id', '').strip()
        customer_text = cleaned_data.get('customer', '').strip()
        
        # اگر customer_id وجود ندارد اما متن وارد شده، سعی کن از متن استخراج کن
        if not customer_id and customer_text:
            # استخراج کد ملی از متن (فرمت: "نام (کد ملی)")
            import re
            match = re.search(r'\((\d+)\)', customer_text)
            if match:
                customer_id = match.group(1)
                cleaned_data['customer_id'] = customer_id
        
        if not customer_id:
            self.add_error('customer', 'لطفاً یک مشتری را از لیست انتخاب کنید.')
            return cleaned_data
        
        if customer_id:
            from core.PersonFolder.PersonModel import Person
            try:
                # بررسی دسترسی: فقط مشتری‌های کارشناس فروش فعلی (یا همه برای superuser)
                if self.request_user and self.request_user.is_superuser:
                    customer = Person.objects.get(national_id=customer_id, type='customer')
                elif self.request_user:
                    customer = Person.objects.get(national_id=customer_id, type='customer', sales_expert=self.request_user)
                else:
                    customer = Person.objects.get(national_id=customer_id, type='customer')
                
                # ذخیره customer برای استفاده در save
                self._customer = customer
            except Person.DoesNotExist:
                self.add_error('customer', 'مشتری انتخاب شده یافت نشد یا شما دسترسی به آن ندارید.')
            except Person.MultipleObjectsReturned:
                self.add_error('customer', 'چندین مشتری با این کد ملی یافت شد. لطفاً با پشتیبانی تماس بگیرید.')
        
        return cleaned_data

    def save(self, commit=True) -> Order:
        order: Order = super().save(commit=False)
        # تنظیم customer از clean
        if hasattr(self, '_customer'):
            order.customer = self._customer
        # Defaults on create
        if not order.order_type:
            order.order_type = 'sale'
        if not order.registration_source:
            order.registration_source = 'expert'
        if not order.status:
            order.status = 'pending_proforma_issue'
        # اگر شماره سفارش خالی است، تولید کن
        if not order.order_number:
            order.order_number = Order.generate_order_number()
        if commit:
            order.save()
        return order


class OrderItemForm(forms.Form):
    """
    فرم قلم سفارش
    فیلدهای اجباری: product, weight_unit, quantity, unit_price
    اختیاری: bag_weight, discount, additional_charges, vat
    نمایشی: total_purchase_cost (محاسبه بعد از ذخیره)
    """
    WEIGHT_UNIT_CHOICES = [
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
        ('bag', 'کیسه'),
        ('piece', 'عدد'),
    ]
    
    def __init__(self, *args, **kwargs):
        accessible_fields: Optional[Dict[str, bool]] = kwargs.pop('accessible_fields', None)
        super().__init__(*args, **kwargs)

        if isinstance(accessible_fields, dict) and hasattr(self, 'fields'):
            for field_name, allowed in list(accessible_fields.items()):
                if not allowed and field_name in self.fields:
                    del self.fields[field_name]

    # فیلد id برای ویرایش اقلام موجود
    id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput()
    )

    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        required=True,
        label='محصول',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    weight_unit = forms.ChoiceField(
        choices=WEIGHT_UNIT_CHOICES,
        required=True,
        initial='kg',
        label='واحد وزن',
        widget=forms.Select(attrs={'class': 'form-control weight-unit-select'})
    )
    bag_weight = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='وزن هر کیسه (کیلوگرم)',
        widget=forms.NumberInput(attrs={'class': 'form-control bag-weight-input', 'step': '0.01'}),
        help_text='فقط برای واحد کیسه'
    )
    requested_unit = forms.CharField(
        max_length=50,
        required=False,
        label='واحد (قدیمی)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'style': 'display:none;'})
    )
    quantity = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True,
        label='مقدار/وزن (کیلوگرم)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label='فی (قیمت واحد) (ریال)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    discount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal('0'),
        label='تخفیف',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    additional_charges = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=Decimal('0'),
        label='اضافات',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    vat_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=Decimal('0'),
        label='درصد مالیات بر ارزش افزوده (درصد)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    def clean(self):
        cleaned = super().clean()
        # Ensure non-negative numbers where applicable
        for key in ['quantity', 'unit_price', 'bag_weight', 'discount', 'additional_charges', 'vat_percent']:
            value = cleaned.get(key)
            if value is not None and value < 0:
                self.add_error(key, 'مقدار نمی‌تواند منفی باشد.')
        
        # بررسی اینکه اگر واحد کیسه است، وزن کیسه باید وارد شود
        weight_unit = cleaned.get('weight_unit')
        bag_weight = cleaned.get('bag_weight')
        if weight_unit == 'bag' and not bag_weight:
            self.add_error('bag_weight', 'برای واحد کیسه، وزن هر کیسه الزامی است.')
        
        return cleaned

    def to_instance(self, order: Order) -> OrderItem:
        data: Dict[str, Any] = self.cleaned_data
        item = OrderItem(
            order=order,
            product=data.get('product'),
            weight_unit=data.get('weight_unit'),
            bag_weight=data.get('bag_weight'),
            requested_unit=data.get('requested_unit') or data.get('weight_unit'),  # fallback
            quantity=data.get('quantity'),
            unit_price=data.get('unit_price'),
            discount=data.get('discount') or Decimal('0'),
            additional_charges=data.get('additional_charges') or Decimal('0'),
            vat_percent=data.get('vat_percent') or Decimal('0'),
        )
        return item


class RequiredOrderItemFormSet(BaseFormSet):
    """
    از حداقل یک قلم اطمینان حاصل می‌کند
    """
    def clean(self):
        super().clean()
        has_at_least_one = False
        for form in self.forms:
            # اگر فرم برای حذف علامت خورده باشد، آن را نادیده بگیر
            if form.cleaned_data.get('DELETE', False):
                continue
            if getattr(form, 'cleaned_data', None) and any(
                form.cleaned_data.get(k) for k in ['product', 'requested_unit', 'quantity', 'unit_price']
            ):
                has_at_least_one = True
                break
        if not has_at_least_one:
            raise forms.ValidationError('حداقل یک قلم سفارش باید وارد شود.')


def build_order_item_formset(data=None, accessible_fields: Optional[Dict[str, bool]] = None):
    """
    سازنده فرم‌ست اقلام سفارش با اعمال دسترسی‌ها
    """
    ItemFormSet = formset_factory(
        form=OrderItemForm,
        formset=RequiredOrderItemFormSet,
        extra=1,
        can_delete=True
    )
    if data is None:
        return ItemFormSet(form_kwargs={'accessible_fields': accessible_fields})
    return ItemFormSet(data, form_kwargs={'accessible_fields': accessible_fields})


def get_accessible_order_fields(user, order_form: CreateOrderForm, sample_item_form: OrderItemForm):
    """
    محاسبه دسترسی فیلدهای فرم اصلی سفارش و فرم قلم‌ها
    به سبک ویو ایجاد مشتری
    """
    if user.is_superuser:
        access_main = {name: True for name in order_form.fields.keys()}
        access_item = {name: True for name in sample_item_form.fields.keys()}
        return access_main, access_item

    # Mapping for order form
    order_field_mapping = {
        'order_number': ('Order', 'order_number'),
        'customer': ('Order', 'customer'),
        'customer_id': None,  # فیلد مخفی، همیشه دسترسی دارد
        'order_type': ('Order', 'order_type'),
        'registration_source': ('Order', 'registration_source'),
        'freight_payment_type': ('Order', 'freight_payment_type'),
    }
    # Mapping for item form
    item_field_mapping = {
        'id': None,  # فیلد مخفی، همیشه دسترسی دارد
        'product': ('OrderItem', 'product'),
        'weight_unit': ('OrderItem', 'weight_unit'),
        'bag_weight': ('OrderItem', 'bag_weight'),
        'requested_unit': ('OrderItem', 'requested_unit'),
        'quantity': ('OrderItem', 'quantity'),
        'unit_price': ('OrderItem', 'unit_price'),
        'discount': ('OrderItem', 'discount'),
        'additional_charges': ('OrderItem', 'additional_charges'),
        'vat_percent': ('OrderItem', 'vat_percent'),
    }

    def can_edit_field(model_class, model_field_name):
        # Prefer edit over view
        if user_can_access_field(user, model_class, model_field_name, 'edit'):
            return True
        if user_can_access_field(user, model_class, model_field_name, 'view'):
            return True
        return False

    # Resolve model classes
    from core.OrderFolder.OrderModel import Order as OrderModel
    from core.OrderFolder.OrderItemModel import OrderItem as OrderItemModel

    access_main = {}
    for form_field, mapping_value in order_field_mapping.items():
        if mapping_value is None:
            # فیلدهایی که نیازی به بررسی دسترسی ندارند (مثل customer_id)
            access_main[form_field] = True
        else:
            model_name, model_field = mapping_value
        access_main[form_field] = can_edit_field(OrderModel, model_field)

    access_item = {}
    for form_field, mapping_value in item_field_mapping.items():
        if mapping_value is None:
            # فیلدهایی که نیازی به بررسی دسترسی ندارند (مثل id)
            access_item[form_field] = True
        else:
            model_name, model_field = mapping_value
            access_item[form_field] = can_edit_field(OrderItemModel, model_field)

    return access_main, access_item


class EditOrderForm(CreateOrderForm):
    """
    فرم ویرایش سفارش
    مشابه CreateOrderForm اما برای ویرایش
    """
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        
        # برای ویرایش، شماره سفارش فقط خواندنی است
        if instance and instance.order_number:
            self.fields['order_number'].widget.attrs['readonly'] = True
            
        # تنظیم مقدار اولیه customer برای autocomplete
        if instance and instance.customer:
            self.fields['customer'].initial = f"{instance.customer.name} ({instance.customer.national_id})"
            self.fields['customer_id'].initial = instance.customer.national_id

