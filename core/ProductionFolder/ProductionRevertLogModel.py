from django.db import models
from django_jalali.db import models as jmodels
from .ProductionProgramModel import ProductionProgram


class ProductionRevertLog(models.Model):
    """
    لاگ برگشت، رد یا آرشیو برنامه‌های تولید
    """
    
    ACTION_CHOICES = [
        ('denied', 'رد شده'),
        ('reverted', 'برگشت به تایید شده'),
        ('archived', 'آرشیو شده'),
    ]
    
    production_program = models.ForeignKey(
        ProductionProgram,
        on_delete=models.CASCADE,
        related_name='revert_logs',
        verbose_name='برنامه تولید'
    )
    
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        verbose_name='نوع عملیات'
    )
    
    reason = models.TextField(
        verbose_name='دلیل',
        blank=True,
        null=True,
        help_text='دلیل رد، برگشت یا آرشیو'
    )
    
    created_by = models.CharField(
        max_length=100,
        verbose_name='ایجاد شده توسط',
        blank=True,
        null=True
    )
    
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    # برای revert: ذخیره ID ثبت انبار معکوس
    reversal_stock_entry_id = models.IntegerField(
        verbose_name='شناسه ثبت انبار معکوس',
        blank=True,
        null=True,
        help_text='برای عملیات برگشت از in progress'
    )
    
    class Meta:
        verbose_name = 'تولید | لاگ برگشت/رد/آرشیو'
        verbose_name_plural = 'تولید | لاگ‌های برگشت/رد/آرشیو'
        ordering = ['-created_at']
    
    def __str__(self):
        program_id = self.production_program.program_id or self.production_program.id
        action_display = self.get_action_type_display()
        return f"{program_id} - {action_display} ({self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else ''})"
