from django.db import models
from django_jalali.db import models as jmodels
from .WarehouseModel import Warehouse
from ..ProductFolder import Product


class InventoryProduct(models.Model):
    """
    مدل محصولات موجود در انبار
    هر انبار می‌تواند شامل چندین محصول با مقادیر مختلف باشد
    """
    
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='inventory_products',
        verbose_name='انبار',
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
        verbose_name = 'انبار | محصول موجودی'
        verbose_name_plural = 'انبار | محصولات موجودی'
        ordering = ['product']
        unique_together = ['warehouse', 'product']
    
    def __str__(self):
        warehouse_id = self.warehouse.warehouse_id if self.warehouse else 'N/A'
        product = str(self.product) if self.product else 'N/A'
        quantity = self.quantity or 'N/A'
        unit = self.unit or 'N/A'
        return f"{warehouse_id} - {product} - {quantity} {unit}"
