from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels


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
        unique=True,
        null=True,
        blank=True,
        primary_key=True,
        verbose_name='شماره سفارش'
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
        max_length=20,
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
    
    # وزن کل سفارش
    total_order_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل سفارش'
    )
    
    # وزن کل ارسال
    total_shipment_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل ارسال'
    )
    
    # وزن کل تحویل
    total_delivery_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل تحویل'
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
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order_number} - {self.get_order_type_display()}"
