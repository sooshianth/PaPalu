from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django_jalali.db import models as jmodels
from core.PersonFolder import Person


class Order(models.Model):
    """مدل سفارش"""

    ORDER_TYPE_CHOICES = [
        ('purchase', 'خرید'),
        ('sale', 'فروش'),
    ]
    
    SOURCE_CHOICES = [
        ('api', 'API'),
        ('expert', 'کارشناس'),
    ]
    
    STATUS_CHOICES = [
        # وضعیت‌های سفارش فروش
        ('pending_proforma_issue', 'در انتظار صدور پیش فاکتور'),
        ('pending_customer_proforma_upload', 'در انتظار آپلود پیش فاکتور مشتری'),
        # بعد از آپلود تأیید پیش فاکتور، سفارش به این وضعیت می‌رود
        ('pending_transaction_receipt_upload', 'در انتظار بارگذاری رسید تراکنش'),
        # بعد از تکمیل بارگذاری رسیدها، سفارش به این وضعیت می‌رود
        ('pending_accounting_approval', 'در انتظار تایید حسابداری'),
        ('pending_allocation', 'در انتظار تخصیص'),
        ('pending_allocation_approval', 'در انتظار تأیید تخصیص'),
        ('pending_factory', 'در انتظار کارخانه'),
        ('pending_unloading_approval', 'در انتظار تایید تخلیه'),
        ('pending_settlement', 'در انتظار تسویه'),
        ('pending_settlement_approval', 'در انتظار تایید تسویه کامل'),
        # وضعیت‌های سفارش خرید تامینی
        ('draft', 'پیش‌نویس'),
        ('awaiting_transport_def', 'در انتظار تعریف حمل'),
        ('awaiting_vehicle_entry', 'در انتظار ورود خودرو'),
        ('awaiting_delivery', 'در انتظار تحویل بار'),
        ('awaiting_wh_reconciliation', 'در انتظار تطبیق اطلاعات انبار'),
        ('awaiting_final_settlement', 'در انتظار تسویه نهایی'),
        ('completed', 'تکمیل سفارش'),
        # وضعیت‌های مشترک
        ('cancelled', 'لغو شده'),
        ('archived', 'بایگانی شده'),
    ]
    
    FREIGHT_PAYMENT_CHOICES = [
        # برای سفارش فروش
        ('seller', 'فروشنده'),
        ('buyer', 'خریدار'),
        ('shared', 'مشترک'),
        # برای سفارش خرید تامینی
        ('cash', 'نقدی'),
        ('credit', 'اعتباری'),
        ('included', 'شامل در قیمت'),
        ('separate', 'پرداخت جداگانه'),
    ]
    
    
    # شماره سفارش
    order_number = models.CharField(
        max_length=100,
        primary_key=True,
        verbose_name='شماره سفارش'
    )
    
    # مشتری/تامین‌کننده (بسته به نوع سفارش)
    customer = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='مشتری/تامین‌کننده',
        null=True,
        blank=True,
        help_text='برای سفارش فروش: مشتری، برای سفارش خرید: تامین‌کننده'
    )
    
    # نوع سفارش(خرید/فروش)
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='نوع سفارش'
    )
    
    # منبع ثبت سفارش (api/کارشناس)
    registration_source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        null=True,
        blank=True,
        verbose_name='منبع ثبت سفارش'
    )
    
    # وضعیت
    status = models.CharField(
        max_length=100,
        choices=STATUS_CHOICES,
        default='pending',
        null=True,
        blank=True,
        verbose_name='وضعیت'
    )
    
    # تاریخ ایجاد
    creation_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name='تاریخ ایجاد'
    )
    
    # کاربر ثبت کننده
    registered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_orders',
        verbose_name='کاربر ثبت کننده'
    )
    
    # نوع پرداخت کرایه
    freight_payment_type = models.CharField(
        max_length=20,
        choices=FREIGHT_PAYMENT_CHOICES,
        null=True,
        blank=True,
        verbose_name='نوع پرداخت کرایه'
    )
    
    # وزن کل ارسال (محاسبه شده از اقلام)
    total_shipment_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل ارسال',
        help_text='مجموع وزن اقلام ارسال شده'
    )
    
    # وزن کل تحویل (محاسبه شده از اقلام)
    total_delivery_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل تحویل',
        help_text='مجموع وزن اقلام تحویل شده'
    )
    
    # شماره سند حسابداری ثبت شده
    accounting_document_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='شماره سند حسابداری ثبت شده'
    )
    
    # فیلدهای مربوط به سفارش خرید تامینی
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
    
    # Timestamps
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
        verbose_name = 'سفارش | سفارش ها'
        verbose_name_plural = 'سفارش | سفارش ها'
        ordering = ['-created_at']
    
    def __str__(self):
        customer_name = self.customer.name if self.customer else 'بدون مشتری'
        return f"{self.order_number} - {customer_name} - {self.get_order_type_display()}"
    
    def get_total_amount(self):
        """
        محاسبه مبلغ کل سفارش از مجموع اقلام
        """
        from django.db.models import Sum
        total = self.order_items.aggregate(total=Sum('total_purchase_cost'))['total']
        return total or 0
    
    @staticmethod
    def generate_order_number():
        """
        تولید خودکار شماره سفارش
        شروع از 100000 و افزایش تدریجی
        """
        last_order = Order.objects.all().order_by('-order_number').first()
        if last_order:
            try:
                last_number = int(last_order.order_number)
                if last_number >= 100000:
                    return str(last_number + 1)
                else:
                    return '100000'
            except (ValueError, TypeError):
                return '100000'
        return '100000'
    
    # Constants for purchase order statuses
    STATUS_DRAFT = 'draft'
    STATUS_AWAITING_TRANSPORT_DEFINITION = 'awaiting_transport_def'
    STATUS_AWAITING_VEHICLE_ENTRY = 'awaiting_vehicle_entry'
    STATUS_AWAITING_DELIVERY = 'awaiting_delivery'
    STATUS_AWAITING_WAREHOUSE_RECONCILIATION = 'awaiting_wh_reconciliation'
    STATUS_AWAITING_FINAL_SETTLEMENT = 'awaiting_final_settlement'
    STATUS_COMPLETED = 'completed'
    
    # Workflow for purchase orders
    WORKFLOW_ALLOWED = {
        STATUS_DRAFT: {STATUS_AWAITING_TRANSPORT_DEFINITION},
        STATUS_AWAITING_TRANSPORT_DEFINITION: {STATUS_AWAITING_VEHICLE_ENTRY},
        STATUS_AWAITING_VEHICLE_ENTRY: {STATUS_AWAITING_DELIVERY},
        STATUS_AWAITING_DELIVERY: {STATUS_AWAITING_WAREHOUSE_RECONCILIATION},
        STATUS_AWAITING_WAREHOUSE_RECONCILIATION: {STATUS_AWAITING_FINAL_SETTLEMENT},
        STATUS_AWAITING_FINAL_SETTLEMENT: {STATUS_COMPLETED},
    }
    
    def can_delete(self):
        """بررسی امکان حذف سفارش (فقط در وضعیت پیش‌نویس)"""
        return self.status == self.STATUS_DRAFT and self.order_type == 'purchase'
    
    def delete(self, *args, **kwargs):
        """حذف سفارش با بررسی وضعیت"""
        if not self.can_delete():
            raise ValueError('حذف سفارش فقط در وضعیت پیش‌نویس مجاز است.')
        return super().delete(*args, **kwargs)
    
    def transition(self, new_status, user=None, note=None):
        """تغییر وضعیت سفارش با ثبت لاگ"""
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError('وضعیت جدید نامعتبر است.')
        
        # فقط برای سفارش‌های خرید workflow را اعمال کن
        if self.order_type == 'purchase':
            allowed = self.WORKFLOW_ALLOWED.get(self.status, set())
            if new_status not in allowed:
                raise ValueError('مسیر تغییر وضعیت غیرمجاز است.')
        
        old_status = self.status
        self.status = new_status
        with transaction.atomic():
            self.save()
            OrderStatusLog.objects.create(
                order=self,
                old_status=old_status or '',
                new_status=new_status,
                changed_by=user,
                note=note or ''
            )
    
    def save(self, *args, **kwargs):
        """ذخیره سفارش با منطق خودکار"""
        creating = self._state.adding
        
        # تولید شماره سفارش برای سفارش‌های خرید
        if creating and not self.order_number and self.order_type == 'purchase':
            # استفاده از فرمت PO- برای سفارش‌های خرید
            last_po = Order.objects.filter(order_type='purchase', order_number__startswith='PO-').order_by('-order_number').first()
            if last_po:
                try:
                    # استخراج عدد از PO-0000001
                    last_num = int(last_po.order_number.split('-')[1])
                    self.order_number = f"PO-{last_num + 1:07d}"
                except (ValueError, IndexError):
                    self.order_number = f"PO-{1:07d}"
            else:
                self.order_number = f"PO-{1:07d}"
        
        # تنظیم وضعیت پیش‌فرض برای سفارش‌های خرید
        if creating and self.order_type == 'purchase' and not self.status:
            self.status = self.STATUS_DRAFT
        
        # تغییر خودکار وضعیت وقتی پیش‌فاکتور تایید می‌شود
        if self.pre_invoice_approved and self.status == self.STATUS_DRAFT and self.order_type == 'purchase':
            self.status = self.STATUS_AWAITING_TRANSPORT_DEFINITION
        
        super().save(*args, **kwargs)


class OrderStatusLog(models.Model):
    """لاگ تغییر وضعیت سفارش"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_logs'
    )
    old_status = models.CharField(max_length=100)
    new_status = models.CharField(max_length=100)
    changed_at = jmodels.jDateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes'
    )
    note = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'لاگ وضعیت سفارش'
        verbose_name_plural = 'لاگ‌های وضعیت سفارش'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.order.order_number}: {self.old_status} -> {self.new_status}"