from django.db import models
from .PersonModel import Person
from core.file_upload_utils import safe_media_upload_to


class Representative(models.Model):
    """مدل نماینده"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='representatives',
        verbose_name='شخص'
    )
    name = models.CharField(max_length=100, verbose_name='نام نماینده', null=True, blank=True)
    position = models.CharField(max_length=100, verbose_name='سمت نماینده', null=True, blank=True)
    mobile_number = models.CharField(max_length=20, verbose_name='شماره موبایل نماینده', null=True, blank=True)
    phone_number = models.CharField(max_length=20, verbose_name='شماره ثابت نماینده', null=True, blank=True)
    confirmation_letter = models.FileField(
        upload_to=safe_media_upload_to('representative_letters', date_include_day=True),
        verbose_name='نامه تایید نماینده',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'شخص | نماینده'
        verbose_name_plural = 'شخص | نمایندگان'
        ordering = ['person', 'name']

    def __str__(self):
        return f"{self.name} - {self.position}"

