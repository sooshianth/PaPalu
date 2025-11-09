from django.db import models
from django_jalali.db import models as jmodels
from ..OrderFolder.OrderModel import Order


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
        primary_key=True,
        verbose_name="شماره تخصیص",
        null=True,
        blank=True
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        related_name='allocations',
        verbose_name="سفارش",
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
        verbose_name="وضعیت تخصیص",
        null=True,
        blank=True
    )
    requested_machine = models.CharField(
        max_length=255,
        verbose_name="ماشین درخواستی",
        blank=True,
        null=True
    )
    
    # Timestamps
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی"
    )
    
    class Meta:
        verbose_name = "تخصیص"
        verbose_name_plural = "تخصیص‌ها"
        ordering = ['-allocation_priority', '-created_at']
    
    def __str__(self):
        allocation_num = self.allocation_number or "نامشخص"
        status_display = self.get_allocation_status_display() if self.allocation_status else "نامشخص"
        return f"{allocation_num} - {status_display}"
