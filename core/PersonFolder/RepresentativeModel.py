from django.db import models
from .PersonModel import Person


class Representative(models.Model):
    """مدل نماینده"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='representatives',
        verbose_name='شخص'
    )
    name = models.CharField(max_length=100, verbose_name='نام نماینده', primary_key=True)
    position = models.CharField(max_length=100, verbose_name='سمت نماینده')
    confirmation_letter = models.FileField(
        upload_to='representative_letters/%Y/%m/%d/',
        verbose_name='نامه تایید نماینده',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'نماینده'
        verbose_name_plural = 'نمایندگان'
        ordering = ['person', 'name']

    def __str__(self):
        return f"{self.name} - {self.position}"

