from django.db import models
from .TransportModel import Transport


class TruckInfo(models.Model):

    VEHICLE_TYPE_CHOICES = [
        ('truck', 'کامیون'),
        ('trailer', 'تریلی'),
        ('van', 'ون'),
        ('pickup', 'وانت'),
        ('other', 'سایر'),
    ]

    LOADING_TYPE_CHOICES = [
        ('open', 'باز'),
        ('closed', 'بسته'),
        ('refrigerated', 'یخچال دار'),
        ('tank', 'تانکر'),
        ('flatbed', 'کفی'),
        ('other', 'سایر'),
    ]

    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='truck_infos',
        verbose_name='حمل',
        null=True,
        blank=True
    )
    
    plate_number = models.CharField(
        max_length=20,
        verbose_name='پلاک',
        null=True,
        blank=True
    )
    
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        verbose_name='نوع ماشین',
        null=True,
        blank=True
    )
    
    is_smart_truck = models.BooleanField(
        default=False,
        verbose_name='هوشمند کامیون',
        null=True,
        blank=True
    )
    
    manufacturer = models.CharField(
        max_length=100,
        verbose_name='کارخانه کامیون',
        null=True,
        blank=True
    )
    
    loading_type = models.CharField(
        max_length=20,
        choices=LOADING_TYPE_CHOICES,
        verbose_name='نوع بارگیر',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'اطلاعات کامیون'
        verbose_name_plural = 'اطلاعات کامیون‌ها'
        ordering = ['transport', 'plate_number']

    def __str__(self):
        return f"اطلاعات کامیون {self.plate_number or 'بدون پلاک'} - {self.transport.waybill_number or ''}"

