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
        verbose_name = 'پیوست'
        verbose_name_plural = 'پیوست ها'
        ordering = ['person']
    

