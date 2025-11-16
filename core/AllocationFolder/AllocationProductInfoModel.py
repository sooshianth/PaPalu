from django.db import models
from .AllocationModel import Allocation
from ..ProductFolder.ProductModel import Product


class AllocationProductInfo(models.Model):
    """مدل اطلاعات محصولات تخصیص"""
    
    UNIT_CHOICES = [
        ('gr', 'گرم'),
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
        ('m3', 'متر مکعب'),
        ('ltr', 'لیتر'),
        ('cc', 'میلی لیتر'),
    ]

    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='product_infos',
        verbose_name="تخصیص",
        null=True,
        blank=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name='allocation_product_infos',
        verbose_name="محصول",
        blank=True,
        null=True
    )
    unit = models.CharField(
        max_length=3,
        choices=UNIT_CHOICES,
        verbose_name="واحد",
        blank=True,
        null=True
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="مقدار",
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "تخصیص | اطلاعات محصولات"
        verbose_name_plural = "تخصیص | اطلاعات محصولات"
    
    def __str__(self):
        product_display = self.product or "نامشخص"
        quantity_display = self.quantity or "نامشخص"
        unit_display = self.unit or "نامشخص"
        return f"{product_display} - {quantity_display} {unit_display}"
