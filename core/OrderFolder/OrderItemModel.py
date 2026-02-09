from django.db import models
from decimal import Decimal
from .OrderModel import Order


class OrderItem(models.Model):
    """مدل اقلام سفارش"""
    
    WEIGHT_UNIT_CHOICES = [
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
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
        
        # محاسبه subtotal
        if self.weight_unit == 'piece':
            subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        else:
            weight_in_kg = self.get_weight_in_kg()
            if weight_in_kg == 0:
                return Decimal('0')
            subtotal = Decimal(str(weight_in_kg)) * Decimal(str(self.unit_price))
        
        # محاسبه مالیات
        vat_percent = Decimal(str(self.vat_percent or 0))
        vat_amount = (vat_percent / Decimal('100')) * subtotal
        return vat_amount.quantize(Decimal('0.01'))
    
    def get_weight_in_kg(self):
        """
        محاسبه وزن کل به کیلوگرم (برای محاسبات یکپارچه).
        مقدار برگشتی Decimal برای جلوگیری از خطای ممیز شناور.
        """
        if not self.quantity:
            return Decimal('0')
        q = Decimal(str(self.quantity))
        if self.weight_unit == 'kg':
            return q
        if self.weight_unit == 'ton':
            return q * 1000
        if self.weight_unit == 'bag' and self.bag_weight:
            return q * Decimal(str(self.bag_weight))
        if self.weight_unit == 'piece':
            return q
        return Decimal('0')
    
    def calculate_total(self):
        """
        محاسبه مجموع بهای قلم
        unit_price بر اساس هر کیلوگرم است (مگر برای piece که بر اساس هر عدد است)
        مالیات بر ارزش افزوده به صورت درصدی (vat_percent) محاسبه می‌شود.
        """
        from decimal import Decimal
        
        if not self.quantity or not self.unit_price:
            return Decimal('0')
        
        # برای واحد piece، قیمت مستقیماً برای هر عدد است
        if self.weight_unit == 'piece':
            subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        else:
            # برای سایر واحدها (kg, ton, bag)، ابتدا وزن را به کیلوگرم تبدیل می‌کنیم
            weight_in_kg = self.get_weight_in_kg()
            if weight_in_kg == Decimal('0'):
                return Decimal('0')
            subtotal = weight_in_kg * Decimal(str(self.unit_price))
        
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
        """
        from decimal import Decimal
        
        if not self.quantity:
            return Decimal('0')
        total_quantity = Decimal(str(self.quantity))
        allocated_in_kg = self.get_allocated_quantity()  # مقدار تخصیص یافته در کیلوگرم
        
        # تبدیل مقدار تخصیص یافته به واحد سفارش
        if self.weight_unit == 'kg':
            allocated_in_order_unit = allocated_in_kg
        elif self.weight_unit == 'ton':
            allocated_in_order_unit = allocated_in_kg / Decimal('1000')
        elif self.weight_unit == 'bag' and self.bag_weight:
            allocated_in_order_unit = allocated_in_kg / Decimal(str(self.bag_weight))
        elif self.weight_unit == 'piece':
            allocated_in_order_unit = allocated_in_kg
        else:
            allocated_in_order_unit = allocated_in_kg
        
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
