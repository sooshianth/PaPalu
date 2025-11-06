from django.db import models
from .Allocation import Allocation


class AllocationProductInfo(models.Model):
    """مدل اطلاعات محصولات تخصیص"""
    
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='product_infos',
        verbose_name="تخصیص",
        null=True,
        blank=True
    )
    product = models.CharField(
        max_length=255,
        verbose_name="محصول",
        blank=True,
        null=True
    )
    unit = models.CharField(
        max_length=100,
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
        verbose_name = "اطلاعات محصولات تخصیص"
        verbose_name_plural = "اطلاعات محصولات تخصیص"
    
    def __str__(self):
        return f"{self.product} - {self.quantity} {self.unit}"
