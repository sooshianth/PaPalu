from django.db import models
from django.utils import timezone
from django_jalali.db import models as jmodels

from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.PersonFolder.PersonModel import Person


class RawMaterialPriceInquiry(models.Model):
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        related_name='price_inquiries',
        verbose_name='ماده اولیه'
    )
    supplier = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='raw_material_price_inquiries',
        verbose_name='تامین‌کننده'
    )
    inquiry_date = jmodels.jDateField(default=timezone.localdate, verbose_name='تاریخ')
    price = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='قیمت')
    delivery_terms = models.CharField(max_length=255, verbose_name='شرایط تحویل')
    loading_location = models.CharField(max_length=255, verbose_name='محل بارگیری')
    freight_unit_price = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True, verbose_name='فی کرایه'
    )
    negotiation_note = models.TextField(null=True, blank=True, verbose_name='شرح مذاکره')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'استعلام قیمت ماده اولیه'
        verbose_name_plural = 'استعلام‌های قیمت مواد اولیه'
        ordering = ['-inquiry_date', '-created_at']

    def __str__(self):
        return f"{self.raw_material.name} - {self.supplier.name} - {self.price}"
