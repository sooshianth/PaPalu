from django.db import models
from django_jalali.db import models as jmodels
from .OrderModel import Order
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.file_upload_utils import safe_media_upload_to_flat


class Invoice(models.Model):
    """مدل فاکتور"""
    
    TAX_TYPE_CHOICES = [
        ('type1', 'نوع 1'),
        ('type2', 'نوع 2'),
        ('type3', 'نوع 3'),
    ]
    
    # سفارش مرتبط
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name='سفارش',
        null=True,
        blank=True,
    )
    
    # شماره صورتحساب مالیاتی
    tax_invoice_number = models.CharField(
        max_length=255,
        verbose_name='شماره صورتحساب مالیاتی',
        null=True,
        blank=True,
    )
    
    # نوع مالیاتی مشتری
    customer_tax_type = models.CharField(
        max_length=20,
        choices=TAX_TYPE_CHOICES,
        verbose_name='نوع مالیاتی مشتری',
        null=True,
        blank=True,
    )
    
    # تاریخ صدور فاکتور
    issue_date = jmodels.jDateField(
        verbose_name='تاریخ صدور فاکتور',
        null=True,
        blank=True,
    )
    
    # فایل فاکتور (اختیاری)
    invoice_file = models.FileField(
        upload_to=safe_media_upload_to_flat('invoices'),
        verbose_name='فایل فاکتور',
        null=True,
        blank=True,
    )
    
    # مشتری (از سفارش)
    customer = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='customer_invoices',
        verbose_name='مشتری',
        null=True,
        blank=True,
    )
    
    # شرکت (تامین نهاده سیمرغ)
    company = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name='company_invoices',
        verbose_name='شرکت',
        null=True,
        blank=True,
    )
    
    # Timestamps
    created_at = jmodels.jDateTimeField(
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True,
        auto_now_add=True,
    )
    
    updated_at = jmodels.jDateTimeField(
        verbose_name='تاریخ بروزرسانی',
        null=True,
        blank=True,
        auto_now=True,
    )
    
    description = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True,
    )
    
    class Meta:
        verbose_name = 'سفارش | فاکتور'
        verbose_name_plural = 'سفارش | فاکتورها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"فاکتور {self.tax_invoice_number or self.id}"
    
    def get_customer_economic_code(self):
        """دریافت شماره اقتصادی مشتری"""
        if not self.customer:
            return None
        
        financial_info = FinancialBanking.objects.filter(person=self.customer).first()
        if financial_info:
            return financial_info.economic_code
        return None
    
    def is_settlement_completed(self):
        """بررسی اینکه آیا تسویه کار شده است یا نه"""
        if not self.order:
            return False
        
        # اگر وضعیت سفارش بعد از pending_settlement_approval باشد، یعنی تسویه کامل شده
        return self.order.status in ['pending_settlement_approval', 'archived']

