from django.db import models
from .FinancialBankingModel import FinancialBanking


class BankAccount(models.Model):

    financial_banking = models.ForeignKey(
        FinancialBanking,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name='مالی بانکی'
    )

    class Meta:
        verbose_name = 'شماره حساب بانکی'
        verbose_name_plural = 'شماره حساب‌های بانکی'
        ordering = ['account_number']


