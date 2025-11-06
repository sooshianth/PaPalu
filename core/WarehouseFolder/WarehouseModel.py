from django.db import models


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
        verbose_name='شناسه انبار'
    )
    
    warehouse_capacity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='ظرفیت انبار'
    )
    
    warehouse_type = models.CharField(
        max_length=20,
        choices=WAREHOUSE_TYPE_CHOICES,
        verbose_name='نوع انبار'
    )
    
    default_product = models.ForeignKey(
        'ProductFolder.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_warehouses',
        verbose_name='کالای پیشفرض'
    )
    
    remaining_capacity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='ظرفیت باقی مانده'
    )
    
    available_capacity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='ظرفیت موجود'
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
        verbose_name = 'انبار'
        verbose_name_plural = 'انبارها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.warehouse_id} - {self.get_warehouse_type_display()}"
