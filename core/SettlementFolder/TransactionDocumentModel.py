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

    PAYMENT_TYPE_CHOICES = [
        ('market_cash', 'نقدی بازارگاه'),
        ('bank', 'بانکی'),
        ('cheque', 'چک'),
    ]

    DISCREPANCY_TYPE_CHOICES = [
        ('shortage', 'کسری'),
        ('surplus', 'سرک'),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
    ]

    # شناسه یکتا (Primary Key)
    id = models.AutoField(
        primary_key=True,
        verbose_name='شناسه'
    )

    # شماره سند حسابداری
    accounting_document_number = models.CharField(
        max_length=50,
        unique=False,  # ممکن است در مرحله تأیید override شود
        null=True,
        blank=True,
        verbose_name='شماره سند حسابداری',
        help_text='شماره سند حسابداری (به صورت خودکار تولید می‌شود یا در مرحله تأیید وارد می‌شود)'
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

    # نوع تسویه (نحوه پرداخت)
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        verbose_name='نوع تسویه',
        null=True,
        blank=True,
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

    # وضعیت تایید تراکنش
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending',
        verbose_name='وضعیت تایید',
        null=True,
        blank=True
    )

    # ========== فیلدهای تأیید تراکنش (override در مرحله تأیید) ==========
    
    # مبلغ استعلام گرفته شده
    inquiry_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مبلغ استعلام گرفته شده',
        null=True,
        blank=True
    )

    # شماره پیگیری واریز (یونیک به صورت جفتی با ساعت واریز)
    tracking_number = models.CharField(
        max_length=100,
        verbose_name='شماره پیگیری واریز',
        null=True,
        blank=True,
        help_text='شماره پیگیری واریز (در چک، شماره صیادی آن چک است)'
    )

    # بانک مبدا (برای تأیید)
    source_bank = models.CharField(
        max_length=100,
        verbose_name='بانک مبدا',
        null=True,
        blank=True
    )

    # شماره حساب (برای تأیید)
    approval_account_number = models.CharField(
        max_length=50,
        verbose_name='شماره حساب',
        null=True,
        blank=True
    )

    # شماره شبا (برای تأیید)
    shaba_number = models.CharField(
        max_length=26,
        verbose_name='شماره شبا',
        null=True,
        blank=True
    )

    # نام استعلام شده
    inquiry_name = models.CharField(
        max_length=200,
        verbose_name='نام استعلام شده',
        null=True,
        blank=True
    )

    # ساعت واریز (یونیک به صورت جفتی با شماره پیگیری)
    transfer_time = jmodels.jDateTimeField(
        verbose_name='ساعت واریز',
        null=True,
        blank=True
    )

    # نوع اختلاف (کسری یا سرک)
    discrepancy_type = models.CharField(
        max_length=20,
        choices=DISCREPANCY_TYPE_CHOICES,
        verbose_name='نوع تسویه (کسری/سرک)',
        null=True,
        blank=True,
        help_text='نوع تسویه: کسری (مبلغ منفی) یا سرک (مبلغ مثبت)'
    )

    # دلیل رد تراکنش
    REJECTION_REASON_CHOICES = [
        ('name_mismatch', 'عدم تطابق نام'),
        ('amount_mismatch', 'عدم تطابق مبلغ'),
        ('account_mismatch', 'عدم تطابق حساب'),
    ]

    rejection_reason = models.CharField(
        max_length=50,
        choices=REJECTION_REASON_CHOICES,
        verbose_name='دلیل رد',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'تسویه | سند تراکنش'
        verbose_name_plural = 'تسویه | اسناد تراکنش'
        ordering = ['-id', '-accounting_document_number', 'document_number']
        # یونیک بودن جفتی tracking_number و transfer_time (فقط اگر هر دو پر شده باشند)
        constraints = [
            models.UniqueConstraint(
                fields=['tracking_number', 'transfer_time'],
                condition=models.Q(tracking_number__isnull=False) & models.Q(transfer_time__isnull=False),
                name='unique_tracking_transfer'
            )
        ]

    def __str__(self):
        return f"سند تراکنش {self.accounting_document_number or f'#{self.id}'} - {self.document_number or ''}"
    
    def generate_accounting_document_number(self):
        """
        تولید خودکار شماره سند حسابداری
        فرمت: TRX-{settlement_id}-{timestamp}-{random}
        """
        import uuid
        from datetime import datetime
        
        if not self.accounting_document_number:
            settlement_id = self.settlement.id if self.settlement else '000'
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            unique_id = str(uuid.uuid4())[:8].upper()
            self.accounting_document_number = f"TRX-{settlement_id}-{timestamp}-{unique_id}"
        
        return self.accounting_document_number

