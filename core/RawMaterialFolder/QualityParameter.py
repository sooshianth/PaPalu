from django.db import models


class QualityParameter(models.Model):
    """پارامتر کیفیت - Quality Parameter"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="نام پارامتر"
    )
    
    class Meta:
        verbose_name = "پارامتر کیفیت"
        verbose_name_plural = "پارامترهای کیفیت"
        ordering = ['name']
    
    def __str__(self):
        return self.name
