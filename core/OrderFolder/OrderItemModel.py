from django.db import models
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
        max_length=3,
        choices=UNIT_CHOICES,
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
        max_length=3,
        choices=UNIT_CHOICES,
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
        verbose_name='فی'
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
    
    # مالیات بر ارزش افزوده
    vat = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        verbose_name='مالیات بر ارزش افزوده'
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
        """محاسبه مجموع بهای قلم"""
        if not self.quantity or not self.unit_price:
            return 0
        subtotal = float(self.quantity) * float(self.unit_price)
        total = subtotal - float(self.discount or 0) + float(self.additional_charges or 0) + float(self.vat or 0)
        return total
    
    def save(self, *args, **kwargs):
        """
        محاسبه خودکار بهای تمام شده خرید قبل از ذخیره
        """
        # محاسبه بهای تمام شده خرید
        if self.quantity and self.unit_price:
            self.total_purchase_cost = self.calculate_total()
        
        super().save(*args, **kwargs)
