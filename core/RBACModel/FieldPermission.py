from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError


class ManagedField(models.Model):
    """
    فیلدهایی که در صفحه «مجوز دسترسی فیلد» می‌خواهیم روی آن‌ها قانون تعریف کنیم.
    این مدل تعیین می‌کند کدام فیلدها در جدول اصلی نمایش داده شوند.
    """
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name='نوع مدل'
    )
    field_name = models.CharField(
        max_length=100,
        verbose_name='نام فیلد'
    )
    field_label = models.CharField(
        max_length=150,
        verbose_name='برچسب فیلد',
        help_text='نام نمایشی فیلد در UI'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )

    class Meta:
        verbose_name = 'RBAC | فیلد قابل مدیریت'
        verbose_name_plural = 'فیلدهای قابل مدیریت'
        unique_together = ['content_type', 'field_name']
        ordering = ['content_type', 'field_name']

    def __str__(self):
        return f"{self.content_type.app_label}.{self.content_type.model}.{self.field_name}"


class FieldPermission(models.Model):
    """
    مدل مجوز دسترسی فیلد
    این مدل یک مجموعه از قوانین دسترسی به فیلدها را تعریف می‌کند.
    می‌تواند به یک نقش (Role) اختصاص داده شود تا آن نقش چندین مجوز فیلد داشته باشد.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='نام مجوز'
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='توضیحات'
    )
    
    role = models.ForeignKey(
        'Role',
        on_delete=models.CASCADE,
        related_name='field_permissions',
        null=True,
        blank=True,
        verbose_name='نقش'
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
        verbose_name = 'RBAC | مجوز دسترسی فیلد'
        verbose_name_plural = 'RBAC | مجوزهای دسترسی فیلد'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class FieldChoice(models.Model):
    """
    مدل انتخاب فیلد
    هر انتخاب مشخص می‌کند که دسترسی به یک فیلد خاص از یک مدل خاص مجاز است یا خیر
    """
    
    ACCESS_TYPE_CHOICES = [
        ('view', 'مشاهده'),
        ('edit', 'ویرایش'),
    ]
    
    field_permission = models.ForeignKey(
        FieldPermission,
        on_delete=models.CASCADE,
        related_name='field_choices',
        verbose_name='مجوز دسترسی فیلد'
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
    
    class Meta:
        verbose_name = 'RBAC | انتخاب فیلد'
        verbose_name_plural = 'RBAC | انتخاب‌های فیلد'
        unique_together = ['field_permission', 'content_type', 'field_name', 'access_type']
        ordering = ['content_type', 'field_name']
        indexes = [
            models.Index(fields=['field_permission', 'content_type']),
            models.Index(fields=['content_type', 'field_name']),
        ]
    
    def __str__(self):
        allowed_text = 'مجاز' if self.allowed else 'غیرمجاز'
        return f"{self.field_permission.name} - {self.content_type.model} - {self.field_name} - {self.get_access_type_display()} ({allowed_text})"
    
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

