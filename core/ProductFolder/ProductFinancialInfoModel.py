from django.db import models
from django_jalali.db import models as jmodels
from .ProductModel import Product

class ProductFinancialInfo(models.Model):
    """
    مدل اطلاعات مالی محصول - قیمت و شرایط فروش
    """
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='financial_info',
        verbose_name='محصول'
    )
    
    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='قیمت'
    )
    
    deadline = jmodels.jDateTimeField(
        verbose_name='مهلت اعتبار قیمت',
        null=False,
        blank=False
    )
    
    condition = models.TextField(
        verbose_name='شرط',
        null=False,
        blank=False
    )
    
    loading_date = models.CharField(
        max_length=255,
        verbose_name='مدت زمان بارگیری',
        null=True,
        blank=True
    )
    
    condition_description = models.TextField(
        verbose_name='توضیحات شرایط',
        null=False,
        blank=False
    )
    
    description = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True
    )
    
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ آخرین ویرایش'
    )
    
    class Meta:
        verbose_name = 'محصول | اطلاعات مالی محصول'
        verbose_name_plural = 'محصول | اطلاعات مالی محصولات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.code} - قیمت: {self.price}"