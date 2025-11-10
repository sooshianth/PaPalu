from django.db import models
from django_jalali.db import models as jmodels
from .SettlementModel import Settlement
from core.PersonFolder import BankAccount


class TransactionDocument(models.Model):
    """مدل سند تراکنش"""

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار وصول'),
        ('received', 'وصول شده'),
        ('overdue', 'سررسید گذشته'),
        ('cancelled', 'لغو شده'),
    ]

    # شماره سند حسابداری به عنوان Primary Key
    accounting_document_number = models.CharField(
        max_length=50,
        primary_key=True,
        verbose_name='شماره سند حسابداری'
    )

    # ForeignKey به Settlement
    settlement = models.ForeignKey(
        Settlement,
        on_delete=models.CASCADE,
        related_name='transaction_documents',
        verbose_name='تسویه',
        null=True,
        blank=True
    )

    # شماره سند
    document_number = models.CharField(
        max_length=50,
        verbose_name='شماره سند',
        null=True,
        blank=True
    )

    # مبلغ سند
    document_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مبلغ سند',
        null=True,
        blank=True
    )

    # تاریخ سر رسید
    due_date = jmodels.jDateField(
        verbose_name='تاریخ سر رسید',
        null=True,
        blank=True
    )

    # تاریخ وصول چک
    check_receipt_date = jmodels.jDateField(
        verbose_name='تاریخ وصول چک',
        null=True,
        blank=True
    )

    # حساب مبدا
    source_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='source_accounts',
        verbose_name='حساب مبدا',
        null=True,
        blank=True
    )

    # حساب مقصد
    destination_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='destination_accounts',
        verbose_name='حساب مقصد',
        null=True,
        blank=True
    )

    # پیوست سند
    document_attachment = models.FileField(
        upload_to='transaction_documents/%Y/%m/%d/',
        verbose_name='پیوست سند',
        null=True,
        blank=True
    )

    # وضعیت وصول
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        verbose_name='وضعیت وصول',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'سند تراکنش'
        verbose_name_plural = 'اسناد تراکنش'
        ordering = ['-accounting_document_number', 'document_number']

    def __str__(self):
        return f"سند تراکنش {self.accounting_document_number or 'بدون شماره'} - {self.document_number or ''}"

