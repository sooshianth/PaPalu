from django.db import models
from .FinancialBankingModel import FinancialBanking


class BankAccount(models.Model):
    """مدل حساب بانکی"""

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
        verbose_name = 'شخص | حساب بانکی'
        verbose_name_plural = 'شخص | حساب بانکی'
        ordering = ['account_number']

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


