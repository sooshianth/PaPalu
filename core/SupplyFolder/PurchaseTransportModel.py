from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator
from django_jalali.db import models as jmodels
from ..TransportFolder.TransportModel import Transport
from .ProcurementPurchaseOrderModel import ProcurementPurchaseOrder
from ..PersonFolder.PersonModel import Person


class PurchaseTransport(models.Model):
    """حمل برای سفارش خرید
    
    این مدل رابط بین سفارش خرید و حمل را مدیریت می‌کند.
    هر سفارش خرید می‌تواند دارای چندین حمل باشد.
    """
    
    STATUS_DRAFT = 'draft'
    STATUS_AWAITING_VEHICLE_ENTRY = 'awaiting_vehicle_entry'
    STATUS_VEHICLE_ENTERED = 'vehicle_entered'
    STATUS_AWAITING_UNLOADING = 'awaiting_unloading'
    STATUS_AWAITING_DELIVERY = 'awaiting_delivery'
    STATUS_AWAITING_WH_RECONCILIATION = 'awaiting_wh_reconciliation'
    STATUS_COMPLETED = 'completed'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'پیش‌نویس'),
        (STATUS_AWAITING_VEHICLE_ENTRY, 'در انتظار ورود خودرو'),
        (STATUS_VEHICLE_ENTERED, 'خودرو وارد شده'),
        (STATUS_AWAITING_UNLOADING, 'در انتظار تخلیه'),
        (STATUS_AWAITING_DELIVERY, 'در انتظار تحویل بار'),
        (STATUS_AWAITING_WH_RECONCILIATION, 'در انتظار تطبیق انبار'),
        (STATUS_COMPLETED, 'تکمیل شده'),
    ]
    
    TRANSPORT_TYPE_CHOICES = [
        ('inbound', 'ورودی'),
        ('outbound', 'خروجی'),
    ]
    
    VEHICLE_TYPE_CHOICES = [
        ('truck', 'کامیون'),
        ('trailer', 'تریلی'),
        ('van', 'ون'),
        ('pickup', 'وانت'),
        ('other', 'سایر'),
    ]
    
    # Primary Key
    transport_id = models.AutoField(
        primary_key=True,
        verbose_name='شناسه حمل'
    )
    
    # Foreign Keys
    purchase_order = models.ForeignKey(
        ProcurementPurchaseOrder,
        on_delete=models.CASCADE,
        related_name='transports',
        verbose_name='سفارش خرید'
    )
    
    transport_ref = models.OneToOneField(
        Transport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_transport',
        verbose_name='ارجاع به حمل اصلی'
    )
    
    # Status
    status = models.CharField(
        max_length=40,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True,
        verbose_name='وضعیت'
    )
    
    # Basic Information
    transport_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name='شماره حمل',
        null=True,
        blank=True
    )
    
    transport_type = models.CharField(
        max_length=10,
        choices=TRANSPORT_TYPE_CHOICES,
        default='inbound',
        verbose_name='نوع حمل'
    )
    
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        verbose_name='نوع ماشین',
        default='truck'
    )
    
    plate_number = models.CharField(
        max_length=20,
        verbose_name='پلاک',
        null=True,
        blank=True
    )
    
    driver = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_transports_as_driver',
        verbose_name='راننده',
        limit_choices_to={'type': 'driver'}
    )
    
    # Payment type fields (matching screenshot requirements)
    freight_payment_type = models.CharField(
        max_length=20,
        verbose_name='نوع کرایه',
        null=True,
        blank=True,
        help_text='نقدی، اعتباری، و غیره'
    )
    
    initial_freight = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کرایه اولیه',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    total_freight = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کرایه کل',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    discount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='تخفیف',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    surplus = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مازاد',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    freight_payment = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='کرایه پرداختی',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    # Driver account references (Foreign Keys to Person with type='driver')
    driver_account_number = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_transports_account_number',
        verbose_name='شماره حساب راننده',
        limit_choices_to={'type': 'driver'}
    )
    
    driver_sheba_number = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_transports_sheba_number',
        verbose_name='شماره شبا راننده',
        limit_choices_to={'type': 'driver'}
    )
    
    # Dates
    expected_arrival_date = jmodels.jDateField(
        verbose_name='تاریخ پیش‌بینی ورود',
        null=True,
        blank=True
    )
    
    actual_arrival_date = jmodels.jDateField(
        verbose_name='تاریخ واقعی ورود',
        null=True,
        blank=True
    )
    
    loading_date = jmodels.jDateField(
        verbose_name='تاریخ بارگیری',
        null=True,
        blank=True
    )
    
    delivery_date = jmodels.jDateField(
        verbose_name='تاریخ تحویل',
        null=True,
        blank=True
    )
    
    # Weight Information
    gross_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن ناخالص',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    tare_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالی',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    net_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالص',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    
    # Additional Information
    notes = models.TextField(
        verbose_name='یادداشت',
        null=True,
        blank=True
    )
    
    waybill_number = models.CharField(
        max_length=50,
        verbose_name='شماره بارنامه',
        null=True,
        blank=True
    )
    
    # Timestamps
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_purchase_transports',
        verbose_name='کاربر ایجاد کننده'
    )
    
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    
    class Meta:
        verbose_name = 'حمل سفارش خرید'
        verbose_name_plural = 'حمل‌های سفارش خرید'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transport_number']),
            models.Index(fields=['status']),
            models.Index(fields=['purchase_order']),
        ]
    
    def __str__(self):
        return self.transport_number or f"Transport #{self.transport_id}"
    
    def save(self, *args, **kwargs):
        creating = self._state.adding
        if creating and not self.transport_number:
            # Generate transport number after first save
            super().save(*args, **kwargs)
            self.transport_number = f"PT-{self.transport_id:07d}"
            return super().save(update_fields=['transport_number'])
        super().save(*args, **kwargs)
    
    def can_delete(self):
        """فقط حمل‌های پیش‌نویس قابل حذف هستند"""
        return self.status == self.STATUS_DRAFT
    
    def delete(self, *args, **kwargs):
        if not self.can_delete():
            raise ValueError('حذف حمل فقط در وضعیت پیش‌نویس مجاز است.')
        return super().delete(*args, **kwargs)
    
    # Workflow transitions
    WORKFLOW_ALLOWED = {
        STATUS_DRAFT: {STATUS_AWAITING_VEHICLE_ENTRY},
        STATUS_AWAITING_VEHICLE_ENTRY: {STATUS_VEHICLE_ENTERED, STATUS_AWAITING_UNLOADING},  # Can go directly to unloading or through vehicle_entered
        STATUS_VEHICLE_ENTERED: {STATUS_AWAITING_UNLOADING},
        STATUS_AWAITING_UNLOADING: {STATUS_AWAITING_DELIVERY},
        STATUS_AWAITING_DELIVERY: {STATUS_AWAITING_WH_RECONCILIATION},
        STATUS_AWAITING_WH_RECONCILIATION: {STATUS_COMPLETED},
    }
    
    def transition(self, new_status, user=None, note=None):
        """تغییر وضعیت حمل با ثبت لاگ و به‌روزرسانی وضعیت سفارش خرید"""
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError('وضعیت جدید نامعتبر است.')
        allowed = self.WORKFLOW_ALLOWED.get(self.status, set())
        if new_status not in allowed:
            raise ValueError('مسیر تغییر وضعیت غیرمجاز است.')
        old_status = self.status
        self.status = new_status
        with transaction.atomic():
            self.save()
            PurchaseTransportStatusLog.objects.create(
                purchase_transport=self,
                old_status=old_status,
                new_status=new_status,
                changed_by=user,
                note=note or ''
            )
            
            # Update purchase order status when transport moves from draft to awaiting_vehicle_entry
            if old_status == self.STATUS_DRAFT and new_status == self.STATUS_AWAITING_VEHICLE_ENTRY:
                po = self.purchase_order
                if po.status == ProcurementPurchaseOrder.STATUS_AWAITING_TRANSPORT_DEFINITION:
                    po.status = ProcurementPurchaseOrder.STATUS_AWAITING_VEHICLE_ENTRY
                    po.save(update_fields=['status'])
            
            # Send notification to guard when status changes to awaiting_vehicle_entry
            if new_status == self.STATUS_AWAITING_VEHICLE_ENTRY:
                self.send_guard_notification()
    
    def send_guard_notification(self):
        """ارسال اعلان به نگهبان با اطلاعات خودرو"""
        import logging
        notification_logger = logging.getLogger("audit")
        
        # Log the notification (in a real system, this would send an actual notification)
        notification_data = {
            'نوع_ماشین': self.get_vehicle_type_display(),
            'پلاک': self.plate_number or 'ثبت نشده',
            'شماره_سفارش': self.purchase_order.order_number,
            'زمان_ثبت': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        notification_logger.info(
            f"اعلان به نگهبان - ورود خودرو: {notification_data['نوع_ماشین']} | "
            f"پلاک: {notification_data['پلاک']} | سفارش: {notification_data['شماره_سفارش']}"
        )


class PurchaseTransportStatusLog(models.Model):
    """لاگ تغییر وضعیت حمل سفارش خرید"""
    purchase_transport = models.ForeignKey(
        PurchaseTransport,
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
        related_name='purchase_transport_status_changes'
    )
    note = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'لاگ وضعیت حمل خرید'
        verbose_name_plural = 'لاگ‌های وضعیت حمل خرید'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.purchase_transport.transport_number}: {self.old_status} -> {self.new_status}"
