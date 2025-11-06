from django.db import models
from .PersonModel import Person


class PaymentPreference(models.Model):

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='payment_preferences',
        verbose_name='شخص'
    )

    class Meta:
        verbose_name = 'ترجیحات پرداخت'
        verbose_name_plural = 'ترجیحات پرداخت'
        ordering = ['person']
    

