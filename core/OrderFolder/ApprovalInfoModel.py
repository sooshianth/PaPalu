from django.db import models
from django_jalali.db import models as jmodels
from .OrderModel import Order


class ApprovalInfo(models.Model):
    # Foreign key to Order
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_infos',
        verbose_name='سفارش'
    )
    
    # زمان ثبت سفارش
    order_registration_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان ثبت سفارش'
    )
    
    # زمان ثبت مدارک پرداخت
    payment_documents_registration_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان ثبت مدارک پرداخت'
    )
    
    # زمان تایید مالی
    financial_approval_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تایید مالی'
    )
    
    # زمان ثبت اطلاعات تخصیص
    allocation_info_registration_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان ثبت اطلاعات تخصیص'
    )
    
    # زمان تأیید تخصیص
    allocation_approval_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تأیید تخصیص'
    )
    
    # زمان تأیید اطلاعات اختلاف
    discrepancy_info_approval_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تأیید اطلاعات اختلاف'
    )
    
    # زمان بسته شدن خرید
    purchase_closure_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان بسته شدن خرید'
    )
    
    # زمان تأیید تسویه اختلاف
    discrepancy_settlement_approval_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان تأیید تسویه اختلاف'
    )
    
    # زمان بایگانی
    archive_time = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='زمان بایگانی'
    )
    
    class Meta:
        verbose_name = 'اطلاعات تأییدیه'
        verbose_name_plural = 'اطلاعات تأییدیه‌ها'
        ordering = ['-order_registration_time']
    
    def __str__(self):
        return f"تأییدیه سفارش {self.order.order_number}"
