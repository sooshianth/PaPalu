from django.db import models
from django_jalali.db import models as jmodels
from django.conf import settings
from django.core.validators import MinValueValidator
from core.PersonFolder import Person, DeliveryAddress
from core.AllocationFolder.AllocationModel import Allocation
from core.PersonFolder.BankAccountModel import BankAccount


class Transport(models.Model):
    """مدل حمل"""

    DIRECTION_CHOICES = [
        ('inbound', 'ورودی'),
        ('outbound', 'خروجی'),
    ]
    
    # Status constants برای سازگاری با کد قدیمی
    STATUS_DRAFT = 'draft'
    STATUS_AWAITING_VEHICLE_ENTRY = 'pending_vehicle_entry'
    STATUS_VEHICLE_ENTERED = 'vehicle_entered'
    STATUS_AWAITING_UNLOADING = 'pending_unloading'
    STATUS_AWAITING_DELIVERY = 'awaiting_delivery'
    STATUS_AWAITING_WH_RECONCILIATION = 'awaiting_wh_reconciliation'
    STATUS_AWAITING_SETTLEMENT = 'pending_settlement'
    STATUS_COMPLETED = 'completed'
    STATUS_AWAITING_PAYMENT_DOC = 'awaiting_payment_doc'
    STATUS_PAYMENT_DOC_UPLOADED = 'payment_doc_uploaded'
    
    STATUS_CHOICES = [
        ('pending_vehicle_entry', 'در انتظار ورود خودرو به کارخانه'),
        ('loading', 'در انتظار بارگیری'),
        ('pending_waybill', 'در انتظار بارنامه'),
        ('pending_exit', 'در انتظار خروج'),
        ('pending_unloading', 'در انتظار تخلیه'),
        ('pending_logistics_approval', 'در انتظار تایید لجستیک'),
        ('pending_settlement', 'در انتظار تسویه'),
        ('completed', 'تکمیل شده'),
        ('awaiting_payment_doc', 'در انتظار بارگذاری اسناد پرداخت'),
        ('payment_doc_uploaded', 'سند پرداخت بارگذاری شده'),
    ]
    
    VEHICLE_TYPE_OFFICIAL_CHOICES = [
        ('official', 'رسمی'),
        ('unofficial', 'غیررسمی'),
    ]
    
    VEHICLE_TYPE_CHOICES = [
        ('truck', 'کامیون'),
        ('trailer', 'تریلی'),
        ('van', 'ون'),
        ('pickup', 'وانت'),
        ('other', 'سایر'),
    ]
    
    TRANSPORT_TYPE_CHOICES = [
        ('inbound', 'ورودی'),
        ('outbound', 'خروجی'),
    ]

    # شماره بارنامه به عنوان Primary Key
    waybill_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='شماره بارنامه'
    )
    
    allocation = models.ForeignKey(
        Allocation,
        on_delete=models.CASCADE,
        related_name='transports',
        verbose_name='تخصیص',
        null=True,
        blank=True
    )
    
    driver = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transports',
        verbose_name='شخص راننده'
    )
    
    delivery_postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی تحویل',
        null=True,
        blank=True
    )
    
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        verbose_name='ورودی/خروجی',
        null=True,
        blank=True
    )
    
    loading_date = jmodels.jDateField(
        verbose_name='تاریخ بارگیری',
        null=True,
        blank=True
    )
    
    unloading_date = jmodels.jDateField(
        verbose_name='تاریخ تخلیه',
        null=True,
        blank=True
    )
    
    transport_company = models.CharField(
        max_length=100,
        verbose_name='شرکت حمل و نقل',
        null=True,
        blank=True
    )

    waybill_date = jmodels.jDateField(
        verbose_name='تاریخ بارنامه',
        null=True,
        blank=True
    )
    
    waybill_serial = models.CharField(
        max_length=50,
        verbose_name='سریال بارنامه',
        null=True,
        blank=True
    )
    
    consignment_number = models.CharField(
        max_length=50,
        verbose_name='شماره حواله',
        null=True,
        blank=True
    )
    
    contract_code = models.CharField(
        max_length=50,
        verbose_name='کد قرارداد',
        null=True,
        blank=True
    )
    
    cardex_code = models.CharField(
        max_length=50,
        verbose_name='کد کاردکس',
        null=True,
        blank=True
    )
    
    origin = models.CharField(
        max_length=100,
        verbose_name='مبدأ',
        null=True,
        blank=True
    )
    
    destination = models.CharField(
        max_length=100,
        verbose_name='مقصد',
        null=True,
        blank=True
    )
    
    # فیلدهای جدید برای جذب خودرو
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending_vehicle_entry',
        verbose_name='وضعیت حمل',
        null=True,
        blank=True
    )
    
    carrier_recruitment = models.CharField(
        max_length=100,
        verbose_name='باربری جذب',
        null=True,
        blank=True
    )
    
    vehicle_type_official = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_OFFICIAL_CHOICES,
        verbose_name='نوع ماشین (رسمی/غیررسمی)',
        null=True,
        blank=True
    )

    # فیلدهای وزن حمل
    gross_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن پر',
        null=True,
        blank=True
    )
    
    empty_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالی',
        null=True,
        blank=True
    )
    
    net_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالص',
        null=True,
        blank=True
    )
    
    # فیلدهای اضافی برای سازگاری با PurchaseTransport
    tare_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالی',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        help_text='همان empty_weight برای سازگاری'
    )
    
    # فیلدهای مالی
    FREIGHT_PAYMENT_CHOICES = [
        ('calculated_in_invoice', 'کرایه محاسبه شده در فی'),
        ('pay_to_supplier', 'پرداخت به شرکت فروشنده'),
        ('pay_to_driver', 'پرداخت به راننده'),
    ]
    
    freight_payment_type = models.CharField(
        max_length=30,
        choices=FREIGHT_PAYMENT_CHOICES,
        verbose_name='نوع کرایه',
        null=True,
        blank=True,
        help_text='نوع پرداخت کرایه'
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
    
    # اطلاعات بانکی راننده
    driver_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver_transports',
        verbose_name='حساب بانکی راننده',
        help_text='حساب بانکی راننده'
    )
    
    # اطلاعات بانکی تامین‌کننده
    supplier_bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplier_transports',
        verbose_name='حساب بانکی تامین‌کننده',
        help_text='حساب بانکی تامین‌کننده'
    )
    
    # فیلدهای قدیمی برای سازگاری (deprecated - استفاده نکنید)
    driver_account_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='شماره حساب راننده (قدیمی)',
        help_text='DEPRECATED: از driver_bank_account استفاده کنید'
    )
    
    driver_sheba_number = models.CharField(
        max_length=26,
        null=True,
        blank=True,
        verbose_name='شماره شبا راننده (قدیمی)',
        help_text='DEPRECATED: از driver_bank_account استفاده کنید'
    )
    
    supplier_account_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name='شماره حساب تامین‌کننده (قدیمی)',
        help_text='DEPRECATED: از supplier_bank_account استفاده کنید'
    )
    
    supplier_sheba_number = models.CharField(
        max_length=26,
        null=True,
        blank=True,
        verbose_name='شماره شبا تامین‌کننده (قدیمی)',
        help_text='DEPRECATED: از supplier_bank_account استفاده کنید'
    )
    
    # تاریخ‌های اضافی
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
    
    delivery_date = jmodels.jDateField(
        verbose_name='تاریخ تحویل',
        null=True,
        blank=True
    )
    
    # فیلدهای بارنامه
    bill_of_lading_file = models.FileField(
        upload_to='bill_of_lading/%Y/%m/',
        verbose_name='فایل بارنامه',
        null=True,
        blank=True,
        help_text='فایل بارنامه فیزیکی/الکترونیکی'
    )
    
    bill_of_lading_date = jmodels.jDateField(
        verbose_name='تاریخ صدور بارنامه',
        null=True,
        blank=True
    )
    
    # اسناد پرداخت کرایه
    freight_payment_document = models.FileField(
        upload_to='freight_payment_documents/%Y/%m/',
        verbose_name='سند پرداخت کرایه',
        null=True,
        blank=True,
        help_text='سند حسابداری پرداخت کرایه (فیش واریز، تاییدیه بانکی، سند تسویه حساب نهایی)'
    )
    
    freight_payment_document_uploaded_at = jmodels.jDateTimeField(
        verbose_name='تاریخ بارگذاری سند',
        null=True,
        blank=True
    )
    
    freight_payment_document_uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_freight_payment_documents',
        verbose_name='بارگذار کننده سند'
    )
    
    # فیلدهای اضافی برای سازگاری
    transport_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        verbose_name='شماره حمل',
        null=True,
        blank=True,
        help_text='برای سازگاری با کد قدیمی - می‌تواند همان waybill_number باشد'
    )
    
    transport_type = models.CharField(
        max_length=10,
        choices=TRANSPORT_TYPE_CHOICES,
        verbose_name='نوع حمل',
        null=True,
        blank=True,
        help_text='برای سازگاری با کد قدیمی - می‌تواند همان direction باشد'
    )
    
    vehicle_type = models.CharField(
        max_length=20,
        choices=VEHICLE_TYPE_CHOICES,
        verbose_name='نوع ماشین',
        null=True,
        blank=True
    )
    
    plate_number = models.CharField(
        max_length=20,
        verbose_name='پلاک',
        null=True,
        blank=True
    )
    
    # یادداشت‌ها
    notes = models.TextField(
        verbose_name='یادداشت',
        null=True,
        blank=True
    )
    
    # Timestamps
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_transports',
        verbose_name='کاربر ایجاد کننده'
    )
    
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'حمل | حمل ها'
        verbose_name_plural = 'حمل | حمل ها'
        ordering = ['-waybill_date', 'waybill_number']

    def __str__(self):
        return self.waybill_number or str(self.pk)
    
    @property
    def purchase_order(self):
        """Property برای سازگاری با کد قدیمی - برمی‌گرداند allocation.order"""
        if self.allocation and self.allocation.order:
            return self.allocation.order
        return None

    def save(self, *args, **kwargs):
        # وضعیت‌های مجاز بر اساس جهت حمل را بررسی می‌کنیم
        if self.direction == 'inbound':
            allowed_statuses = [
                'pending_vehicle_entry',
                'pending_unloading',
                'pending_logistics_approval',
                'pending_settlement',
                'completed',
                'awaiting_payment_doc',
                'payment_doc_uploaded'
            ]
        elif self.direction == 'outbound':
            allowed_statuses = [
                'pending_vehicle_entry',
                'loading',
                'pending_waybill',
                'pending_exit',
                'completed',
                'awaiting_payment_doc',
                'payment_doc_uploaded'
            ]
        else:
            allowed_statuses = []

        if self.status and self.status not in allowed_statuses:
            raise ValueError("وضعیت انتخاب‌شده با جهت حمل سازگار نیست.")
        
        # برای سازگاری: اگر transport_type تنظیم نشده، از direction استفاده کن
        if not self.transport_type and self.direction:
            self.transport_type = self.direction
        
        # برای سازگاری: اگر transport_number تنظیم نشده، از waybill_number استفاده کن
        if not self.transport_number and self.waybill_number:
            self.transport_number = self.waybill_number

        super().save(*args, **kwargs)
    
    def can_delete(self):
        """بررسی امکان حذف حمل - فقط در وضعیت پیش‌نویس مجاز است"""
        return self.status == self.STATUS_DRAFT
    
    def send_guard_notification(self):
        """ارسال اعلان به نگهبان با اطلاعات خودرو - برای سازگاری با کد قدیمی"""
        import logging
        notification_logger = logging.getLogger("audit")
        
        # Log the notification (in a real system, this would send an actual notification)
        notification_data = {
            'نوع_ماشین': self.get_vehicle_type_display() if self.vehicle_type else 'ثبت نشده',
            'پلاک': self.plate_number or 'ثبت نشده',
            'شماره_سفارش': self.allocation.order.order_number if self.allocation and self.allocation.order else 'نامشخص',
            'زمان_ثبت': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else 'نامشخص'
        }
        
        notification_logger.info(
            f"اعلان به نگهبان - ورود خودرو: {notification_data['نوع_ماشین']} | "
            f"پلاک: {notification_data['پلاک']} | سفارش: {notification_data['شماره_سفارش']}"
        )