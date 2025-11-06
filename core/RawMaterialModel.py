from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django_jalali.db import models as jmodels


class Supplier(models.Model):
    """تامین‌کننده - Supplier"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="نام تامین‌کننده"
    )
    
    class Meta:
        verbose_name = "تامین‌کننده"
        verbose_name_plural = "تامین‌کنندگان"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class QualityParameter(models.Model):
    """پارامتر کیفیت - Quality Parameter"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="نام پارامتر"
    )
    
    class Meta:
        verbose_name = "پارامتر کیفیت"
        verbose_name_plural = "پارامترهای کیفیت"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class RawMaterialPurchaseInfo(models.Model):
    """اطلاعات خرید - Purchase Information"""
    
    suppliers = models.ManyToManyField(
        Supplier,
        related_name='purchase_infos',
        verbose_name="تامین‌کنندگان",
        blank=True
    )
    minimum_order_quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حداقل مقدار سفارش",
        null=True,
        blank=True
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="درصد مالیات بر ارزش افزوده",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    accounting_code = models.CharField(
        max_length=100,
        verbose_name="کد حسابداری مرتبط",
        null=True,
        blank=True
    )
    tax_code = models.CharField(
        max_length=100,
        verbose_name="کد مالیاتی ماده",
        null=True,
        blank=True
    )
    safety_stock_level = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حد موجودی اطمینان",
        null=True,
        blank=True
    )
    reorder_point = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="نقطه سفارش مجدد",
        null=True,
        blank=True
    )
    default_warehouse = models.TextField(
        verbose_name="انبار پیش‌فرض نگهداری",
        null=True,
        blank=True
    )
    transportation_conditions = models.TextField(
        verbose_name="شرایط حمل",
        null=True,
        blank=True
    )
    storage_conditions = models.TextField(
        verbose_name="شرایط نگهداری",
        null=True,
        blank=True
    )
    notes = models.TextField(
        verbose_name="توضیحات",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "اطلاعات خرید"
        verbose_name_plural = "اطلاعات خرید"

    def __str__(self):
        supplier_names = ", ".join([s.name for s in self.suppliers.all()[:3]])
        if self.suppliers.count() > 3:
            supplier_names += "..."
        return f"اطلاعات خرید - {supplier_names or 'بدون تامین‌کننده'}"


class RawMaterialQualityControl(models.Model):
    """کنترل کیفیت - Quality Control"""
    
    requires_sampling = models.BooleanField(
        default=False,
        verbose_name="نیاز به نمونه‌برداری",
        null=True,
        blank=True
    )
    quality_parameters = models.ManyToManyField(
        QualityParameter,
        related_name='quality_controls',
        verbose_name="پارامترهای کیفیت",
        blank=True
    )
    upper_limit = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حد بالای مجاز برای پارامتر",
        null=True,
        blank=True
    )
    lower_limit = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="حد پایین مجاز برای پارامتر",
        null=True,
        blank=True
    )
    moisture_content = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="میزان رطوبت",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    density = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="چگالی (Density)",
        null=True,
        blank=True
    )
    ash_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="درصد خاکستر",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    metabolizable_energy = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="انرژی قابل متابولیسم (ME)",
        null=True,
        blank=True
    )
    fat_content = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="چربی",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    protein_content = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="پروتئین",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    evaporation_melting_temperature = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="دما تبخیر/ذوب",
        null=True,
        blank=True
    )
    light_sensitive = models.BooleanField(
        default=False,
        verbose_name="حساس به نور؟",
        null=True,
        blank=True
    )
    sampling_instructions = models.TextField(
        verbose_name="دستورالعمل نمونه‌برداری",
        null=True,
        blank=True
    )
    preparation_instructions = models.TextField(
        verbose_name="دستورالعمل آماده‌سازی قبل از مصرف",
        null=True,
        blank=True
    )
    natural_waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="درصد ضایعات طبیعی",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    natural_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="درصد افت طبیعی",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    safety_hazards_msds = models.TextField(
        verbose_name="خطرات ایمنی (MSDS)",
        null=True,
        blank=True
    )
    possible_substitutes = models.TextField(
        verbose_name="جایگزین‌های ممکن در تولید",
        null=True,
        blank=True
    )
    storage_conditions = models.TextField(
        verbose_name="شرایط نگهداری",
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "کنترل کیفیت"
        verbose_name_plural = "کنترل کیفیت"

    def __str__(self):
        parameter_names = ", ".join([p.name for p in self.quality_parameters.all()[:3]])
        if self.quality_parameters.count() > 3:
            parameter_names += "..."
        return f"کنترل کیفیت - {parameter_names or 'بدون پارامتر'}"


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
    
    # اطلاعات پایه - Basic Information (placed directly in main model)
    raw_material_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="شناسه ماده اولیه",
        db_index=True
    )
    name = models.CharField(
        max_length=255,
        verbose_name="نام ماده اولیه"
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
        default='solid'
    )
    primary_unit = models.CharField(
        max_length=50,
        verbose_name="واحد شمارش اصلی (مبنای خرید)",
        help_text="مثال: کیلوگرم، لیتر، تن"
    )
    secondary_unit = models.CharField(
        max_length=50,
        verbose_name="واحد شمارش فرعی (مبنای سنجش انبار)",
        null=True,
        blank=True,
        help_text="مثال: گرم، میلی‌لیتر"
    )
    conversion_factor = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        verbose_name="ضریب تبدیل واحد اصلی به فرعی (دیفالت)",
        default=1.0,
        help_text="مثال: 1 کیلوگرم = 1000 گرم"
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
        verbose_name="وضعیت فعال یا غیرفعال بودن ماده اولیه"
    )
    attachments = models.FileField(
        upload_to='raw_materials/attachments/%Y/%m/',
        verbose_name="پیوست‌ها",
        null=True,
        blank=True
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
    expiration_date = jmodels.jDateField(
        verbose_name="تاریخ انقضا",
        null=True,
        blank=True
    )
    
    # ForeignKey relationships to subclass models
    purchase_info = models.ForeignKey(
        RawMaterialPurchaseInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_materials',
        verbose_name="اطلاعات خرید"
    )
    quality_control = models.ForeignKey(
        RawMaterialQualityControl,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_materials',
        verbose_name="کنترل کیفیت"
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
        verbose_name = "ماده اولیه"
        verbose_name_plural = "مواد اولیه"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['raw_material_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.raw_material_id} - {self.name}"

