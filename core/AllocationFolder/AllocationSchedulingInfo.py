from django.db import models
from django_jalali.db import models as jmodels
from .Allocation import Allocation


class AllocationSchedulingInfo(models.Model):
    """مدل اطلاعات زمانبندی و برنامه اجرا"""
    
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='scheduling_infos',
        verbose_name="تخصیص",
        null=True,
        blank=True
    )
    allocation_received_time = jmodels.jDateTimeField(
        verbose_name="زمان دریافت تخصیص",
        blank=True,
        null=True
    )
    production_start_time = jmodels.jDateTimeField(
        verbose_name="زمان شروع تولید",
        blank=True,
        null=True
    )
    warehouse_availability_announcement_time = jmodels.jDateTimeField(
        verbose_name="زمان اعلام موجودیت در انبار",
        blank=True,
        null=True
    )
    shipping_announcement_time = jmodels.jDateTimeField(
        verbose_name="زمان اعلام بار به باربری",
        blank=True,
        null=True
    )
    total_allocation_delivery_time = jmodels.jDateTimeField(
        verbose_name="زمان تحویل کل تخصیص",
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = "اطلاعات زمانبندی و برنامه اجرا"
        verbose_name_plural = "اطلاعات زمانبندی و برنامه اجرا"
    
    def __str__(self):
        if self.allocation_received_time:
            return f"زمانبندی - {self.allocation_received_time.strftime('%Y-%m-%d %H:%M')}"
        return "اطلاعات زمانبندی"
