from django.db import models
from django_jalali.db import models as jmodels
from .OrderModel import Order
from core.file_upload_utils import safe_media_upload_to_flat


class OrderDocument(models.Model):
    """مدل اسناد سفارش"""

    # Foreign key to Order
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='order_documents',
        verbose_name='سفارش'
    )
    
    # پیوست پیش فاکتور
    proforma_attachment = models.FileField(
        upload_to=safe_media_upload_to_flat('order_documents/proforma'),
        null=True,
        blank=True,
        verbose_name='پیوست پیش فاکتور'
    )
    
    # پیوست تاییدیه پیش فاکتور
    proforma_confirmation_attachment = models.FileField(
        upload_to=safe_media_upload_to_flat('order_documents/proforma_confirmation'),
        null=True,
        blank=True,
        verbose_name='پیوست تاییدیه پیش فاکتور'
    )
    
    class Meta:
        verbose_name = 'سفارش | اسناد'
        verbose_name_plural = 'سفارش | اسناد'
    
    def __str__(self):
        return f"اسناد سفارش {self.order.order_number}"
