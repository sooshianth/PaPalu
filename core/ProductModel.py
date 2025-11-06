from django.db import models
from django_jalali.db import models as jmodels


class Product(models.Model):
    """
    مدل اصلی محصول - اطلاعات پایه
    """
    
    PHYSICAL_SHAPE_CHOICES = [
        ('mesh', 'مش'),
        ('pellet', 'پلت'),
        ('granule', 'گرانول'),
        ('achil', 'آچیل'),
    ]
    
    # اطلاعات پایه
    name = models.CharField(
        max_length=255,
        verbose_name='نام محصول'
    )
    
    code = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='کد محصول'
    )
    
    category = models.CharField(
        max_length=255,
        verbose_name='گروه محصول'
    )
    
    subcategory = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='زیر گروه محصول'
    )
    
    physical_shape = models.CharField(
        max_length=20,
        choices=PHYSICAL_SHAPE_CHOICES,
        verbose_name='شکل فیزیکی'
    )
    
    pellet_granule_diameter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='قطر پلت یا گرانول'
    )
    
    invoice_description = models.TextField(
        verbose_name='شرح محصول برای پیش فاکتور'
    )
    
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        verbose_name='تصویر محصول'
    )
    
    full_description = models.TextField(
        verbose_name='شرح کامل محصول'
    )
    
    lab_analysis = models.TextField(
        verbose_name='آنالیز آزمایشگاهی محصول'
    )
    
    original_selection = models.TextField(
        verbose_name='گزیده اصلی(مثلا: موردی روز 1 تا 10 مقدار ماده اولیه)'
    )
    
    is_custom = models.BooleanField(
        default=False,
        verbose_name='محصول سفارشی است؟'
    )
    
    main_unit = models.CharField(
        max_length=50,
        verbose_name='واحد شمارش اصلی'
    )
    
    secondary_unit = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='واحد شمارش فرعی'
    )
    
    conversion_coefficient = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='ضریب تبدیل اصلی به فرعی'
    )
    
    expiration_date = jmodels.jDateField(
        blank=True,
        null=True,
        verbose_name='تاریخ انقضا'
    )
    
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ آخرین ویرایش'
    )
    
    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class ProductionInfo(models.Model):
    """
    اطلاعات تولید محصول
    """
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='production_info',
        verbose_name='محصول'
    )
    
    formula_id = models.CharField(
        max_length=100,
        verbose_name='شناسه فرمول'
    )
    
    production_time = models.DurationField(
        verbose_name='زمان تولید'
    )
    
    min_batch_production = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل پچ تولید'
    )
    
    raw_material_conversion_guarantee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='ضمنت تبدیل مواد اولیه به محصول'
    )
    
    specific_production_instruction = models.TextField(
        verbose_name='دستور العمل خاص تولید'
    )
    
    sampling_instruction = models.TextField(
        verbose_name='دستور العمل نمونه‌برداری'
    )
    
    pre_consumption_preparation_instruction = models.TextField(
        verbose_name='دستورالعمل آماده‌سازی قبل از مصرف'
    )
    
    natural_waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد ضایعات طبیعی'
    )
    
    natural_loss_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد افت طبیعی'
    )
    
    msds = models.TextField(
        verbose_name='خطرات ایمنی (MSDS)'
    )
    
    production_checklists = models.TextField(
        verbose_name='چک‌لیست‌های ممکن در تولید'
    )
    
    class Meta:
        verbose_name = 'اطلاعات تولید'
        verbose_name_plural = 'اطلاعات تولید'
    
    def __str__(self):
        return f"اطلاعات تولید - {self.product.name}"


class BOM(models.Model):
    """
    شناسه ماده اولیه (Bill of Materials)
    """
    
    production_info = models.ForeignKey(
        ProductionInfo,
        on_delete=models.CASCADE,
        related_name='bom_items',
        verbose_name='اطلاعات تولید'
    )
    
    raw_material = models.CharField(
        max_length=255,
        verbose_name='ماده اولیه (ها)'
    )
    
    unit_used = models.CharField(
        max_length=50,
        verbose_name='واحد به کار رفته (ها)'
    )
    
    original_selection = models.TextField(
        verbose_name='گزیده اصلی(مثلا: موردی روز 1 تا 10 مقدار ماده اولیه)'
    )
    
    class Meta:
        verbose_name = 'ماده اولیه'
        verbose_name_plural = 'مواد اولیه (BOM)'
    
    def __str__(self):
        return f"{self.raw_material} - {self.production_info.product.name}"


class QualityControl(models.Model):
    """
    کنترل کیفیت محصول - پارامترهای کلیدی استاندارد
    """
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='quality_control',
        verbose_name='محصول'
    )
    
    requires_post_production_test = models.BooleanField(
        default=False,
        verbose_name='نیاز به آزمایش بعد تولید؟'
    )
    
    standard_key_parameters = models.TextField(
        verbose_name='پارامترهای کلیدی استاندارد هر پالاستر'
    )
    
    upper_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='حد مجاز بالا برای پالاستر'
    )
    
    lower_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='حد پایین مجاز برای پالاستر'
    )
    
    moisture_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='میزان رطوبت'
    )
    
    density = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        blank=True,
        null=True,
        verbose_name='چگالی (Density)'
    )
    
    ash_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='درصد خاکستر'
    )
    
    metabolizable_energy = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='انرژی قابل متابولیسم (ME)'
    )
    
    fat = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='چربی'
    )
    
    protein = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='پروتئین'
    )
    
    physical_pre_size = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='اندازه پیش فیزیکی'
    )
    
    storage_conditions = models.TextField(
        verbose_name='شرایط نگهداری'
    )
    
    storage_temperature = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='دما دیگر/ذخیره'
    )
    
    light_sensitive = models.BooleanField(
        default=False,
        verbose_name='حساسیت به نور؟'
    )
    
    class Meta:
        verbose_name = 'کنترل کیفیت'
        verbose_name_plural = 'کنترل کیفیت'
    
    def __str__(self):
        return f"کنترل کیفیت - {self.product.name}"


class ProductSales(models.Model):
    """
    اطلاعات فروش محصول
    """
    
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='sales_info',
        verbose_name='محصول'
    )
    
    min_sales_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل مقدار سفارش'
    )
    
    price_with_tax = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='درصد مالیات بر ارزش افزوده'
    )
    
    accountings = models.CharField(
        max_length=255,
        verbose_name='کد حسابداری‌ها'
    )
    
    related_bank_account = models.CharField(
        max_length=255,
        verbose_name='کد مالیاتی ماده'
    )
    
    inventory_existence = models.BooleanField(
        default=True,
        verbose_name='حداقل موجودی انبار'
    )
    
    reorder_point_production = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='نقطه سفارش مجدد'
    )
    
    new_production_point = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='نقطه سفارش تولید'
    )
    
    class Meta:
        verbose_name = 'اطلاعات فروش'
        verbose_name_plural = 'اطلاعات فروش'
    
    def __str__(self):
        return f"اطلاعات فروش - {self.product.name}"

