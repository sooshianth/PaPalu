from django.db import models
from .PersonModel import Person


class SocialNetwork(models.Model):
    """مدل شبکه اجتماعی"""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='social_networks',
        verbose_name='شخص'
    )

    PLATFORM_CHOICES = [
        ('instagram', 'اینستاگرام'),
        ('linkedin', 'لینکدین'),
        ('telegram', 'تلگرام'),
        ('whatsapp', 'واتس‌اپ'),
        ('website', 'وب‌سایت'),
        ('other', 'سایر'),
    ]

    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        verbose_name='پلتفرم',
        null=True,
        blank=True,
    )

    handle = models.CharField(
        max_length=100,
        verbose_name='نام کاربری/شناسه',
        null=True,
        blank=True,
    )

    url = models.URLField(
        verbose_name='آدرس پروفایل/وب‌سایت',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'شخص | شبکه اجتماعی'
        verbose_name_plural = 'شخص | شبکه های اجتماعی'
        ordering = ['person']
    

