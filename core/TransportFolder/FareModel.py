from django.db import models
from .TransportModel import Transport


class Fare(models.Model):
    """مدل کرایه"""

    FARE_TYPE_CHOICES = [
        #TODO
    ]

    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='fares',
        verbose_name='حمل',
        null=True,
        blank=True
    )
    
    fare_type = models.CharField(
        max_length=20,
        choices=FARE_TYPE_CHOICES,
        verbose_name='نوع کرایه',
        null=True,
        blank=True
    )
    
    per_transport_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='فی حمل',
        null=True,
        blank=True
    )
    
    initial_fare = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کرایه اولیه',
        null=True,
        blank=True
    )
    
    terminal_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کارمزد پایانه',
        null=True,
        blank=True
    )
    
    company_fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کارمزد شرکت',
        null=True,
        blank=True
    )
    
    other_costs = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='سایر هزینه‌ها',
        null=True,
        blank=True
    )
    
    total_fare = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کرایه کل',
        null=True,
        blank=True
    )
    
    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='تخفیف',
        null=True,
        blank=True
    )
    
    excess = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مازاد',
        null=True,
        blank=True
    )
    
    paid_fare = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کرایه پرداختی',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'حمل | کرایه'
        verbose_name_plural = 'حمل | کرایه‌ها'
        ordering = ['transport']

    def __str__(self):
        return f"کرایه {self.transport.waybill_number or ''} - {self.total_fare or 0}"

