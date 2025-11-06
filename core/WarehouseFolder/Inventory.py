from django.db import models
from .WarehouseModel import Warehouse


class Inventory(models.Model):
    """
    مدل موجودیت انبار
    شامل اطلاعات موجودی انبار در یک تاریخ مشخص
    """
    
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='inventories',
        verbose_name='انبار'
    )
    
    date = models.DateField(
        verbose_name='تاریخ'
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
        verbose_name = 'موجودیت'
        verbose_name_plural = 'موجودیت‌ها'
        ordering = ['-date']
        unique_together = ['warehouse', 'date']
    
    def __str__(self):
        return f"{self.warehouse.warehouse_id} - {self.date}"
