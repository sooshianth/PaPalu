from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class PhoneNumber(models.Model):
    """مدل شماره تلفن"""

    PHONE_TYPE_CHOICES = [
        ('landline', 'شماره ثابت'),
        ('mobile', 'شماره همراه'),
    ]

    # برای اتصال به مدل های مختلف جنریک شد
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name='نوع'
    )
    object_id = models.PositiveIntegerField(verbose_name='شناسه')
    content_object = GenericForeignKey('content_type', 'object_id')

    phone_type = models.CharField(
        max_length=10,
        choices=PHONE_TYPE_CHOICES,
        verbose_name='نوع شماره'
    )
    number = models.CharField(max_length=20, verbose_name='شماره تلفن')
    is_primary = models.BooleanField(default=False, verbose_name='شماره اصلی')

    class Meta:
        verbose_name = 'شماره تلفن'
        verbose_name_plural = 'شماره های تلفن'
        ordering = ['-is_primary', 'phone_type']


