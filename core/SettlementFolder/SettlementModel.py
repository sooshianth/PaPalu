from django.db import models
from core.PersonFolder import Person
from core.TransportFolder import Transport
from core.OrderFolder import Order


class Settlement(models.Model):
    """مدل تسویه"""

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
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='settlements',
        verbose_name='سفارش',
        null=True,
        blank=True
    )

    # شماره بارنامه
    waybill = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='settlements',
        verbose_name='بارنامه',
        null=True,
        blank=True
    )

    # شخص بدهکار
    debtor_person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
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
        verbose_name = 'تسویه | تسویه ها'
        verbose_name_plural = 'تسویه | تسویه ها'
        # 'order_number' فیلدی روی خود Settlement نیست، اگر لازم شد بعداً می‌توانی آن را به
        # 'order__order_number' (در صورت وجود این فیلد روی مدل Order) تغییر دهی.
        # فعلاً برای رفع خطای مایگریشن، فقط بر اساس id مرتب می‌کنیم.
        ordering = ['-id']

    def __str__(self):
        order_number = None
        try:
            # اگر مدل Order فیلدی به نام order_number داشته باشد
            order_number = getattr(self.order, 'order_number', None)
        except Exception:
            order_number = None
        return f"تسویه {self.settlement_type or ''} - سفارش: {order_number or 'بدون شماره'}"
