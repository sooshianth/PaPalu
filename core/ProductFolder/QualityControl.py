from django.db import models
from .Product import Product


class QualityControl(models.Model):
    """
    کنترل کیفیت محصول - پارامترهای کلیدی استاندارد
    """
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='quality_control',
        verbose_name='محصول'
    )
    
    requires_post_production_test = models.BooleanField(
        default=False,
        verbose_name='نیاز به آزمایش بعد تولید؟'
    )
    
    standard_key_parameters = models.TextField(
        verbose_name='پارامترهای کلیدی استاندارد هر پالاستر'
    )
    
    upper_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='حد مجاز بالا برای پالاستر'
    )
    
    lower_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='حد پایین مجاز برای پالاستر'
    )
    
    moisture_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='میزان رطوبت'
    )
    
    density = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='چگالی (Density)'
    )
    
    ash_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='درصد خاکستر'
    )
    
    metabolizable_energy = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='انرژی قابل متابولیسم (ME)'
    )
    
    fat = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='چربی'
    )
    
    protein = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='پروتئین'
    )
    
    physical_pre_size = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='اندازه پیش فیزیکی'
    )
    
    storage_conditions = models.TextField(
        verbose_name='شرایط نگهداری'
    )
    
    storage_temperature = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='دما دیگر/ذخیره'
    )
    
    light_sensitive = models.BooleanField(
        default=False,
        verbose_name='حساسیت به نور؟'
    )
    
    class Meta:
        verbose_name = 'کنترل کیفیت'
        verbose_name_plural = 'کنترل کیفیت'
    
    def __str__(self):
        return f"کنترل کیفیت - {self.product.name}"

