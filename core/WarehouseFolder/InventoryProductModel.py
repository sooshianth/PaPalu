from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django_jalali.db import models as jmodels
from .WarehouseModel import Warehouse


class InventoryItem(models.Model):
    """
    مدل عمومی برای آیتم‌های موجود در انبار
    هر انبار می‌تواند شامل چندین آیتم (محصول یا ماده اولیه) با مقادیر مختلف باشد
    """
    
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='inventory_items',
        verbose_name='انبار',
        blank=True,
        null=True
    )
    
    # Generic relation to either Product or RawMaterial
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('product', 'rawmaterial')},
        verbose_name='نوع آیتم',
        blank=True,
        null=True
    )
    object_id = models.CharField(
        max_length=100,
        verbose_name='شناسه آیتم',
        blank=True,
        null=True,
        db_index=True
    )
    item = GenericForeignKey('content_type', 'object_id')
    
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
        verbose_name = 'انبار | آیتم موجودی'
        verbose_name_plural = 'انبار | آیتم‌های موجودی'
        ordering = ['content_type', 'object_id']
        unique_together = ['warehouse', 'content_type', 'object_id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        warehouse_id = self.warehouse.warehouse_id if self.warehouse else 'N/A'
        item_str = str(self.item) if self.item else 'N/A'
        quantity = self.quantity or 'N/A'
        unit = self.unit or 'N/A'
        item_type = self.content_type.model if self.content_type else 'N/A'
        return f"{warehouse_id} - [{item_type}] {item_str} - {quantity} {unit}"
    
    @property
    def item_type(self):
        """Returns the type of item (product or rawmaterial)"""
        if self.content_type:
            return self.content_type.model
        return None
    
    @property
    def is_product(self):
        """Check if the item is a Product"""
        return self.content_type and self.content_type.model == 'product'
    
    @property
    def is_raw_material(self):
        """Check if the item is a RawMaterial"""
        return self.content_type and self.content_type.model == 'rawmaterial'
