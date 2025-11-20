from django.db import models
from .ProductionInfoModel import ProductionInfo
from core.RawMaterialFolder.RawMaterialModel import RawMaterial


class BOM(models.Model):
    """
    شناسه ماده اولیه (Bill of Materials)
    """
    
    production_info = models.ForeignKey(
        ProductionInfo,
        on_delete=models.CASCADE,
        related_name='bom_items',
        verbose_name='اطلاعات تولید',
        null=True,
        blank=True,
    )
    
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        related_name='bom_usages',
        verbose_name='ماده اولیه',
        null=True,
        blank=True,
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='مقدار ماده اولیه',
        null=True,
        blank=True,
    )
    
    original_selection = models.TextField(
        verbose_name='گزیده اصلی(مثلا: موردی روز 1 تا 10 مقدار ماده اولیه)',
        null=True,
        blank=True,
    )
    
    class Meta:
        verbose_name = 'محصول | ماده اولیه'
        verbose_name_plural = 'محصول | ماده اولیه (BOM)'
    
    def __str__(self):
        raw_material_name = self.raw_material.name if self.raw_material else 'بدون نام'
        if self.production_info and self.production_info.product:
            return f"{raw_material_name} - {self.production_info.product.name}"
        return f"{raw_material_name}"

