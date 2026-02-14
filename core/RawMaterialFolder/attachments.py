from django.db import models
from . import RawMaterial
from core.file_upload_utils import safe_media_upload_to_flat


class RawMaterialAttachment(models.Model):
    attachment = models.FileField(
        upload_to=safe_media_upload_to_flat('raw_material_attachments'),
        verbose_name="فایل پیوست"        
    )

    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='raw_material_attachments',
        verbose_name="ماده اولیه مرتبط"
    )

    class Meta:
        verbose_name = 'ماده اولیه | پیوست'
        verbose_name_plural = 'ماده اولیه | پیوست‌ها'