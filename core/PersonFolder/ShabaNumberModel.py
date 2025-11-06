from django.db import models
from .FinancialBankingModel import FinancialBanking


class ShabaNumber(models.Model):

    financial_banking = models.ForeignKey(
        FinancialBanking,
        on_delete=models.CASCADE,
        related_name='shaba_numbers',
        verbose_name='مالی بانکی'
    )

    class Meta:
        verbose_name = 'شماره شبا'
        verbose_name_plural = 'شماره های شبا'
        ordering = ['shaba_number']


