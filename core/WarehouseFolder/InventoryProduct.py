from django.db import models
from .Inventory import Inventory


class InventoryProduct(models.Model):
    """
    مدل محصولات موجود در موجودیت انبار
    هر موجودیت می‌تواند شامل چندین محصول با مقادیر مختلف باشد
    """
    
    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='موجودیت'
    )
    
    product = models.ForeignKey(
        'ProductFolder.Product',
        on_delete=models.CASCADE,
        related_name='inventory_records',
        verbose_name='محصول'
    )
    
    unit = models.CharField(
        max_length=50,
        verbose_name='واحد'
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مقدار'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی'
    )
    
    class Meta:
        verbose_name = 'محصول موجودیت'
        verbose_name_plural = 'محصولات موجودیت'
        ordering = ['product']
        unique_together = ['inventory', 'product']
    
    def __str__(self):
        return f"{self.inventory.warehouse.warehouse_id} - {self.product} - {self.quantity} {self.unit}"
