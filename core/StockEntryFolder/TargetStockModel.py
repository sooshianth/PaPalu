from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
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
    
    # Generic relation to either Product or RawMaterial
    to_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('product', 'rawmaterial')},
        verbose_name='نوع آیتم مقصد',
        null=True,
        blank=True
    )
    to_object_id = models.PositiveIntegerField(
        verbose_name='شناسه آیتم مقصد',
        null=True,
        blank=True,
        db_index=True
    )
    to_item = GenericForeignKey('to_content_type', 'to_object_id')
    
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
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='مقدار'
    )
    
    class Meta:
        verbose_name = 'انبار | شب بخیر (مقصد)'
        verbose_name_plural = 'انبار | شب بخیرها (مقصد)'
        indexes = [
            models.Index(fields=['to_content_type', 'to_object_id']),
        ]
    
    def __str__(self):
        destination = self.to_item or 'آیتم نامشخص'
        return f"{destination} به {self.to_warehouse}"
    
    def clean(self):
        """Validate target item and quantity."""
        if not self.to_content_type or not self.to_object_id:
            raise ValidationError(
                'باید یک محصول یا مواد اولیه به عنوان مقصد انتخاب شود.'
            )
        
        if self.quantity and self.quantity <= 0:
            raise ValidationError('مقدار باید بزرگتر از صفر باشد.')
    
    @property
    def unit(self):
        """Get unit from the item's primary/main unit"""
        if self.to_item:
            if self.is_raw_material and hasattr(self.to_item, 'primary_unit'):
                return self.to_item.primary_unit or 'تن'
            elif self.is_product and hasattr(self.to_item, 'main_unit'):
                return self.to_item.main_unit or 'تن'
        return 'تن'
    
    @property
    def is_product(self):
        """Check if the target item is a Product"""
        return self.to_content_type and self.to_content_type.model == 'product'
    
    @property
    def is_raw_material(self):
        """Check if the target item is a RawMaterial"""
        return self.to_content_type and self.to_content_type.model == 'rawmaterial'
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
