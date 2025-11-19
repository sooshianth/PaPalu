from django.db import models
from .TransportModel import Transport


class TransportAttachment(models.Model):
    """مدل پیوست حمل (کارت ملی، روزنامه رسمی و ...)"""
    
    ATTACHMENT_TYPE_CHOICES = [
        ('national_card', 'کارت ملی'),
        ('official_gazette', 'روزنامه رسمی'),
        ('other', 'سایر'),
    ]
    
    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='حمل',
        null=True,
        blank=True
    )
    
    attachment_type = models.CharField(
        max_length=20,
        choices=ATTACHMENT_TYPE_CHOICES,
        verbose_name='نوع پیوست',
        null=True,
        blank=True
    )
    
    file = models.FileField(
        upload_to='transport_attachments/%Y/%m/%d/',
        verbose_name='فایل',
        null=True,
        blank=True
    )
    
    description = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'حمل | پیوست حمل'
        verbose_name_plural = 'حمل | پیوست‌های حمل'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"پیوست {self.get_attachment_type_display()} - {self.transport.waybill_number if self.transport else ''}"

