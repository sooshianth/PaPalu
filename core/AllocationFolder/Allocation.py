from django.db import models


class Allocation(models.Model):
    """مدل اصلی تخصیص"""
    
    # Status choices
    STATUS_CHOICES = [
        ('planned', 'برنامه‌ریزی شده'),
        ('pending_approval', 'در انتظار تأیید'),
        ('approved', 'تأیید شده'),
        ('in_shipping', 'در حال ارسال'),
        ('delivered', 'تحویل شده'),
        ('canceled', 'لغو شده'),
    ]
    
    # Basic Info fields (directly in main model)
    allocation_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="شماره تخصیص"
    )
    order_number = models.CharField(
        max_length=100,
        verbose_name="شماره سفارش",
        blank=True,
        null=True
    )
    allocation_priority = models.IntegerField(
        verbose_name="الویت تخصیص",
        default=0,
        blank=True,
        null=True
    )
    delivery_postal_code = models.CharField(
        max_length=20,
        verbose_name="کد پستی تحویل",
        blank=True,
        null=True
    )
    allocation_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned',
        verbose_name="وضعیت تخصیص"
    )
    requested_machine = models.CharField(
        max_length=255,
        verbose_name="ماشین درخواستی",
        blank=True,
        null=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی"
    )
    
    class Meta:
        verbose_name = "تخصیص"
        verbose_name_plural = "تخصیص‌ها"
        ordering = ['-allocation_priority', '-created_at']
    
    def __str__(self):
        return f"{self.allocation_number} - {self.get_allocation_status_display()}"
