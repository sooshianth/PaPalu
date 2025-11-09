from django.db import models
from .PersonModel import Person


class FinancialBanking(models.Model):
    """مدل مالی بانکی"""

    TAX_GROUP_CHOICES = [
        ('type1', 'نوع 1'),
        ('type2', 'نوع 2'),
        ('type3', 'نوع 3'),
    ]

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='financial_banking',
        verbose_name='شخص'
    )
    tax_group = models.CharField(
        max_length=10,
        choices=TAX_GROUP_CHOICES,
        verbose_name='گروه مالیاتی شخص',
        null=True,
        blank=True
    )
    account_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مانده حساب شخص',
        null=True,
        blank=True
    )
    economic_code = models.CharField(
        max_length=50,
        verbose_name='کد اقتصادی شخص',
        null=True,
        blank=True
    )
    tax_postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی مالیاتی شخص',
        null=True,
        blank=True
    )
    tax_province = models.CharField(
        max_length=50,
        verbose_name='استان مالیاتی شخص',
        null=True,
        blank=True
    )
    tax_city = models.CharField(
        max_length=50,
        verbose_name='شهر مالیاتی شخص',
        null=True,
        blank=True
    )
    tax_address = models.TextField(
        verbose_name='آدرس پستی مالیاتی شخص',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'مالی بانکی'
        verbose_name_plural = 'مالی بانکی'
        ordering = ['person']

    def __str__(self):
        return f"مالی بانکی {self.person.name if self.person.name else self.person.national_id}"

