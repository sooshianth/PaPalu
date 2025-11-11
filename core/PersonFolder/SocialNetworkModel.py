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

    class Meta:
        verbose_name = 'شخص | شبکه اجتماعی'
        verbose_name_plural = 'شخص | شبکه های اجتماعی'
        ordering = ['person']
    

