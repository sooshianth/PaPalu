from django.db import models
from django.core.exceptions import ValidationError
from .StockEntryModel import StockEntry


class TargetStock(models.Model):
    """
    Model representing the target (to) side of a stock entry.
    """
    
    stock_entry = models.ForeignKey(
        StockEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='target_stocks',
        verbose_name='لاگ انبار'
    )
    
    to_product = models.ForeignKey(
        'core.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='target_stocks',
        verbose_name='به محصول'
    )
    
    to_warehouse = models.ForeignKey(
        'core.Warehouse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='target_stocks',
        verbose_name='به انبار'
    )
    
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='مقدار'
    )
    
    class Meta:
        verbose_name = 'شب بخیر (مقصد)'
        verbose_name_plural = 'شب بخیرها (مقصد)'
    
    def __str__(self):
        destination = self.to_product or 'انبار'
        return f"{destination} به {self.to_warehouse}"
    
    def clean(self):
        """Validate quantity."""
        if self.quantity <= 0:
            raise ValidationError('مقدار باید بزرگتر از صفر باشد.')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
