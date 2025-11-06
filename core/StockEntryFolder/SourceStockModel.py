from django.db import models
from django.core.exceptions import ValidationError
from .StockEntryModel import StockEntry


class SourceStock(models.Model):
    """
    Model representing the source (from) side of a stock entry.
    """
    
    stock_entry = models.ForeignKey(
        StockEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_stocks',
        verbose_name='لاگ انبار'
    )
    
    from_product = models.ForeignKey(
        'core.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_stocks',
        verbose_name='از محصول'
    )
    
    from_raw_material = models.ForeignKey(
        'core.RawMaterial',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_stocks',
        verbose_name='از مواد اولیه'
    )
    
    from_warehouse = models.ForeignKey(
        'core.Warehouse',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='source_stocks',
        verbose_name='از انبار'
    )
    
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='مقدار'
    )
    
    class Meta:
        verbose_name = 'صب بخیر (منبع)'
        verbose_name_plural = 'صب بخیرها (منبع)'
    
    def __str__(self):
        source = self.from_product or self.from_raw_material
        return f"{source} از {self.from_warehouse}"
    
    def clean(self):
        """Validate that either product or raw material is specified."""
        if not self.from_product and not self.from_raw_material:
            raise ValidationError(
                'باید حداقل یک محصول یا مواد اولیه به عنوان منبع انتخاب شود.'
            )
        
        if self.from_product and self.from_raw_material:
            raise ValidationError(
                'نمی‌توان هم محصول و هم مواد اولیه را به طور همزمان انتخاب کرد.'
            )
        
        if self.quantity <= 0:
            raise ValidationError('مقدار باید بزرگتر از صفر باشد.')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
