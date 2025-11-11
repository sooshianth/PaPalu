from django.db import models
from .PersonModel import Person


class Attachment(models.Model):
    """مدل پیوست"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='شخص'
    )

    class Meta:
        verbose_name = 'شخص | پیوست'
        verbose_name_plural = 'شخص | پیوست ها'
        ordering = ['person']
    

