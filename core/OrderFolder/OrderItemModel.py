from django.db import models
from .OrderModel import Order


class OrderItem(models.Model):
    """مدل اقلام سفارش"""

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
        'ProductFolder.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
        verbose_name='محصول'
    )
    
    # واحد درخواستی
    requested_unit = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='واحد درخواستی'
    )
    
    # مقدار
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='مقدار'
    )
    
    # واحد فرعی (اختیاری)
    secondary_unit = models.CharField(
        max_length=50,
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
        verbose_name = 'قلم سفارش'
        verbose_name_plural = 'اقلام سفارش'
        ordering = ['id']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.product}"
    
    def calculate_total(self):
        """محاسبه مجموع بهای قلم"""
        subtotal = self.quantity * self.unit_price
        total = subtotal - self.discount + self.additional_charges + self.vat
        return total
