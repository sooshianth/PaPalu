from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from ..PersonFolder.PersonModel import Person
from django_jalali.db import models as jmodels
from core.file_upload_utils import safe_media_upload_to


class RawMaterial(models.Model):
    """مواد اولیه - Raw Materials"""
    
    PHYSICAL_FORM_CHOICES = [
        ('solid', 'جامد'),
        ('liquid', 'مایع'),
        ('powder', 'پودر'),
        ('granular', 'دانه‌ای'),
        ('paste', 'خمیری'),
        ('gas', 'گاز'),
        ('other', 'سایر'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
    ]
    
    UNIT_CHOICES = [
        ('gr', 'گرم'),
        ('kg', 'کیلوگرم'),
        ('ton', 'تن'),
        ('m3', 'متر مکعب'),
        ('ltr', 'لیتر'),
        ('cc', 'میلی لیتر'),
    ]
    
    # اطلاعات پایه - Basic Information (placed directly in main model)
    raw_material_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="شناسه ماده اولیه",
        db_index=True,
        null=True,
        blank=True
    )
    name = models.CharField(
        max_length=255,
        verbose_name="نام ماده اولیه",
        null=True,
        blank=True
    )
    technical_description = models.TextField(
        verbose_name="توضیحات و مشخصات فنی",
        null=True,
        blank=True
    )
    physical_form = models.CharField(
        max_length=50,
        choices=PHYSICAL_FORM_CHOICES,
        verbose_name="شکل فیزیکی",
        default='solid',
        null=True,
        blank=True
    )
    primary_unit = models.CharField(
        max_length=3,
        choices=UNIT_CHOICES,
        verbose_name='واحد اصلی',
        null=True,
        blank=True
    )
    secondary_unit = models.CharField(
        max_length=3,
        choices=UNIT_CHOICES,
        verbose_name='واحد فرعی',
        null=True,
        blank=True
    )
    conversion_factor = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        verbose_name="ضریب تبدیل واحد اصلی به فرعی (دیفالت)",
        default=1,
        help_text="مثال: 1 کیلوگرم = 1000 گرم",
        null=True,
        blank=True
    )
    hs_code = models.CharField(
        max_length=50,
        verbose_name="HS Code",
        null=True,
        blank=True,
        help_text="کد هماهنگ تعرفه گمرکی"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="وضعیت فعال یا غیرفعال بودن ماده اولیه",
        null=True,
        blank=True
    )
    attachments = models.FileField(
        upload_to=safe_media_upload_to('raw_materials/attachments'),
        verbose_name="پیوست‌ها",
        null=True,
        blank=True
    )
    main_supplier = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='main_supplied_materials',
        verbose_name='تامین‌کننده اصلی این کالا',
        help_text='فقط اشخاص با نوع "تامین" قابل انتخاب هستند.'
    )
    veterinary_health_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="شناسه یکتا در سیستم دامپزشکی/بهداشت",
        null=True,
        blank=True,
        db_index=True
    )
    standard_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="درصد افت استاندارد",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    # تاریخ انقضا به صورت کاراکتری (درخواست کاربر: CharField نه تاریخ واقعی)
    expiration_date = models.CharField(
        max_length=50,
        verbose_name="تاریخ انقضا",
        null=True,
        blank=True,
        help_text="مثال: 1404/12 یا Q4-1404 یا فرمت دلخواه"
    )
    
    # Timestamps
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="تاریخ آخرین بروزرسانی"
    )

    class Meta:
        verbose_name = "مواد اولیه | مواد اولیه"
        verbose_name_plural = "مواد اولیه | مواد اولیه"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['raw_material_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def save(self, *args, **kwargs):
        """Auto-generate raw_material_id if not provided"""
        if not self.raw_material_id:
            # Generate unique ID with format: RM-YYYY-NNNN
            from django.utils import timezone
            year = timezone.now().year
            
            # Find the last material for this year
            last_material = RawMaterial.objects.filter(
                raw_material_id__startswith=f'RM-{year}-'
            ).order_by('-raw_material_id').first()
            
            if last_material and last_material.raw_material_id:
                try:
                    # Extract the number part and increment
                    last_num = int(last_material.raw_material_id.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            
            self.raw_material_id = f'RM-{year}-{new_num:04d}'
        
        super().save(*args, **kwargs)

    def __str__(self):
        raw_id = self.raw_material_id or "No ID"
        name = self.name or "No Name"
        return f"{raw_id} - {name}"
