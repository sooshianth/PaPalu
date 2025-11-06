from django.db import models
from core.PersonFolder import Person
from core.TransportFolder import Transport


class Settlement(models.Model):

    SETTLEMENT_TYPE_CHOICES = [
        ('purchase', 'خرید'),
        ('sale', 'فروش'),
        ('rent', 'کرایه'),
    ]

    SETTLEMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('partial', 'جزئی'),
        ('completed', 'تکمیل شده'),
        ('cancelled', 'لغو شده'),
    ]

    # نوع تسویه
    settlement_type = models.CharField(
        max_length=20,
        choices=SETTLEMENT_TYPE_CHOICES,
        verbose_name='نوع تسویه',
        null=True,
        blank=True
    )

    # شماره سفارش
    order_number = models.CharField(
        max_length=50,
        verbose_name='شماره سفارش',
        null=True,
        blank=True
    )

    # شماره بارنامه
    waybill_number = models.CharField(
        max_length=50,
        verbose_name='شماره بارنامه',
        null=True,
        blank=True
    )

    # شخص بدهکار
    debtor_person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        related_name='debtor_settlements',
        verbose_name='شخص بدهکار',
        null=True,
        blank=True
    )

    # شخص بستانکار
    creditor_person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        related_name='creditor_settlements',
        verbose_name='شخص بستانکار',
        null=True,
        blank=True
    )

    # مبلغ کل سند مبدا
    original_document_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مبلغ کل سند مبدا',
        null=True,
        blank=True
    )

    # مبلغ تسویه شده
    settled_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مبلغ تسویه شده',
        null=True,
        blank=True
    )

    # وضعیت تسویه
    settlement_status = models.CharField(
        max_length=20,
        choices=SETTLEMENT_STATUS_CHOICES,
        verbose_name='وضعیت تسویه',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'تسویه'
        verbose_name_plural = 'تسویه‌ها'
        ordering = ['-id', 'order_number']

    def __str__(self):
        return f"تسویه {self.settlement_type or ''} - سفارش: {self.order_number or 'بدون شماره'}"
