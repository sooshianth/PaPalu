from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django_jalali.db import models as jmodels
from ..PersonFolder.PersonModel import Person
from ..RawMaterialFolder.RawMaterialModel import RawMaterial


class ProcurementPurchaseOrder(models.Model):
    """سفارش خرید مواد اولیه (Internal Procurement)

    This model is distinct from sales-side purchase orders. It represents what the
    company is buying from suppliers. Workflow enforced via status choices and
    transition helper. Order number generated automatically at creation.
    """

    STATUS_DRAFT = 'draft'
    STATUS_AWAITING_TRANSPORT_DEFINITION = 'awaiting_transport_def'
    STATUS_AWAITING_VEHICLE_ENTRY = 'awaiting_vehicle_entry'
    STATUS_AWAITING_DELIVERY = 'awaiting_delivery'
    STATUS_AWAITING_WAREHOUSE_RECONCILIATION = 'awaiting_wh_reconciliation'
    STATUS_AWAITING_FINAL_SETTLEMENT = 'awaiting_final_settlement'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'پیش‌نویس'),
        (STATUS_AWAITING_TRANSPORT_DEFINITION, 'در انتظار تعریف حمل'),
        (STATUS_AWAITING_VEHICLE_ENTRY, 'در انتظار ورود خودرو'),
        (STATUS_AWAITING_DELIVERY, 'در انتظار تحویل بار'),
        (STATUS_AWAITING_WAREHOUSE_RECONCILIATION, 'در انتظار تطبیق اطلاعات انبار'),
        (STATUS_AWAITING_FINAL_SETTLEMENT, 'در انتظار تسویه نهایی'),
        (STATUS_COMPLETED, 'تکمیل سفارش'),
    ]

    FREIGHT_PAYMENT_CHOICES = [
        ('cash', 'نقدی'),
        ('credit', 'اعتباری'),
        ('included', 'شامل در قیمت'),
        ('separate', 'پرداخت جداگانه'),
    ]

    order_number = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
        verbose_name='شماره سفارش'
    )
    supplier = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='procurement_purchase_orders',
        verbose_name='تامین‌کننده'
    )
    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
        verbose_name='وضعیت'
    )
    freight_payment_type = models.CharField(
        max_length=20,
        choices=FREIGHT_PAYMENT_CHOICES,
        verbose_name='نوع پرداخت کرایه'
    )
    # Financial data (editable only until payment confirmed)
    subtotal_without_freight = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='جمع قیمت بدون کرایه',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    freight_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='هزینه کرایه',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد مالیات بر ارزش افزوده',
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    payment_confirmed = models.BooleanField(
        default=False,
        verbose_name='پرداخت تایید شده'
    )
    pre_invoice_file = models.FileField(
        upload_to='procurement/preinvoices/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='فایل پیش‌فاکتور'
    )
    pre_invoice_approved = models.BooleanField(
        default=False,
        verbose_name='پیش‌فاکتور تایید شد'
    )
    external_system_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='شناسه یکتا در سیستم دامپروش/کی‌اچ/انبار/لبه‌ژنت'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_procurement_purchase_orders',
        verbose_name='کاربر ثبت کننده'
    )

    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'سفارش خرید | سفارشات خرید'
        verbose_name_plural = 'سفارش خرید | سفارشات خرید'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if creating and not self.order_number:
            # Simple sequential pattern: PO-<id after save>. Use transaction for safety.
            super().save(*args, **kwargs)
            self.order_number = f"PO-{self.id:07d}"
            # Status initial always draft per core rule
            if not self.status:
                self.status = self.STATUS_DRAFT
            return super().save(update_fields=['order_number', 'status'])
        # Auto transition when pre-invoice approved from draft
        if self.pre_invoice_approved and self.status == self.STATUS_DRAFT:
            self.status = self.STATUS_AWAITING_TRANSPORT_DEFINITION
        super().save(*args, **kwargs)

    def can_delete(self):
        return self.status == self.STATUS_DRAFT

    def delete(self, *args, **kwargs):
        if not self.can_delete():
            raise ValueError('حذف سفارش فقط در وضعیت پیش‌نویس مجاز است.')
        return super().delete(*args, **kwargs)

    WORKFLOW_ALLOWED = {
        STATUS_DRAFT: {STATUS_AWAITING_TRANSPORT_DEFINITION},
        STATUS_AWAITING_TRANSPORT_DEFINITION: {STATUS_AWAITING_VEHICLE_ENTRY},
        STATUS_AWAITING_VEHICLE_ENTRY: {STATUS_AWAITING_DELIVERY},
        STATUS_AWAITING_DELIVERY: {STATUS_AWAITING_WAREHOUSE_RECONCILIATION},
        STATUS_AWAITING_WAREHOUSE_RECONCILIATION: {STATUS_AWAITING_FINAL_SETTLEMENT},
        STATUS_AWAITING_FINAL_SETTLEMENT: {STATUS_COMPLETED},
    }

    def transition(self, new_status, user=None, note=None):
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError('وضعیت جدید نامعتبر است.')
        allowed = self.WORKFLOW_ALLOWED.get(self.status, set())
        if new_status not in allowed:
            raise ValueError('مسیر تغییر وضعیت غیرمجاز است.')
        old_status = self.status
        self.status = new_status
        with transaction.atomic():
            self.save()
            ProcurementPurchaseOrderStatusLog.objects.create(
                purchase_order=self,
                old_status=old_status,
                new_status=new_status,
                changed_by=user,
                note=note or ''
            )


class ProcurementPurchaseOrderMaterial(models.Model):
    """مواد اولیه مرتبط با سفارش خرید (Many-to-many through)"""
    purchase_order = models.ForeignKey(
        ProcurementPurchaseOrder,
        on_delete=models.CASCADE,
        related_name='materials'
    )
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.PROTECT,
        related_name='procurement_order_items'
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name='مقدار'
    )
    unit = models.CharField(
        max_length=10,
        verbose_name='واحد',
        null=True,
        blank=True
    )
    notes = models.TextField(
        verbose_name='توضیحات',
        null=True,
        blank=True,
        help_text='توضیحات خاص این ماده در این سفارش'
    )
    # Per-material financial and logistics fields
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='قیمت واحد',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='قیمت کل',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    freight_included = models.BooleanField(
        default=False,
        verbose_name='بهای تمام شده بدون احتساب کرایه'
    )
    vat_on_material = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مالیات بر ارزش افزوده (این ماده)',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    freight_cost_completed = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='بهای تمام شده کرایه خرید',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    total_cost_completed = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='بهای تمام شده خرید',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    external_allocation_id = models.CharField(
        max_length=100,
        verbose_name='شناسه تخصیص (تخصیص دیفالت تأمین)',
        null=True,
        blank=True
    )
    created_at = jmodels.jDateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'آیتم سفارش خرید'
        verbose_name_plural = 'آیتم‌های سفارش خرید'

    def __str__(self):
        return f"{self.purchase_order.order_number} - {self.raw_material.name}" if self.purchase_order_id else 'PO Material'


class ProcurementPurchaseOrderStatusLog(models.Model):
    """لاگ تغییر وضعیت سفارش خرید"""
    purchase_order = models.ForeignKey(
        ProcurementPurchaseOrder,
        on_delete=models.CASCADE,
        related_name='status_logs'
    )
    old_status = models.CharField(max_length=40)
    new_status = models.CharField(max_length=40)
    changed_at = jmodels.jDateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='procurement_po_status_changes'
    )
    note = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'لاگ وضعیت سفارش خرید'
        verbose_name_plural = 'لاگ‌های وضعیت سفارش خرید'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.purchase_order.order_number}: {self.old_status} -> {self.new_status}"
