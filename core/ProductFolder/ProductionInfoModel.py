from django.db import models
from .ProductModel import Product


class ProductionInfo(models.Model):
    """
    اطلاعات تولید محصول
    """
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='production_infos',
        verbose_name='محصول',
        null=True,
        blank=True,
    )
    
    formula_id = models.CharField(
        max_length=100,
        verbose_name='شناسه فرمول',
        null=True,
        blank=True,
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name='نام محصول',
        null=True,
        blank=True,
    )
    
    production_time = models.DurationField(
        verbose_name='زمان تولید',
        null=True,
        blank=True,
    )
    
    min_batch_production = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل پچ تولید',
        null=True,
        blank=True,
    )
    
    raw_material_conversion_guarantee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='ضمنت تبدیل مواد اولیه به محصول',
        null=True,
        blank=True,
    )
    
    specific_production_instruction = models.TextField(
        verbose_name='دستور العمل خاص تولید',
        null=True,
        blank=True,
    )
    
    sampling_instruction = models.TextField(
        verbose_name='دستور العمل نمونه‌برداری',
        null=True,
        blank=True,
    )
    
    pre_consumption_preparation_instruction = models.TextField(
        verbose_name='دستورالعمل آماده‌سازی قبل از مصرف',
        null=True,
        blank=True,
    )
    
    natural_waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد ضایعات طبیعی',
        null=True,
        blank=True,
    )
    
    natural_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد افت طبیعی',
        null=True,
        blank=True,
    )
    
    msds = models.TextField(
        verbose_name='خطرات ایمنی (MSDS)',
        null=True,
        blank=True,
    )
    
    production_checklists = models.TextField(
        verbose_name='چک‌لیست‌های ممکن در تولید',
        null=True,
        blank=True,
    )
    
    class Meta:
        verbose_name = 'محصول | اطلاعات تولید'
        verbose_name_plural = 'محصول | اطلاعات تولید'
    
    def __str__(self):
        if self.product:
            return f"اطلاعات تولید - {self.product.name} ({self.formula_id or ''})"
        return f"اطلاعات تولید - {self.formula_id or 'بدون محصول'}"

