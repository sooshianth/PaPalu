from django.db import models
from .PersonModel import Person


class PurchasePreference(models.Model):
    """مدل ترجیحات خرید"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='purchase_preferences',
        verbose_name='شخص'
    )

    class Meta:
        verbose_name = 'شخص | ترجیحات خرید'
        verbose_name_plural = 'شخص | ترجیحات خرید'
        ordering = ['person']
    

