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
    
    # محصول
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
        verbose_name='محصول'
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
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='فی (ریال)'
    )
    
    # تخفیف
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name='تخفیف'
    )
    
    # اضافات
    additional_charges = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name='اضافات'
    )
    
    # بهای تمام شده بدون احتساب کرایه
    cost_without_freight = models.DecimalField(
        max_digits=12,
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
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='بهای تمام شده کرایه خرید'
    )
    
    # بهای تمام شده خرید
    total_purchase_cost = models.DecimalField(
        max_digits=12,
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
        return f"{self.order.order_number} - {self.product}"
    
    def get_weight_in_kg(self):
        """
        محاسبه وزن کل به کیلوگرم (برای محاسبات یکپارچه)
        """
        if not self.quantity:
            return 0
        
        if self.weight_unit == 'kg':
            return float(self.quantity)
        elif self.weight_unit == 'ton':
            return float(self.quantity) * 1000
        elif self.weight_unit == 'bag' and self.bag_weight:
            return float(self.quantity) * float(self.bag_weight)
        elif self.weight_unit == 'piece':
            # برای عدد، وزن را همان تعداد در نظر می‌گیریم
            return float(self.quantity)
        return 0
    
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
            
            if weight_in_kg == 0:
                return Decimal('0')
            
            # محاسبه subtotal: وزن به کیلوگرم * قیمت هر کیلوگرم
            subtotal = Decimal(str(weight_in_kg)) * Decimal(str(self.unit_price))
        
        # محاسبه مالیات بر اساس درصد
        vat_percent = Decimal(str(self.vat_percent or 0))
        vat_amount = (vat_percent / Decimal('100')) * subtotal
        
        # محاسبه نهایی با در نظرگیری تخفیف، اضافات و مالیات درصدی
        discount = Decimal(str(self.discount or 0))
        additional_charges = Decimal(str(self.additional_charges or 0))
        total = subtotal - discount + additional_charges + vat_amount
        return total.quantize(Decimal('0.01'))
    
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
