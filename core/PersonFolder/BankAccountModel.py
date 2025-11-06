from django.db import models
from .FinancialBankingModel import FinancialBanking


class BankAccount(models.Model):

    financial_banking = models.ForeignKey(
        FinancialBanking,
        on_delete=models.CASCADE,
        related_name='bank_accounts',
        verbose_name='مالی بانکی'
    )

    account_number = models.CharField(
        max_length=50,
        verbose_name='شماره حساب بانکی',
        null=True,
        blank=True,
    )

    shaba_number = models.CharField(
        max_length=50,
        verbose_name='شماره شبا',
        null=True,
        blank=True,
    )

    bank_name = models.CharField(
        max_length=50,
        verbose_name='نام بانک',
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'شماره حساب بانکی'
        verbose_name_plural = 'شماره حساب‌های بانکی'
        ordering = ['account_number']


