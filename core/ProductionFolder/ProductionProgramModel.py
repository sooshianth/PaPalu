from django.db import models
from django.utils import timezone
from django_jalali.db import models as jmodels
from decimal import Decimal

from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.ProductModel import Product


class ProductionProgram(models.Model):
    """برنامه تولید

    گردش وضعیت:
      Draft -> Confirmed -> In Progress -> Completed

    فیلدهای کلیدی (مطابق تسک):
      formula_id (شناسه فرمول), product, planned_weight_ton (تناژ برنامه ریزی شده),
      predicted_start_time (ساعت شروع پیشبینی شده), predicted_end_time (ساعت پایان پیشبینی شده),
      execution_date (تاریخ اجرای برنامه), packaging_type (نوع بسته بندی), extra_description (توضیحات اضافه).
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'پیش نویس'
        CONFIRMED = 'confirmed', 'تایید شده'
        IN_PROGRESS = 'in_progress', 'در حال اجرا'
        COMPLETED = 'completed', 'تکمیل شده'

    PACKAGING_CHOICES = [
        ('bulk', 'فله'),
        ('bag', 'کیسه'),
        ('carton', 'کارتن'),
    ]

    production_info = models.ForeignKey(
        ProductionInfo,
        on_delete=models.CASCADE,
        related_name='production_programs',
        verbose_name='اطلاعات فرمول',
        null=True, blank=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='production_programs',
        verbose_name='محصول',
        null=True, blank=True
    )
    formula_id = models.CharField(
        max_length=100,
        verbose_name='شناسه فرمول',
        null=True, blank=True
    )
    planned_weight_ton = models.DecimalField(
        max_digits=12, decimal_places=3,
        verbose_name='تناژ برنامه ریزی شده (تن)',
        null=True, blank=True
    )
    predicted_start_time = models.DateTimeField(
        verbose_name='ساعت شروع پیشبینی شده',
        null=True, blank=True
    )
    predicted_end_time = models.DateTimeField(
        verbose_name='ساعت پایان پیشبینی شده',
        null=True, blank=True
    )
    execution_date = jmodels.jDateField(
        verbose_name='تاریخ اجرای برنامه',
        null=True, blank=True
    )
    packaging_type = models.CharField(
        max_length=20,
        choices=PACKAGING_CHOICES,
        verbose_name='نوع بسته بندی',
        null=True, blank=True
    )
    extra_description = models.TextField(
        verbose_name='توضیحات اضافی برای فرمول',
        null=True, blank=True
    )

    planned_hours = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='مدت زمان برنامه (ساعت)',
        null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name='وضعیت'
    )

    inventory_snapshot = models.DecimalField(
        max_digits=12, decimal_places=3,
        null=True, blank=True,
        verbose_name='موجودی لحظه ثبت'
    )
    net_unplanned_requirement = models.DecimalField(
        max_digits=12, decimal_places=3,
        null=True, blank=True,
        verbose_name='نیاز برنامه ریزی نشده خالص'
    )
    consumption_summary = models.JSONField(
        null=True, blank=True,
        verbose_name='خلاصه مصرف مواد اولیه'
    )
    priority_index = models.DecimalField(
        max_digits=10, decimal_places=3,
        null=True, blank=True,
        verbose_name='شاخص اولویت'
    )

    # Consumption JSON snapshot (raw_material_id -> quantity_needed)
    # (moved above for clarity; left comment for reference)
    
    produced_weight_ton = models.DecimalField(
        max_digits=12, decimal_places=3,
        null=True, blank=True,
        verbose_name='وزن تولید شده واقعی'
    )

    fulfillment_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='درصد تحقق'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین ویرایش')
    started_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان شروع')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان تکمیل')

    class Meta:
        verbose_name = 'برنامه تولید'
        # Fixed a hidden null byte in verbose_name_plural string.
        verbose_name_plural = 'برنامه های تولید'
        ordering = ['-created_at']

    def __str__(self):
        p = self.product or (self.production_info.product if self.production_info else None)
        return f"برنامه تولید {p.name if p else ''} ({self.formula_id or ''}) - {self.get_status_display()}"

    @property
    def is_editable(self):
        return self.status == self.Status.DRAFT

    def lock_fields(self):  # called after confirmation
        pass  # Placeholder: business rules can be enforced in forms / admin

    def compute_consumption(self):
        """Calculate raw material requirements based on BOM and planned_weight_ton.
        Simple proportional logic: required = BOM.quantity * planned_weight_ton / min_batch_production (if defined).
        """
        if not self.production_info or not self.planned_weight_ton:
            return {}
        summary = {}
        min_batch = self.production_info.min_batch_production or Decimal('1')
        for bom in self.production_info.bom_items.all():
            if bom.quantity and bom.raw_material:
                required = (bom.quantity * self.planned_weight_ton) / min_batch
                summary[bom.raw_material.raw_material_id or str(bom.id)] = float(round(required, 4))
        return summary

    def compute_priority(self):
        """Priority index heuristic: (net_unplanned_requirement or (planned_weight - inventory)) / planned_weight.
        Clamped to [0,1.5] to avoid extremes."""
        if not self.planned_weight_ton:
            return None
        base_need = None
        if self.net_unplanned_requirement is not None:
            base_need = self.net_unplanned_requirement
        elif self.inventory_snapshot is not None:
            base_need = max(self.planned_weight_ton - self.inventory_snapshot, Decimal('0'))
        if base_need is None:
            return None
        pr = base_need / self.planned_weight_ton
        return float(round(min(max(pr, Decimal('0')), Decimal('1.5')), 3))

    def save(self, *args, **kwargs):
        # Auto populate formula/product from production_info if missing
        if self.production_info:
            if not self.formula_id:
                self.formula_id = self.production_info.formula_id
            if not self.product:
                self.product = self.production_info.product
        # Compute consumption & priority when confirming or in progress
        if self.status in [self.Status.CONFIRMED, self.Status.IN_PROGRESS, self.Status.COMPLETED]:
            self.consumption_summary = self.compute_consumption()
            self.priority_index = self.compute_priority()
        # Update timestamps
        if self.status == self.Status.IN_PROGRESS and not self.started_at:
            self.started_at = timezone.now()
        if self.status == self.Status.COMPLETED and not self.completed_at:
            self.completed_at = timezone.now()
        # Fulfillment percentage
        if self.produced_weight_ton and self.planned_weight_ton:
            self.fulfillment_percentage = round((self.produced_weight_ton / self.planned_weight_ton) * Decimal('100'), 2)
        super().save(*args, **kwargs)
