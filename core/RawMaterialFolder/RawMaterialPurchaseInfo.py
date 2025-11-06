from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .Supplier import Supplier
from .RawMaterial import RawMaterial


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
    suppliers = models.ManyToManyField(
        Supplier,
        related_name='purchase_infos',
        verbose_name="تامین‌کنندگان",
        blank=True
    )
    minimum_order_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حداقل مقدار سفارش",
        null=True,
        blank=True
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
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
    default_warehouse = models.TextField(
        verbose_name="انبار پیش‌فرض نگهداری",
        null=True,
        blank=True
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
    notes = models.TextField(
        verbose_name="توضیحات",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "اطلاعات خرید"
        verbose_name_plural = "اطلاعات خرید"

    def __str__(self):
        supplier_names = ", ".join([s.name for s in self.suppliers.all()[:3]])
        if self.suppliers.count() > 3:
            supplier_names += "..."
        return f"اطلاعات خرید - {supplier_names or 'بدون تامین‌کننده'}"
