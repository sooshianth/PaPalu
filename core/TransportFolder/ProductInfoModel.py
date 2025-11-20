from django.db import models
from .TransportModel import Transport
from core.ProductFolder import Product
from core.RawMaterialFolder import RawMaterial


class ProductInfo(models.Model):
    """مدل اطلاعات محصول"""

    ITEM_TYPE_CHOICES = [
        ('product', 'محصول'),
        ('raw_material', 'مواد اولیه'),
    ]

    PACKAGING_TYPE_CHOICES = [
        ('bag', 'کیسه'),
        ('pallet', 'پالت'),
        ('bulk', 'فله'),
        ('box', 'جعبه'),
        ('barrel', 'بشکه'),
        ('sack', 'گونی'),
        ('other', 'سایر'),
    ]

    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='product_infos',
        verbose_name='حمل',
        null=True,
        blank=True
    )
    
    weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن',
        null=True,
        blank=True
    )
    
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        verbose_name='محصول/مواد اولیه',
        null=True,
        blank=True
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transport_product_infos',
        verbose_name='محصول'
    )
    
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transport_product_infos',
        verbose_name='مواد اولیه'
    )
    
    packaging_type = models.CharField(
        max_length=20,
        choices=PACKAGING_TYPE_CHOICES,
        verbose_name='نوع بسته بندی',
        null=True,
        blank=True
    )
    
    origin_warehouse = models.CharField(
        max_length=100,
        verbose_name='انبار مبدأ',
        null=True,
        blank=True
    )
    
    destination_warehouse = models.CharField(
        max_length=100,
        verbose_name='انبار مقصد',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'حمل | اطلاعات محصول'
        verbose_name_plural = 'حمل | اطلاعات محصولات'
        ordering = ['transport']

    def __str__(self):
        item_name = ''
        if self.item_type == 'product' and self.product:
            item_name = self.product.name
        elif self.item_type == 'raw_material' and self.raw_material:
            item_name = self.raw_material.name
        return f"اطلاعات محصول {self.transport.waybill_number} - {item_name}"

