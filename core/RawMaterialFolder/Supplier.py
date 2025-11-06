from django.db import models


class Supplier(models.Model):
    """تامین‌کننده - Supplier"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="نام تامین‌کننده"
    )
    
    class Meta:
        verbose_name = "تامین‌کننده"
        verbose_name_plural = "تامین‌کنندگان"
        ordering = ['name']
    
    def __str__(self):
        return self.name
