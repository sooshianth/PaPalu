from django import forms
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.ProductFolder import Product
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress


class AllocationProductInfoForm(forms.ModelForm):
    """فرم برای اقلام محصول تخصیص"""
    
    class Meta:
        model = AllocationProductInfo
        fields = ['product', 'unit', 'quantity']
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control product-select',
                'placeholder': 'انتخاب محصول'
            }),
            'unit': forms.Select(attrs={
                'class': 'form-control unit-select',
                'placeholder': 'انتخاب واحد'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مقدار',
                'step': '0.001',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        # ذخیره order برای استفاده در متدهای دیگر
        self.order = order
        
        # فیلتر محصولات بر اساس سفارش
        if order:
            order_products = order.order_items.values_list('product_id', flat=True).distinct()
            self.fields['product'].queryset = Product.objects.filter(id__in=order_products)
        else:
            self.fields['product'].queryset = Product.objects.all()
        
        self.fields['product'].empty_label = '-- انتخاب محصول --'
        self.fields['product'].required = True
        self.fields['unit'].required = True
        self.fields['quantity'].required = True
        
        # اگر instance وجود دارد و محصول و واحد دارد، نیازی به تنظیم پیش‌فرض نیست
        # اما اگر instance جدید است و initial data وجود دارد، واحد را از OrderItem بگیریم
        if not self.instance.pk and order:
            # اگر product در initial data وجود دارد، واحد را از OrderItem بگیریم
            if 'product' in self.initial and self.initial['product']:
                product_id = self.initial['product']
                default_unit = self._get_default_unit_from_order(order, product_id)
                if default_unit:
                    self.initial['unit'] = default_unit
    
    def _get_default_unit_from_order(self, order, product_id):
        """
        دریافت واحد پیش‌فرض از OrderItem مربوط به محصول در سفارش
        """
        try:
            order_item = OrderItem.objects.filter(
                order=order,
                product_id=product_id
            ).first()
            
            if order_item and order_item.weight_unit:
                # تبدیل واحد OrderItem به واحد AllocationProductInfo
                unit_mapping = {
                    'kg': 'kg',
                    'ton': 'ton',
                    'bag': 'kg',  # کیسه به کیلوگرم تبدیل می‌شود
                    'piece': 'kg',  # عدد به کیلوگرم تبدیل می‌شود
                }
                return unit_mapping.get(order_item.weight_unit, 'kg')
        except Exception:
            pass
        return None


BaseAllocationProductInfoFormSet = forms.inlineformset_factory(
    Allocation,
    AllocationProductInfo,
    form=AllocationProductInfoForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)


class AllocationProductInfoFormSet(BaseAllocationProductInfoFormSet):
    """FormSet سفارشی که order را به فرم‌ها پاس می‌دهد"""
    
    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
    
    def _construct_form(self, i, **kwargs):
        """ساخت هر فرم با پاس دادن order"""
        kwargs['order'] = self.order
        return super()._construct_form(i, **kwargs)


class CreateAllocationForm(forms.ModelForm):
    """فرم ایجاد تخصیص"""
    
    class Meta:
        model = Allocation
        fields = ['allocation_number', 'allocation_priority', 'requested_machine', 'delivery_postal_code']
        widgets = {
            'allocation_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'شماره تخصیص'
            }),
            'allocation_priority': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'الویت تخصیص',
                'min': '0'
            }),
            'requested_machine': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ماشین درخواستی'
            }),
            'delivery_postal_code': forms.TextInput(attrs={
                'class': 'form-control postal-code-autocomplete',
                'placeholder': 'جستجوی کد پستی تحویل...',
                'maxlength': '20',
                'autocomplete': 'off',
                'dir': 'ltr'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)
        
        # ذخیره order برای استفاده در validation
        self.order = order
        
        # تنظیم فیلدهای اجباری
        self.fields['allocation_number'].required = True
        self.fields['allocation_priority'].required = True
        self.fields['requested_machine'].required = True
        self.fields['delivery_postal_code'].required = True
        
        # اگر order وجود دارد، می‌توانیم لیست آدرس‌های تحویل را برای نمایش در تمپلیت آماده کنیم
        # اما فیلد همچنان TextInput باقی می‌ماند تا کاربر بتواند کد پستی را وارد کند
    
    def clean_delivery_postal_code(self):
        """اعتبارسنجی کد پستی - باید متعلق به مشتری سفارش باشد"""
        postal_code = self.cleaned_data.get('delivery_postal_code')
        
        if not postal_code:
            return postal_code
        
        # اگر order وجود ندارد، نمی‌توانیم validation انجام دهیم
        if not self.order:
            return postal_code
        
        # بررسی اینکه کد پستی متعلق به مشتری سفارش است
        if self.order.customer:
            try:
                delivery_address = DeliveryAddress.objects.get(
                    postal_code=postal_code,
                    person=self.order.customer
                )
                # کد پستی معتبر است
                return postal_code
            except DeliveryAddress.DoesNotExist:
                raise forms.ValidationError(
                    'کد پستی وارد شده معتبر نیست یا متعلق به مشتری این سفارش نیست. '
                    'لطفاً کد پستی معتبر انتخاب کنید.'
                )
        else:
            # اگر سفارش مشتری ندارد، نمی‌توانیم validation انجام دهیم
            raise forms.ValidationError('سفارش فاقد مشتری است. لطفاً ابتدا مشتری را به سفارش اضافه کنید.')
    
    def clean_allocation_number(self):
        allocation_number = self.cleaned_data.get('allocation_number')
        if allocation_number:
            # بررسی تکراری نبودن شماره تخصیص
            if self.instance.pk:
                existing = Allocation.objects.filter(allocation_number=allocation_number).exclude(pk=self.instance.pk)
            else:
                existing = Allocation.objects.filter(allocation_number=allocation_number)
            
            if existing.exists():
                raise forms.ValidationError('شماره تخصیص تکراری است.')
        
        return allocation_number

