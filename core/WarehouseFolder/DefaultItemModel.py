from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class DefaultItem(models.Model):
    """
    مدل آیتم پیشفرض
    می‌تواند یک محصول یا ماده اولیه باشد
    """
    
    ITEM_TYPE_CHOICES = [
        ('product', 'محصول'),
        ('raw_material', 'ماده اولیه'),
    ]
    
    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES,
        verbose_name='نوع آیتم',
        null=True,
        blank=True
    )
    
    # GenericForeignKey برای پشتیبانی از محصول یا ماده اولیه
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={'model__in': ('product', 'rawmaterial')},
        verbose_name='نوع محتوا'
    )
    
    object_id = models.PositiveIntegerField(
        verbose_name='شناسه آبجکت'
    )
    
    content_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'انبار | آیتم پیشفرض'
        verbose_name_plural = 'انبار | آیتم‌های پیشفرض'
        ordering = ['-created_at']
        # جلوگیری از ایجاد آیتم تکراری برای یک محصول/ماده اولیه
        unique_together = [['content_type', 'object_id']]
    
    def __str__(self):
        if self.content_object:
            return f"{self.get_item_type_display()}: {self.content_object}"
        return f"آیتم پیشفرض {self.id}"
    
    def get_item_name(self):
        """بازگشت نام آیتم"""
        if self.content_object:
            if hasattr(self.content_object, 'product_name'):
                return self.content_object.product_name
            elif hasattr(self.content_object, 'raw_material_name'):
                return self.content_object.raw_material_name
        return None
    
    def get_item_field(self, field_name, default=None):
        """
        بازگشت مقدار یک فیلد از آیتم
        استفاده: warehouse.default_item.get_item_field('expiry_date')
        """
        if self.content_object and hasattr(self.content_object, field_name):
            return getattr(self.content_object, field_name)
        return default
    
    def is_product(self):
        """بررسی اینکه آیتم یک محصول است"""
        return self.item_type == 'product'
    
    def is_raw_material(self):
        """بررسی اینکه آیتم یک ماده اولیه است"""
        return self.item_type == 'raw_material'
