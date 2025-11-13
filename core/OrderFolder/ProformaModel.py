from pyexpat import model
from django.db import models
from .OrderModel import Order
from django_jalali.db import models as jmodels
from core.PersonFolder.PersonModel import Person

class Proforma(models.Model):
    
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE, 
        related_name='proformas',
        verbose_name='سفارش',
        null=True,
        blank=True,
    )
    
    proforma_number = models.CharField(
        max_length=255,
        verbose_name='شماره سریال',
        null=True,
        blank=True,
    )
    
    validity_date = jmodels.jDateField(
        verbose_name='تاریخ  اعتبار سریال',
        null=True,
        blank=True,
    )

    customer = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='proformas',
        verbose_name='مشتری',
        null=True,
        blank=True,
    )

    company = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='proformas',
        verbose_name='شرکت',
        null=True,
        blank=True,
    )

    created_at = jmodels.jDateTimeField(
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True,
        auto_now_add=True,
    )

    updated_at = jmodels.jDateTimeField(
        verbose_name='تاریخ بروزرسانی',
        null=True,
        blank=True,
        auto_now=True,
    )

    description = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'پیش فاکتور'
        verbose_name_plural = 'پیش فاکتورها'
        ordering = ['-created_at']

    def __str__(self):
        return f"پیش فاکتور {self.proforma_number}"