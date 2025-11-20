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

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'نقدی'),
        ('bank_transfer', 'واریز بانکی'),
        ('card', 'کارت به کارت'),
        ('credit', 'اعتباری'),
    ]

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name='روش پرداخت',
        null=True,
        blank=True,
    )

    payment_term_days = models.PositiveIntegerField(
        verbose_name='شرایط پرداخت (روز)',
        null=True,
        blank=True,
    )

    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='سقف اعتبار',
        null=True,
        blank=True,
    )

    notes = models.TextField(
        verbose_name='توضیحات پرداخت',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'شخص | ترجیحات پرداخت'
        verbose_name_plural = 'شخص | ترجیحات پرداخت'
        ordering = ['person']
    

