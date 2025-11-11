from django.db import models
from .PersonModel import Person


class PaymentPreference(models.Model):
    """مدل ترجیحات پرداخت"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='payment_preferences',
        verbose_name='شخص'
    )

    class Meta:
        verbose_name = 'شخص | ترجیحات پرداخت'
        verbose_name_plural = 'شخص | ترجیحات پرداخت'
        ordering = ['person']
    

