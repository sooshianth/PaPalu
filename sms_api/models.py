from django.db import models
from django.utils import timezone
from django_jalali.db import models as jmodels

is_celery_active = False

class SmsQueue(models.Model):
    NOTIFICATION_TYPES = [
        # وضعیت‌های خرید
        ('INITIATED', 'شروع شده'),
        ('SMS_SENT', 'پیامک ارسال شده'),
        ('PAYMENT_VERIFIED', 'ثبت خرید در بازارگاه'),
        ('ALLOCATION_APPROVED', 'ثبت تخصیص در بازارگاه'),
        ('ADDRESS_SENT', 'ارسال آدرس به واردکننده'),
        ('WAITING_FOR_BARNAMEH', 'در انتظار بارنامه'),
        ('BARNAMEH_INCOMPLETE', 'صدور بارنامه (ناقص)'),
        ('BARNAMEH_ISSUED', 'صدور بارنامه'),
        ('PURCHASE_CLOSED', 'بستن خرید در بازارگاه'),
        ('PAY_KASRI', 'پرداخت کسری'),
        ('RECIEIVE_SARAK', 'دریافت سرک'),
        ('FULLY_SETTLED', 'تسویه کامل'),
        ('INVOICE_ISSUED', 'صدور فاکتور'),
        ('CANCELED', 'لغو شده'),
        ('ARCHIVED', 'آرشیو شده'),
        # نوع‌های قدیمی برای سازگاری
        ('new_purchase', 'اطلاع رسانی خرید جدید'),
        ('payment_confirmation', 'تایید پرداخت'),
        ('address_notification', 'اطلاع رسانی آدرس'),
        ('barnameh_notification', 'اطلاع رسانی بارنامه'),
        ('extelaf_notification', 'اطلاع رسانی اختلاف'),
        ('purchase_aware', 'اطلاع رسانی خرید جدید (مدیریت)'),
        ('bulk_campaign', 'کمپین پیامک انبوه'),
        ('custom', 'پیام سفارشی'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار ارسال'),
        ('sent', 'ارسال شده'),
        ('failed', 'ارسال ناموفق'),
        ('suspended', 'معلق'),
    ]

    recipient_number = models.CharField(max_length=11, verbose_name="شماره گیرنده")
    message = models.TextField(max_length=4800, verbose_name="متن پیام")
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='custom', verbose_name="نوع اطلاع رسانی")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    is_suspended = models.BooleanField(default=False, verbose_name="معلق شده")
    retry_count = models.IntegerField(default=0, verbose_name="تعداد تلاش مجدد")
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    scheduled_for = jmodels.jDateTimeField(default=timezone.now, verbose_name="زمان ارسال")
    sent_at = jmodels.jDateTimeField(null=True, blank=True, verbose_name="تاریخ ارسال")

    def __str__(self):
        return f"SMS to {self.recipient_number} - {self.get_status_display()}"


    class Meta:
        verbose_name = "صف پیامک"
        verbose_name_plural = "صف پیامک‌ها"
        ordering = ['scheduled_for', 'created_at']

class SmsLog(models.Model):
    recipient_number = models.CharField(max_length=11, verbose_name="شماره گیرنده")
    message = models.TextField(max_length=4800, verbose_name="متن پیام")
    notification_type = models.CharField(max_length=30, null=True, blank=True, verbose_name="نوع اطلاع رسانی")
    sent_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name="تاریخ ارسال")
    status = models.CharField(max_length=10, default='sent', verbose_name="وضعیت")
    api_response = models.TextField(null=True, blank=True, verbose_name="پاسخ API")
    
    def __str__(self):
        return f"SMS to {self.recipient_number} at {self.sent_at}"

    class Meta:
        verbose_name = "تاریخچه پیامک"
        verbose_name_plural = "تاریخچه پیامک‌ها"
        ordering = ['-sent_at']


class SmsConfig(models.Model):
    """
    مدل تنظیمات پیامک برای کنترل فعال یا غیرفعال بودن ارسال پیامک‌ها توسط ادمین از طریق پنل ادمین.
    """
    sms_enabled = models.BooleanField(
        default=False,
        verbose_name="ارسال پیامک فعال باشد؟",
        help_text="در صورت غیرفعال بودن، هیچ پیامکی ارسال نخواهد شد."
    )
    
    # تنظیم جدید برای نحوه تشخیص موفقیت ارسال
    assume_success_on_no_error = models.BooleanField(
        default=True,
        verbose_name="فرض موفقیت در عدم وجود خطا؟",
        help_text="اگر فعال باشد، در صورتی که API خطا نده، پیامک موفق تلقی می‌شود (مناسب برای پروداکشن)"
    )
    
    # تنظیم جدید برای ارسال پیامک اطلاع‌رسانی خرید جدید
    purchase_aware_enabled = models.BooleanField(
        default=False,
        verbose_name="ارسال پیامک اطلاع‌رسانی خرید جدید فعال باشد؟",
        help_text="در صورت فعال بودن، هنگام ثبت خرید جدید، پیامک اطلاع‌رسانی به شماره‌های تعریف شده در PURCHASE_AWARE_NUMBERS ارسال می‌شود"
    )

    class Meta:
        verbose_name = "تنظیمات پیامک"
        verbose_name_plural = "تنظیمات پیامک"

    def __str__(self):
        return "تنظیمات پیامک"

    def save(self, *args, **kwargs):
        # فقط یک رکورد تنظیمات باید وجود داشته باشد (Singleton)
        if not self.pk and SmsConfig.objects.exists():
            raise ValueError("فقط یک رکورد تنظیمات پیامک می‌تواند وجود داشته باشد.")
        super().save(*args, **kwargs)

    @staticmethod
    def is_sms_enabled():
        """
        بررسی فعال بودن ارسال پیامک از طریق تنظیمات.
        اگر رکوردی وجود نداشت، پیش‌فرض فعال است.
        """
        config = SmsConfig.objects.first()
        if config is not None:
            return config.sms_enabled
        return False
    
    @staticmethod
    def should_assume_success_on_no_error():
        """
        بررسی اینکه آیا باید در عدم وجود خطا، ارسال پیامک موفق تلقی شود.
        """
        config = SmsConfig.objects.first()
        if config is not None:
            return config.assume_success_on_no_error
        return True  # پیش‌فرض: فرض موفقیت
    
    @staticmethod
    def is_purchase_aware_enabled():
        """
        بررسی فعال بودن ارسال پیامک اطلاع‌رسانی خرید جدید.
        اگر رکوردی وجود نداشت، پیش‌فرض غیرفعال است.
        """
        config = SmsConfig.objects.first()
        if config is not None:
            return config.purchase_aware_enabled
        return False  # پیش‌فرض: غیرفعال