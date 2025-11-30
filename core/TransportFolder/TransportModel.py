from django.db import models
from django_jalali.db import models as jmodels
from core.PersonFolder import Person, DeliveryAddress
from core.AllocationFolder.AllocationModel import Allocation


class Transport(models.Model):
    """مدل حمل"""

    DIRECTION_CHOICES = [
        ('inbound', 'ورودی'),
        ('outbound', 'خروجی'),
    ]
    
    STATUS_CHOICES = [
        ('pending_vehicle_entry', 'در انتظار ورود خودرو به کارخانه'),
        ('vehicle_entered', 'خودرو وارد شده'),
        ('loading', 'در انتظار بارگیری'),
        ('loaded', 'بارگیری شده'),
        ('pending_waybill', 'در انتظار بارنامه'),
        ('pending_exit', 'در انتظار خروج'),
        ('in_transit', 'در حال حمل'),
        ('delivered', 'تحویل شده'),
        ('completed', 'تکمیل شده'),
    ]
    
    VEHICLE_TYPE_OFFICIAL_CHOICES = [
        ('official', 'رسمی'),
        ('unofficial', 'غیررسمی'),
    ]

    # شماره بارنامه به عنوان Primary Key
    waybill_number = models.CharField(
        max_length=50,
        primary_key=True,
        verbose_name='شماره بارنامه'
    )
    
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='transports',
        verbose_name='تخصیص',
        null=True,
        blank=True
    )
    
    driver = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transports',
        verbose_name='شخص راننده'
    )
    
    delivery_postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی تحویل',
        null=True,
        blank=True
    )
    
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        verbose_name='ورودی/خروجی',
        null=True,
        blank=True
    )
    
    loading_date = jmodels.jDateField(
        verbose_name='تاریخ بارگیری',
        null=True,
        blank=True
    )
    
    unloading_date = jmodels.jDateField(
        verbose_name='تاریخ تخلیه',
        null=True,
        blank=True
    )
    
    transport_company = models.CharField(
        max_length=100,
        verbose_name='شرکت حمل و نقل',
        null=True,
        blank=True
    )

    waybill_date = jmodels.jDateField(
        verbose_name='تاریخ بارنامه',
        null=True,
        blank=True
    )
    
    waybill_serial = models.CharField(
        max_length=50,
        verbose_name='سریال بارنامه',
        null=True,
        blank=True
    )
    
    consignment_number = models.CharField(
        max_length=50,
        verbose_name='شماره حواله',
        null=True,
        blank=True
    )
    
    contract_code = models.CharField(
        max_length=50,
        verbose_name='کد قرارداد',
        null=True,
        blank=True
    )
    
    cardex_code = models.CharField(
        max_length=50,
        verbose_name='کد کاردکس',
        null=True,
        blank=True
    )
    
    origin = models.CharField(
        max_length=100,
        verbose_name='مبدأ',
        null=True,
        blank=True
    )
    
    destination = models.CharField(
        max_length=100,
        verbose_name='مقصد',
        null=True,
        blank=True
    )
    
    # فیلدهای جدید برای جذب خودرو
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending_vehicle_entry',
        verbose_name='وضعیت حمل',
        null=True,
        blank=True
    )
    
    carrier_recruitment = models.CharField(
        max_length=100,
        verbose_name='باربری جذب',
        null=True,
        blank=True
    )
    
    vehicle_type_official = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_OFFICIAL_CHOICES,
        verbose_name='نوع ماشین (رسمی/غیررسمی)',
        null=True,
        blank=True
    )

    # فیلدهای وزن حمل
    gross_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن پر',
        null=True,
        blank=True
    )
    
    empty_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالی',
        null=True,
        blank=True
    )
    
    net_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالص',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'حمل | حمل ها'
        verbose_name_plural = 'حمل | حمل ها'
        ordering = ['-waybill_date', 'waybill_number']

    def __str__(self):
        return self.waybill_number or str(self.pk)

