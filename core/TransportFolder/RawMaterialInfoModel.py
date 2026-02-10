from django.db import models
from django.core.validators import MinValueValidator
from .TransportModel import Transport
from core.RawMaterialFolder import RawMaterial
from core.OrderFolder import OrderItem


class RawMaterialInfo(models.Model):
    """مدل اطلاعات مواد اولیه در حمل - برای پیگیری مقدار هر ماده اولیه در هر حمل"""

    WEIGHT_UNIT_CHOICES = [
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
        ('bag', 'کیسه'),
        ('piece', 'عدد'),
    ]

    PACKAGING_TYPE_CHOICES = [
        ('bag', 'کیسه'),
        ('pallet', 'پالت'),
        ('bulk', 'فله'),
        ('box', 'جعبه'),
        ('barrel', 'بشکه'),
        ('sack', 'گونی'),
        ('other', 'سایر'),
    ]

    transport = models.ForeignKey(
        Transport,
        on_delete=models.CASCADE,
        related_name='raw_material_infos',
        verbose_name='حمل'
    )
    
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='transport_allocations',
        verbose_name='ماده اولیه سفارش',
        help_text='ارجاع به ماده اولیه در سفارش'
    )
    
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.PROTECT,
        related_name='transport_raw_material_infos',
        verbose_name='ماده اولیه'
    )
    
    allocated_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='مقدار تخصیص یافته',
        validators=[MinValueValidator(0)],
        help_text='مقدار این ماده اولیه در این حمل'
    )
    
    net_weight = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name='وزن خالص (کیلوگرم)',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        help_text='وزن خالص محاسبه شده این ماده اولیه در تخلیه'
    )
    
    destination_warehouse = models.ForeignKey(
        'core.Warehouse',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_material_info_destinations',
        verbose_name='انبار مقصد (در تخلیه)',
        help_text='انبار مقصدی که این ماده در تحویل انبار به آن تخلیه شده'
    )
    
    weight_unit = models.CharField(
        max_length=10,
        choices=WEIGHT_UNIT_CHOICES,
        verbose_name='واحد وزن',
        default='kg'
    )
    
    packaging_type = models.CharField(
        max_length=20,
        choices=PACKAGING_TYPE_CHOICES,
        verbose_name='نوع بسته بندی',
        null=True,
        blank=True
    )
    
    number_of_packages = models.IntegerField(
        verbose_name='تعداد بسته',
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='تعداد کیسه، پالت، و غیره'
    )
    
    notes = models.TextField(
        verbose_name='یادداشت',
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی'
    )

    class Meta:
        verbose_name = 'حمل | اطلاعات ماده اولیه'
        verbose_name_plural = 'حمل | اطلاعات مواد اولیه'
        ordering = ['transport', 'raw_material']
        unique_together = [['transport', 'order_item']]

    def __str__(self):
        return f"{self.transport.transport_number} - {self.raw_material.name} - {self.allocated_quantity} {self.get_weight_unit_display()}"
    
    def clean(self):
        """اعتبارسنجی: مقدار تخصیص یافته نباید بیشتر از مقدار باقیمانده در سفارش باشد"""
        from django.core.exceptions import ValidationError
        from decimal import Decimal
        
        if not self.order_item:
            raise ValidationError('باید یک ماده اولیه از سفارش انتخاب شود.')
        
        # بررسی که ماده اولیه با order_item مطابقت دارد
        if self.raw_material != self.order_item.raw_material:
            raise ValidationError('ماده اولیه انتخاب شده با ماده اولیه سفارش مطابقت ندارد.')
        
        # محاسبه مقدار باقیمانده در واحد سفارش
        remaining_in_order_unit = self.order_item.get_remaining_quantity()
        
        # تبدیل مقدار باقیمانده به کیلوگرم
        # چون allocated_quantity همیشه در کیلوگرم است
        order_item = self.order_item
        if order_item.weight_unit == 'kg':
            remaining_in_kg = remaining_in_order_unit
        elif order_item.weight_unit == 'ton':
            remaining_in_kg = remaining_in_order_unit * Decimal('1000')
        elif order_item.weight_unit == 'bag' and order_item.bag_weight:
            remaining_in_kg = remaining_in_order_unit * Decimal(str(order_item.bag_weight))
        elif order_item.weight_unit == 'piece':
            remaining_in_kg = remaining_in_order_unit
        else:
            remaining_in_kg = remaining_in_order_unit
        
        # اگر در حال ویرایش هستیم، مقدار فعلی را به باقیمانده اضافه کن
        if self.pk:
            try:
                old_instance = RawMaterialInfo.objects.get(pk=self.pk)
                # مقدار قدیمی هم در کیلوگرم است
                remaining_in_kg += old_instance.allocated_quantity
            except RawMaterialInfo.DoesNotExist:
                pass
        
        if self.allocated_quantity > remaining_in_kg:
            raise ValidationError(
                f'مقدار تخصیص یافته ({self.allocated_quantity} کیلوگرم) نمی‌تواند بیشتر از مقدار باقیمانده ({remaining_in_kg} کیلوگرم) باشد.'
            )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

