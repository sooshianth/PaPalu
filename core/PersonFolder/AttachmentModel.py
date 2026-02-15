from django.db import models
from .PersonModel import Person
from core.file_upload_utils import safe_media_upload_to


class Attachment(models.Model):
    """مدل پیوست"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='شخص'
    )

    DOC_TYPE_CHOICES = [
        ('contract', 'قرارداد'),
        ('license', 'مجوز'),
        ('certificate', 'گواهی'),
        ('other', 'سایر'),
    ]

    doc_type = models.CharField(
        max_length=20,
        choices=DOC_TYPE_CHOICES,
        verbose_name='نوع مدرک',
        null=True,
        blank=True,
    )

    file = models.FileField(
        upload_to=safe_media_upload_to('person_attachments', date_include_day=True),
        verbose_name='فایل پیوست',
        null=True,
        blank=True,
    )

    description = models.CharField(
        max_length=255,
        verbose_name='توضیح پیوست',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'شخص | پیوست'
        verbose_name_plural = 'شخص | پیوست ها'
        ordering = ['person']
    

