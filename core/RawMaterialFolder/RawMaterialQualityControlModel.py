from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .QualityParameterModel import QualityParameter
from .RawMaterialModel import RawMaterial


class RawMaterialQualityControl(models.Model):
    """کنترل کیفیت - Quality Control"""
    
    raw_material = models.ForeignKey(
        RawMaterial,
        on_delete=models.CASCADE,
        related_name='quality_controls',
        verbose_name="ماده اولیه",
        null=True,
        blank=True
    )
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
        verbose_name = "مواد اولیه | کنترل کیفیت"
        verbose_name_plural = "مواد اولیه | کنترل کیفیت"

    def __str__(self):
        parameter_names = ", ".join([p.name for p in self.quality_parameters.all()[:3]])
        if self.quality_parameters.count() > 3:
            parameter_names += "..."
        return f"کنترل کیفیت - {parameter_names or 'بدون پارامتر'}"
