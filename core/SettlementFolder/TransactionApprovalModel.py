from django.db import models
from django.core.exceptions import ValidationError
from django_jalali.db import models as jmodels
from .SettlementModel import Settlement
from core.OrderFolder.OrderModel import Order


class TransactionApproval(models.Model):
    """مدل تأیید تراکنش فروش"""

    # ForeignKey به Settlement (می‌تواند چندین تأیید برای یک Settlement وجود داشته باشد)
    settlement = models.ForeignKey(
        Settlement,
        on_delete=models.CASCADE,
        related_name='transaction_approvals',
        verbose_name='تسویه',
        null=False,
        blank=False
    )

    # شماره سند حسابداری
    accounting_document_number = models.CharField(
        max_length=100,
        verbose_name='شماره سند حسابداری',
        null=False,
        blank=False
    )

    # مبلغ استعلام گرفته شده
    inquiry_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مبلغ استعلام گرفته شده',
        null=False,
        blank=False
    )

    # شماره پیگیری واریز (یونیک به صورت جفتی با ساعت واریز)
    tracking_number = models.CharField(
        max_length=100,
        verbose_name='شماره پیگیری واریز',
        null=False,
        blank=False,
        help_text='شماره پیگیری واریز (در چک، شماره صیادی آن چک است)'
    )

    # بانک مبدا
    source_bank = models.CharField(
        max_length=100,
        verbose_name='بانک مبدا',
        null=False,
        blank=False
    )

    # شماره حساب
    account_number = models.CharField(
        max_length=100,
        verbose_name='شماره حساب',
        null=False,
        blank=False
    )

    # شماره شبا
    shaba_number = models.CharField(
        max_length=26,
        verbose_name='شماره شبا',
        null=False,
        blank=False
    )

    # نام استعلام شده
    inquiry_name = models.CharField(
        max_length=200,
        verbose_name='نام استعلام شده',
        null=False,
        blank=False
    )

    # ساعت واریز (یونیک به صورت جفتی با شماره پیگیری)
    transfer_time = jmodels.jDateTimeField(
        verbose_name='ساعت واریز',
        null=False,
        blank=False
    )

    # Timestamps
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی'
    )

    class Meta:
        verbose_name = 'تسویه | تأیید تراکنش'
        verbose_name_plural = 'تسویه | تأییدهای تراکنش'
        ordering = ['-created_at']
        # یونیک بودن جفتی tracking_number و transfer_time
        unique_together = [['tracking_number', 'transfer_time']]

    def __str__(self):
        return f"تأیید تراکنش - {self.settlement.order.order_number if self.settlement and self.settlement.order else 'بدون سفارش'} - {self.tracking_number}"


