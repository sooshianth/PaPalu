from django.db import models
from .ProductModel import Product


class ProductionInfo(models.Model):
    """
    اطلاعات تولید محصول
    """
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='production_info',
        verbose_name='محصول'
    )
    
    formula_id = models.CharField(
        max_length=100,
        verbose_name='شناسه فرمول'
    )
    
    production_time = models.DurationField(
        verbose_name='زمان تولید'
    )
    
    min_batch_production = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل پچ تولید'
    )
    
    raw_material_conversion_guarantee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='ضمنت تبدیل مواد اولیه به محصول'
    )
    
    specific_production_instruction = models.TextField(
        verbose_name='دستور العمل خاص تولید'
    )
    
    sampling_instruction = models.TextField(
        verbose_name='دستور العمل نمونه‌برداری'
    )
    
    pre_consumption_preparation_instruction = models.TextField(
        verbose_name='دستورالعمل آماده‌سازی قبل از مصرف'
    )
    
    natural_waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد ضایعات طبیعی'
    )
    
    natural_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد افت طبیعی'
    )
    
    msds = models.TextField(
        verbose_name='خطرات ایمنی (MSDS)'
    )
    
    production_checklists = models.TextField(
        verbose_name='چک‌لیست‌های ممکن در تولید'
    )
    
    class Meta:
        verbose_name = 'اطلاعات تولید'
        verbose_name_plural = 'اطلاعات تولید'
    
    def __str__(self):
        return f"اطلاعات تولید - {self.product.name}"

