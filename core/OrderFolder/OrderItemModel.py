from django.db import models
from decimal import Decimal
from .OrderModel import Order


class OrderItem(models.Model):
    """مدل اقلام سفارش"""
    
    # واحدها فقط از تعریف ماده اولیه - RawMaterial.UNIT_CHOICES + bag, piece
    WEIGHT_UNIT_CHOICES = [
        ('gr', 'گرم'),
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
        ('m3', 'متر مکعب'),
        ('ltr', 'لیتر'),
        ('cc', 'میلی لیتر'),
        ('bag', 'کیسه'),
        ('piece', 'عدد'),
    ]

    # Foreign key to Order
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='order_items',
        verbose_name='سفارش'
    )
    
    # محصول (برای سفارش فروش)
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
        verbose_name='محصول'
    )
    
    # ماده اولیه (برای سفارش خرید تامینی)
    raw_material = models.ForeignKey(
        'RawMaterial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
        verbose_name='ماده اولیه'
    )
    
    # توضیحات
    notes = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True,
        help_text='توضیحات خاص این قلم در این سفارش'
    )
    
    # شناسه تخصیص (تخصیص دیفالت تأمین)
    external_allocation_id = models.CharField(
        max_length=100,
        verbose_name='شناسه تخصیص (تخصیص دیفالت تأمین)',
        null=True,
        blank=True
    )
    
    # واحد وزن
    weight_unit = models.CharField(
        max_length=10,
        choices=WEIGHT_UNIT_CHOICES,
        default='kg',
        verbose_name='واحد وزن',
        null=True,
        blank=True
    )
    
    # وزن هر کیسه (در صورتی که واحد کیسه باشد)
    bag_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن هر کیسه (کیلوگرم)',
        help_text='در صورت انتخاب واحد کیسه، وزن هر کیسه را وارد کنید'
    )
    
    # واحد درخواستی (deprecated - استفاده از weight_unit)
    requested_unit = models.CharField(
        max_length=10,
        choices=WEIGHT_UNIT_CHOICES,
        null=True,
        blank=True,
        verbose_name='واحد درخواستی (قدیمی)'
    )
    
    # مقدار/وزن
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='مقدار/وزن',
        help_text='بر اساس واحد انتخابی'
    )
    
    # واحد فرعی (اختیاری)
    secondary_unit = models.CharField(
        max_length=10,
        choices=WEIGHT_UNIT_CHOICES,
        null=True,
        blank=True,
        verbose_name='واحد فرعی'
    )
    
    # نرخ تبدیل واحد فرعی به اصلی
    conversion_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name='نرخ تبدیل واحد فرعی به اصلی'
    )
    
    # فی
    unit_price = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='فی (ریال)'
    )
    
    # تخفیف
    discount = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name='تخفیف'
    )
    
    # اضافات
    additional_charges = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name='اضافات'
    )
    
    # بهای تمام شده بدون احتساب کرایه
    cost_without_freight = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='بهای تمام شده بدون احتساب کرایه'
    )
    
    # درصد مالیات بر ارزش افزوده (VAT percent)
    vat_percent = models.DecimalField(
        max_digits=5,   # e.g., 9.00%
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name='درصد مالیات بر ارزش افزوده'
    )
    
    # بهای تمام شده کرایه خرید
    freight_cost = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='بهای تمام شده کرایه خرید'
    )
    
    # بهای تمام شده خرید
    total_purchase_cost = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='بهای تمام شده خرید'
    )
    
    class Meta:
        verbose_name = 'سفارش | اقلام'
        verbose_name_plural = 'سفارش | اقلام'
        ordering = ['id']
    
    def __str__(self):
        item_name = ''
        if self.product:
            item_name = str(self.product)
        elif self.raw_material:
            item_name = str(self.raw_material)
        else:
            item_name = 'بدون نام'
        return f"{self.order.order_number if self.order else 'N/A'} - {item_name}"
    
    @property
    def vat(self):
        """محاسبه مبلغ مالیات بر ارزش افزوده"""
        from decimal import Decimal
        
        if not self.quantity or not self.unit_price:
            return Decimal('0')
        
        # subtotal مطابق calculate_total: فی به ازای واحد سفارش
        subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        vat_percent = Decimal(str(self.vat_percent or 0))
        vat_amount = (vat_percent / Decimal('100')) * subtotal
        return vat_amount.quantize(Decimal('0.01'))
    
    def _normalize_unit_to_canonical(self, unit_str):
        """واحد را به فرم استاندارد (kg, ton, gr, bag, piece) برمی‌گرداند برای مقایسه."""
        if not unit_str:
            return None
        u = (unit_str or '').strip().lower()
        mapping = {
            'kg': 'kg', 'کیلوگرم': 'kg', 'kilogram': 'kg',
            'ton': 'ton', 'تن': 'ton',
            'gr': 'gr', 'گرم': 'gr', 'gram': 'gr',
            'bag': 'bag', 'کیسه': 'bag',
            'piece': 'piece', 'عدد': 'piece', 'تعداد': 'piece',
        }
        return mapping.get(u, u)

    def get_weight_in_kg(self, quantity=None):
        """
        محاسبه وزن کل به کیلوگرم.
        - برای ماده اولیه: از conversion_factor (اصلی به فرعی در مدل؛ در کد فرعی→اصلی استفاده می‌شود).
        - برای محصول: از conversion_coefficient (فرعی به اصلی)؛ مقدار اصلی = مقدار فرعی × ضریب.
        quantity: اختیاری - اگر نباشد از self.quantity استفاده می‌شود.
        """
        qty = quantity if quantity is not None else self.quantity
        if not qty:
            return Decimal('0')
        q = Decimal(str(qty))
        if self.weight_unit == 'piece':
            return q
        if self.weight_unit == 'bag' and self.bag_weight:
            return q * Decimal(str(self.bag_weight))
        # ماده اولیه: primary = secondary * conversion_factor (در کد به صورت فرعی→اصلی استفاده شده)
        if self.raw_material:
            cf = self.raw_material.conversion_factor
            if not cf or cf <= 0:
                cf = Decimal('1')
            else:
                cf = Decimal(str(cf))
            primary = self.raw_material.primary_unit
            secondary = self.raw_material.secondary_unit
            if self.weight_unit == primary:
                q_primary = q
            elif self.weight_unit == secondary:
                q_primary = q * cf
            else:
                return Decimal('0')
            if primary == 'kg':
                return q_primary
            if secondary == 'kg':
                return q_primary / cf
        # محصول: مثل مواد اولیه؛ فقط ضریب تبدیل فرعی به اصلی. بدون هاردکد برای تن/گرم.
        # مقدار اصلی = مقدار فرعی × conversion_coefficient؛ تبدیل به kg فقط وقتی یکی از واحدها kg باشد.
        if self.product:
            main_unit = self._normalize_unit_to_canonical(self.product.main_unit)
            sec_unit = self._normalize_unit_to_canonical(self.product.secondary_unit)
            cf = self.product.conversion_coefficient
            if not cf or cf <= 0:
                cf = Decimal('1')
            else:
                cf = Decimal(str(cf))
            order_unit = self._normalize_unit_to_canonical(self.weight_unit) or self.weight_unit
            if order_unit == main_unit:
                q_main = q
            elif order_unit == sec_unit:
                q_main = q * cf  # فرعی به اصلی
            else:
                return Decimal('0')
            # تبدیل به kg فقط با استفاده از ضریب و واحد kg (مثل RawMaterial)
            if main_unit == 'kg':
                return q_main
            if sec_unit == 'kg':
                return q_main / cf
            return Decimal('0')
        return Decimal('0')
    
    def kg_to_order_unit(self, kg_value):
        """
        تبدیل کیلوگرم به واحد سفارش. فرمول: primary = secondary * conversion_factor
        یعنی secondary = primary / cf
        """
        if not kg_value or kg_value <= 0:
            return Decimal('0')
        kg_val = Decimal(str(kg_value))
        if self.weight_unit == 'piece':
            return kg_val
        if self.weight_unit == 'bag' and self.bag_weight:
            return kg_val / Decimal(str(self.bag_weight))
        if self.raw_material:
            cf = self.raw_material.conversion_factor
            if not cf or cf <= 0:
                cf = Decimal('1')
            else:
                cf = Decimal(str(cf))
            primary = self.raw_material.primary_unit
            secondary = self.raw_material.secondary_unit
            if self.weight_unit == primary:
                if primary == 'kg':
                    return kg_val
                if primary == 'ton':
                    return kg_val / cf
            elif self.weight_unit == secondary:
                if primary == 'kg':
                    return kg_val / cf
                if secondary == 'kg':
                    return kg_val
        return kg_val
    
    def is_purchased_in_secondary_unit(self):
        """آیا خرید با واحد فرعی (ثانویه) انجام شده؟"""
        return (
            self.raw_material
            and self.weight_unit
            and self.raw_material.secondary_unit == self.weight_unit
        )
    
    def calculate_total(self):
        """
        محاسبه مجموع بهای قلم
        unit_price (فی) بر اساس همان واحد انتخابی سفارش است (ریال/کیلوگرم، ریال/لیتر، ریال/عدد و ...).
        quantity در همان واحد ذخیره شده؛ پس subtotal = quantity * unit_price.
        مالیات بر ارزش افزوده به صورت درصدی (vat_percent) محاسبه می‌شود.
        """
        from decimal import Decimal
        
        if not self.quantity or not self.unit_price:
            return Decimal('0')
        
        # فی همیشه به ازای همان واحد quantity است (عدد، کیلوگرم، لیتر، تن، کیسه و ...)
        subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        
        # محاسبه مالیات بر اساس درصد
        vat_percent = Decimal(str(self.vat_percent or 0))
        vat_amount = (vat_percent / Decimal('100')) * subtotal
        
        # محاسبه نهایی با در نظرگیری تخفیف، اضافات و مالیات درصدی
        discount = Decimal(str(self.discount or 0))
        additional_charges = Decimal(str(self.additional_charges or 0))
        total = subtotal - discount + additional_charges + vat_amount
        return total.quantize(Decimal('0.01'))
    
    def get_allocated_quantity(self):
        """
        محاسبه مجموع مقدار تخصیص یافته در تمام حمل‌ها
        """
        from django.db.models import Sum
        total_allocated = self.transport_allocations.aggregate(
            total=Sum('allocated_quantity')
        )['total']
        return Decimal(str(total_allocated or 0))
    
    def get_remaining_quantity(self):
        """
        محاسبه مقدار باقیمانده برای تخصیص به حمل‌ها
        مقدار باقیمانده در واحد سفارش برمی‌گردد
        RawMaterialInfo.allocated_quantity در همان واحد سفارش ذخیره می‌شود
        """
        from decimal import Decimal
        
        if not self.quantity:
            return Decimal('0')
        total_quantity = Decimal(str(self.quantity))
        allocated_in_order_unit = self.get_allocated_quantity()
        return total_quantity - allocated_in_order_unit
    
    def is_fully_allocated(self):
        """
        بررسی اینکه آیا تمام مقدار این ماده اولیه تخصیص یافته است یا نه
        """
        remaining = self.get_remaining_quantity()
        return remaining <= Decimal('0')
    
    def save(self, *args, **kwargs):
        """
        محاسبه خودکار بهای تمام شده خرید قبل از ذخیره
        """
        # محاسبه بهای تمام شده خرید
        try:
            if self.quantity and self.unit_price:
                total = self.calculate_total()
                # اطمینان از اینکه total یک Decimal معتبر است
                if total is not None:
                    self.total_purchase_cost = total.quantize(Decimal('0.01'))
                else:
                    self.total_purchase_cost = Decimal('0')
            else:
                self.total_purchase_cost = Decimal('0')
        except Exception:
            # در صورت خطا، مقدار صفر قرار می‌دهیم
            self.total_purchase_cost = Decimal('0')
        
        super().save(*args, **kwargs)
