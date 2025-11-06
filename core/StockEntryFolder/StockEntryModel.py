from django.db import models
from django_jalali.db import models as jmodels


class StockEntry(models.Model):
    """
    Main model representing stock entry/movement transaction in the warehouse.
    """
    
    transaction_date = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ تراکنش'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='یادداشت‌ها'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ به‌روزرسانی'
    )
    
    class Meta:
        verbose_name = 'لاگ انبار'
        verbose_name_plural = 'لاگ‌های انبار'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['transaction_date']),
        ]
    
    def __str__(self):
        return f"تراکنش انبار - {self.transaction_date.strftime('%Y-%m-%d %H:%M')}"
