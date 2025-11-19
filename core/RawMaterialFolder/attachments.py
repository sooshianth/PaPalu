from django.db import models
from . import RawMaterial

class Attachment(models.Model):
    attachment = models.FileField(
        upload_to='raw_material_attachments/',
        verbose_name="فایل پیوست"        
    )

    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments',
        verbose_name="ماده اولیه مرتبط"
    )