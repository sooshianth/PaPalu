from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


class FieldAccessRule(models.Model):
    """
    مدل کنترل دسترسی فیلدها
    این مدل مشخص می‌کند که هر کاربر چه دسترسی‌ای به فیلدهای مختلف مدل‌ها دارد
    """
    
    ACCESS_TYPE_CHOICES = [
        ('view', 'مشاهده'),
        ('edit', 'ویرایش'),
        ('delete', 'حذف'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='field_access_rules',
        verbose_name='کاربر'
    )
    
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name='نوع مدل',
        help_text='مدلی که می‌خواهید دسترسی فیلدش را کنترل کنید'
    )
    
    field_name = models.CharField(
        max_length=100,
        verbose_name='نام فیلد',
        help_text='نام دقیق فیلد در مدل (مثال: first_name, email, price)'
    )
    
    access_type = models.CharField(
        max_length=10,
        choices=ACCESS_TYPE_CHOICES,
        verbose_name='نوع دسترسی'
    )
    
    allowed = models.BooleanField(
        default=True,
        verbose_name='مجاز',
        help_text='آیا این دسترسی مجاز است؟'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاریخ به‌روزرسانی'
    )
    
    class Meta:
        verbose_name = 'قانون دسترسی فیلد'
        verbose_name_plural = 'قوانین دسترسی فیلدها'
        unique_together = ['user', 'content_type', 'field_name', 'access_type']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'content_type']),
            models.Index(fields=['content_type', 'field_name']),
        ]
    
    def __str__(self):
        allowed_text = 'مجاز' if self.allowed else 'غیرمجاز'
        return f"{self.user.username} - {self.content_type.model} - {self.field_name} - {self.get_access_type_display()} ({allowed_text})"
    
    def clean(self):
        """اعتبارسنجی برای مطمئن شدن از وجود فیلد در مدل"""
        super().clean()
        
        # بررسی اینکه آیا فیلد در مدل وجود دارد
        model_class = self.content_type.model_class()
        if model_class:
            field_names = [f.name for f in model_class._meta.get_fields()]
            if self.field_name not in field_names:
                raise ValidationError({
                    'field_name': f'فیلد "{self.field_name}" در مدل "{model_class.__name__}" وجود ندارد. فیلدهای موجود: {", ".join(field_names)}'
                })
    
    @staticmethod
    def has_field_access(user, model_instance, field_name, access_type='view'):
        """
        بررسی اینکه آیا کاربر به فیلد خاصی دسترسی دارد یا نه
        
        Args:
            user: شیء کاربر
            model_instance: نمونه‌ای از مدل که می‌خواهیم بررسی کنیم
            field_name: نام فیلد
            access_type: نوع دسترسی (view, edit, delete)
        
        Returns:
            True اگر کاربر دسترسی دارد، در غیر این صورت False
        """
        if user.is_superuser:
            return True
        
        content_type = ContentType.objects.get_for_model(model_instance)
        
        # بررسی وجود قانون دسترسی
        rule = FieldAccessRule.objects.filter(
            user=user,
            content_type=content_type,
            field_name=field_name,
            access_type=access_type
        ).first()
        
        # اگر قانونی تعریف نشده، به طور پیش‌فرض دسترسی داده می‌شود
        if rule is None:
            return True
        
        return rule.allowed
    
    @staticmethod
    def get_accessible_fields(user, model_class, access_type='view'):
        """
        لیست فیلدهایی که کاربر به آن‌ها دسترسی دارد را برمی‌گرداند
        
        Args:
            user: شیء کاربر
            model_class: کلاس مدل
            access_type: نوع دسترسی (view, edit, delete)
        
        Returns:
            لیست نام فیلدها
        """
        if user.is_superuser:
            return [f.name for f in model_class._meta.get_fields()]
        
        content_type = ContentType.objects.get_for_model(model_class)
        
        # گرفتن همه فیلدها
        all_fields = [f.name for f in model_class._meta.get_fields()]
        
        # گرفتن قوانین دسترسی
        rules = FieldAccessRule.objects.filter(
            user=user,
            content_type=content_type,
            access_type=access_type
        )
        
        # فیلدهایی که قانون برایشان تعریف نشده، به طور پیش‌فرض قابل دسترسی هستند
        denied_fields = [rule.field_name for rule in rules if not rule.allowed]
        
        return [field for field in all_fields if field not in denied_fields]

