from django.db import models
from django_jalali.db import models as jmodels
from .OrderModel import Order
from ..SettlementFolder.SettlementModel import Settlement
from ..PersonFolder.PersonModel import Person


class DocumentRelation(models.Model):
    """مدل ارتباط با اسناد"""

    # Foreign key to Order
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='document_relations',
        verbose_name='سفارش'
    )
    
    # شناسه تخصیص ها
    allocation_ids = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='شناسه تخصیص‌ها',
        help_text='شناسه‌های تخصیص مرتبط با این سفارش (جدا شده با کاما)'
    )
    
    # شماره بارنامه ها
    waybill_numbers = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name='شماره بارنامه‌ها',
        help_text='شماره‌های بارنامه مرتبط با این سفارش (جدا شده با کاما)'
    )
    
    # تسویه مربوط
    related_settlement = models.ForeignKey(
        Settlement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_relations',
        verbose_name='تسویه مربوط'
    )
    
    # پرداخت ها - رابطه many-to-many با مدل پرداخت (در صورت وجود)
    # payments = models.ManyToManyField(
    #     'PaymentFolder.Payment',
    #     blank=True,
    #     related_name='order_relations',
    #     verbose_name='پرداخت‌ها'
    # )
    
    # تراکنش ها - رابطه many-to-many با مدل تراکنش (در صورت وجود)
    # transactions = models.ManyToManyField(
    #     'TransactionFolder.Transaction',
    #     blank=True,
    #     related_name='order_relations',
    #     verbose_name='تراکنش‌ها'
    # )
    
    # شخص خریدار
    buyer = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_order_relations',
        verbose_name='شخص خریدار'
    )
    
    # شخص فروشنده
    seller = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_order_relations',
        verbose_name='شخص فروشنده'
    )
    
    # تاریخ ایجاد
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        verbose_name='تاریخ ایجاد'
    )
    
    # تاریخ بروزرسانی
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        verbose_name='تاریخ بروزرسانی'
    )
    
    class Meta:
        verbose_name = 'ارتباط با اسناد'
        verbose_name_plural = 'ارتباطات با اسناد'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"ارتباطات سفارش {self.order.order_number}"
    
    def get_allocation_ids_list(self):
        """برگرداندن لیست شناسه‌های تخصیص"""
        if self.allocation_ids:
            return [id.strip() for id in self.allocation_ids.split(',')]
        return []
    
    def get_waybill_numbers_list(self):
        """برگرداندن لیست شماره‌های بارنامه"""
        if self.waybill_numbers:
            return [num.strip() for num in self.waybill_numbers.split(',')]
        return []
