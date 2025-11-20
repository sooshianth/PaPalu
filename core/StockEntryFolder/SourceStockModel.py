from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
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
    
    # Generic relation to either Product or RawMaterial
    from_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('product', 'rawmaterial')},
        verbose_name='نوع آیتم منبع',
        null=True,
        blank=True
    )
    from_object_id = models.PositiveIntegerField(
        verbose_name='شناسه آیتم منبع',
        null=True,
        blank=True,
        db_index=True
    )
    from_item = GenericForeignKey('from_content_type', 'from_object_id')
    
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
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='مقدار'
    )
    
    class Meta:
        verbose_name = 'انبار | صب بخیر (منبع)'
        verbose_name_plural = 'انبار | صب بخیرها (منبع)'
        indexes = [
            models.Index(fields=['from_content_type', 'from_object_id']),
        ]
    
    def __str__(self):
        source = self.from_item or 'آیتم نامشخص'
        return f"{source} از {self.from_warehouse}"
    
    def clean(self):
        """Validate that an item is specified."""
        if not self.from_content_type or not self.from_object_id:
            raise ValidationError(
                'باید یک محصول یا مواد اولیه به عنوان منبع انتخاب شود.'
            )
        
        if self.quantity and self.quantity <= 0:
            raise ValidationError('مقدار باید بزرگتر از صفر باشد.')
    
    @property
    def unit(self):
        """Get unit from the item's primary/main unit"""
        if self.from_item:
            if self.is_raw_material and hasattr(self.from_item, 'primary_unit'):
                return self.from_item.primary_unit or 'تن'
            elif self.is_product and hasattr(self.from_item, 'main_unit'):
                return self.from_item.main_unit or 'تن'
        return 'تن'
    
    @property
    def is_product(self):
        """Check if the source item is a Product"""
        return self.from_content_type and self.from_content_type.model == 'product'
    
    @property
    def is_raw_material(self):
        """Check if the source item is a RawMaterial"""
        return self.from_content_type and self.from_content_type.model == 'rawmaterial'
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
