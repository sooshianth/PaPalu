from django.db import models
from .PersonModel import Person


class DeliveryAddress(models.Model):
    """مدل آدرس تحویل"""

    RECIPIENT_TYPE_CHOICES = [
        ('person', 'شخص'),
        ('company', 'شرکت'),
        ('warehouse', 'انبار'),
        ('other', 'سایر'),
    ]

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='delivery_addresses',
        verbose_name='شخص'
    )
    postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی تحویل',
        primary_key=True
    )
    recipient_name = models.CharField(
        max_length=100,
        verbose_name='نام تحویل گیرنده شخص'
    )
    recipient_national_id = models.CharField(
        max_length=10,
        verbose_name='کد ملی تحویل گیرنده',
        null=True,
        blank=True
    )
    unique_delivery_id = models.CharField(
        max_length=50,
        verbose_name='شناسه یکتا تحویل',
        null=True,
        blank=True
    )
    province = models.CharField(
        max_length=50,
        verbose_name='استان تحویل'
    )
    city = models.CharField(
        max_length=50,
        verbose_name='شهر تحویل'
    )
    address = models.TextField(
        verbose_name='آدرس پستی تحویل'
    )
    delivery_limit = models.CharField(
        max_length=200,
        verbose_name='محدودیت تحویل',
        null=True,
        blank=True
    )
    recipient_type = models.CharField(
        max_length=20,
        choices=RECIPIENT_TYPE_CHOICES,
        verbose_name='نوع تحویل گیرنده',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'شخص | آدرس تحویل'
        verbose_name_plural = 'شخص | آدرس های تحویل'
        ordering = ['person', 'province', 'city']

    def __str__(self):
        return f"{self.recipient_name} - {self.city}, {self.province}"

