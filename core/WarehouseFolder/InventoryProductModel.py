from django.db import models
from django_jalali.db import models as jmodels
from .InventoryModel import Inventory
from ..ProductFolder import Product


class InventoryProduct(models.Model):
    """
    مدل محصولات موجود در موجودیت انبار
    هر موجودیت می‌تواند شامل چندین محصول با مقادیر مختلف باشد
    """
    
    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='موجودیت',
        blank=True,
        null=True
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name='inventory_records',
        verbose_name='محصول',
        blank=True,
        null=True
    )
    
    unit = models.CharField(
        max_length=50,
        verbose_name='واحد',
        blank=True,
        null=True
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='مقدار',
        blank=True,
        null=True
    )
    
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        blank=True,
        null=True
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی',
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = 'انبار | محصول موجودیت'
        verbose_name_plural = 'انبار | محصولات موجودیت'
        ordering = ['product']
        unique_together = ['inventory', 'product']
    
    def __str__(self):
        warehouse_id = self.inventory.warehouse.warehouse_id if self.inventory and self.inventory.warehouse else 'N/A'
        product = str(self.product) if self.product else 'N/A'
        quantity = self.quantity or 'N/A'
        unit = self.unit or 'N/A'
        return f"{warehouse_id} - {product} - {quantity} {unit}"
