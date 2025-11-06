from django.db import models
from .ProductionInfo import ProductionInfo


class BOM(models.Model):
    """
    شناسه ماده اولیه (Bill of Materials)
    """
    
    production_info = models.ForeignKey(
        ProductionInfo,
        on_delete=models.CASCADE,
        related_name='bom_items',
        verbose_name='اطلاعات تولید'
    )
    
    raw_material = models.CharField(
        max_length=255,
        verbose_name='ماده اولیه (ها)'
    )
    
    unit_used = models.CharField(
        max_length=50,
        verbose_name='واحد به کار رفته (ها)'
    )
    
    original_selection = models.TextField(
        verbose_name='گزیده اصلی(مثلا: موردی روز 1 تا 10 مقدار ماده اولیه)'
    )
    
    class Meta:
        verbose_name = 'ماده اولیه'
        verbose_name_plural = 'مواد اولیه (BOM)'
    
    def __str__(self):
        return f"{self.raw_material} - {self.production_info.product.name}"

