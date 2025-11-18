from django.db import models
from django.contrib.auth.models import User
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
        ('pending', 'در انتظار'),
        ('confirmed', 'تایید شده'),
        ('processing', 'در حال پردازش'),
        ('pending_proforma_issue', 'در انتظار صدور پیش فاکتور'),
        ('pending_customer_proforma_upload', 'در انتظار آپلود پیش فاکتور مشتری'),
        # بعد از آپلود تأیید پیش فاکتور، سفارش به این وضعیت می‌رود
        ('pending_transaction_receipt_upload', 'در انتظار بارگذاری رسید تراکنش'),
        # بعد از تکمیل بارگذاری رسیدها، سفارش به این وضعیت می‌رود
        ('pending_accounting_approval', 'در انتظار تایید حسابداری'),
        ('pending_allocation', 'در انتظار تخصیص'),
        ('pending_allocation_approval', 'در انتظار تأیید تخصیص'),
        ('completed', 'تکمیل شده'),
        ('cancelled', 'لغو شده'),
        ('archived', 'بایگانی شده'),
    ]
    
    FREIGHT_PAYMENT_CHOICES = [
        ('seller', 'فروشنده'),
        ('buyer', 'خریدار'),
        ('shared', 'مشترک'),
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
