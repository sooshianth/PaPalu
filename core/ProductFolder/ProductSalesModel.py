from django.db import models
from .ProductModel import Product


class ProductSales(models.Model):
    """
    اطلاعات فروش محصول
    """
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='sales_info',
        verbose_name='محصول',
        blank=True,
        null=True,
    )
    
    min_sales_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل مقدار سفارش',
        blank=True,
        null=True,
    )
    
    price_with_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='درصد مالیات بر ارزش افزوده',
        blank=True,
        null=True,
    )
    
    accountings = models.CharField(
        max_length=255,
        verbose_name='کد حسابداری‌ها',
        blank=True,
        null=True,
    )
    
    related_bank_account = models.CharField(
        max_length=255,
        verbose_name='کد مالیاتی ماده',
        blank=True,
        null=True,
    )
    
    inventory_existence = models.BooleanField(
        default=True,
        verbose_name='حداقل موجودی انبار',
        blank=True,
        null=True,
    )
    
    reorder_point_production = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='نقطه سفارش مجدد'
    )
    
    new_production_point = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='نقطه سفارش تولید'
    )
    
    class Meta:
        verbose_name = 'اطلاعات فروش'
        verbose_name_plural = 'اطلاعات فروش'
    
    def __str__(self):
        return f"اطلاعات فروش - {self.product.name}"

