from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .SupplierModel import Supplier
from .RawMaterialModel import RawMaterial
from ..WarehouseFolder.WarehouseModel import Warehouse


class RawMaterialPurchaseInfo(models.Model):
    """اطلاعات خرید - Purchase Information"""
    
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        related_name='purchase_infos',
        verbose_name="ماده اولیه",
        null=True,
        blank=True
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        related_name='purchase_infos',
        verbose_name="تامین‌کنندگان",
        blank=True,
        null=True
    )
    minimum_order_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حداقل مقدار سفارش",
        null=True,
        blank=True
    )
    vat_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        verbose_name="درصد مالیات بر ارزش افزوده",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    accounting_code = models.CharField(
        max_length=100,
        verbose_name="کد حسابداری مرتبط",
        null=True,
        blank=True
    )
    tax_code = models.CharField(
        max_length=100,
        verbose_name="کد مالیاتی ماده",
        null=True,
        blank=True
    )
    safety_stock_level = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حد موجودی اطمینان",
        null=True,
        blank=True
    )
    reorder_point = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="نقطه سفارش مجدد",
        null=True,
        blank=True
    )
    default_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_for_rawmaterial_purchase',
        verbose_name="انبار پیش‌فرض نگهداری"
    )
    transportation_conditions = models.TextField(
        verbose_name="شرایط حمل",
        null=True,
        blank=True
    )
    storage_conditions = models.TextField(
        verbose_name="شرایط نگهداری",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "مواد اولیه | اطلاعات خرید"
        verbose_name_plural = "مواد اولیه | اطلاعات خرید"

    def __str__(self):
        if self.raw_material:
            name = getattr(self.raw_material, 'name', None)
            if not name:
                name = str(self.raw_material)
            return f"اطلاعات خرید - {name}"
        return "اطلاعات خرید - بدون ماده اولیه"
