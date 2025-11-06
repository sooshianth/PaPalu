from django.db import models
from django_jalali.db import models as jmodels
from .TransportModel import Transport


class LoadingScheduleInfo(models.Model):

    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='loading_schedule_infos',
        verbose_name='حمل',
        null=True,
        blank=True
    )
    
    vehicle_attraction_time = jmodels.jDateTimeField(
        verbose_name='زمان جذب خودرو',
        null=True,
        blank=True
    )
    
    vehicle_entry_time = jmodels.jDateTimeField(
        verbose_name='زمان ورود خودرو',
        null=True,
        blank=True
    )
    
    vehicle_exit_time = jmodels.jDateTimeField(
        verbose_name='زمان خروج خودرو',
        null=True,
        blank=True
    )
    
    unloading_confirmation_time = jmodels.jDateTimeField(
        verbose_name='زمان تأیید تخلیه',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'اطلاعات زمانبندی'
        verbose_name_plural = 'اطلاعات زمانبندی‌ها'
        ordering = ['transport', 'vehicle_entry_time']

    def __str__(self):
        return f"زمانبندی {self.transport.waybill_number or ''}"

