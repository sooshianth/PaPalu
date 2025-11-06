from django.db import models
from django_jalali.db import models as jmodels
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
        verbose_name='انبار',
        blank=True,
        null=True
    )
    
    date = jmodels.jDateField(
        verbose_name='تاریخ',
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
        verbose_name = 'موجودیت'
        verbose_name_plural = 'موجودیت‌ها'
        ordering = ['-date']
        unique_together = ['warehouse', 'date']
    
    def __str__(self):
        warehouse_id = self.warehouse.warehouse_id if self.warehouse else 'N/A'
        date = self.date or 'N/A'
        return f"{warehouse_id} - {date}"
