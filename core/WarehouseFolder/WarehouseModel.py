from django.db import models
from django_jalali.db import models as jmodels
from .DefaultItem import DefaultItem


class Warehouse(models.Model):
    """
    مدل انبار
    شامل اطلاعات پایه انبار
    """
    
    WAREHOUSE_TYPE_CHOICES = [
        ('primary', 'اولیه'),
        ('secondary', 'ثانویه'),
    ]
    
    warehouse_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='شناسه انبار',
        null=True,
        blank=True
    )
    
    warehouse_capacity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='ظرفیت انبار',
        null=True,
        blank=True
    )
    
    warehouse_type = models.CharField(
        max_length=20,
        choices=WAREHOUSE_TYPE_CHOICES,
        verbose_name='نوع انبار',
        null=True,
        blank=True
    )
    
    default_item = models.ForeignKey(
        DefaultItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='warehouses',
        verbose_name='آیتم پیشفرض'
    )
    
    remaining_capacity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='ظرفیت باقی مانده',
        null=True,
        blank=True
    )
    
    available_capacity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='ظرفیت موجود',
        null=True,
        blank=True
    )
    
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'انبار'
        verbose_name_plural = 'انبارها'
        ordering = ['-created_at']
    
    def __str__(self):
        warehouse_id = self.warehouse_id or 'N/A'
        warehouse_type = self.get_warehouse_type_display() if self.warehouse_type else 'N/A'
        return f"{warehouse_id} - {warehouse_type}"
