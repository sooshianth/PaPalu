from django.db import models
from .TransportModel import Transport


class FreightPaymentDocumentAttachment(models.Model):
    """پیوست سند پرداخت کرایه (چند فایل به ازای هر حمل)"""
    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='freight_payment_document_attachments',
        verbose_name='حمل',
    )
    file = models.FileField(
        upload_to='freight_payment_documents/attachments/%Y/%m/%d/',
        verbose_name='فایل سند',
    )

    class Meta:
        verbose_name = 'حمل | پیوست سند پرداخت کرایه'
        verbose_name_plural = 'حمل | پیوست‌های اسناد پرداخت کرایه'
        ordering = ['id']

    def __str__(self):
        return f"سند پرداخت کرایه #{self.id} - {self.transport.transport_number or self.transport_id}"
