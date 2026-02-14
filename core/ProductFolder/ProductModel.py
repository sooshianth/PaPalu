from django.db import models
from django_jalali.db import models as jmodels
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.file_upload_utils import safe_media_upload_to_flat


class PhysicalShape(models.Model):
    """
    کلاس شکل فیزیکی محصول تا توسط ادمین مدیریت شود
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='نام شکل فیزیکی'
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='توضیحات شکل فیزیکی'
    )

    class Meta:
        verbose_name = 'محصول | شکل فیزیکی'
        verbose_name_plural = 'محصول | اشکال فیزیکی'

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    مدل اصلی محصول - اطلاعات پایه
    """
    
    PRODUCT_APPLICATION_CHOICES = [
        ('chicken_layer', 'مرغ تخم‌گذار'),
        ('chicken_broiler', 'مرغ گوشتی'),
        ('cow_dairy', 'گاو شیری'),
        ('cow_beef', 'گاو گوشتی'),
        ('sheep_dairy', 'گوسفند شیری'),
        ('sheep_meat', 'گوسفند گوشتی'),
        ('3 year khar', 'خر ۳ ساله'),
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
    
    grade = models.CharField(
        max_length=255,
        verbose_name='گرید',
        null=True,
        blank=True
    )
    
    physical_shape = models.CharField(
        max_length=100,
        verbose_name='شکل فیزیکی',
        null=True,
        blank=True
    )
    
    main_application = models.CharField(
        max_length=255,
        verbose_name='کاربرد اصلی',
        choices=PRODUCT_APPLICATION_CHOICES,
        null=True,
        blank=True  
    )
    
    is_custom = models.BooleanField(
        default=False,
        verbose_name='محصول سفارشی است؟',
        null=True,
        blank=True
    )
    
    full_description = models.TextField(
        verbose_name='شرح کامل محصول',
        null=True,
        blank=True
    )
    
    main_unit = models.CharField(
        max_length=50,
        verbose_name='واحد شمارش اصلی',
        null=True,
        blank=True
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
        verbose_name='ضریب تبدیل فرعی به اصلی',
        help_text='مثال: 1 گرم = 0.001 کیلوگرم → ضریب 0.001؛ مقدار اصلی = مقدار فرعی × ضریب'
    )
    
    expiration_date = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='مدت اعتبار',
        help_text='مثال: 2 سال، 6 ماه، 18 ماه'
    )
    
    # فیلدهای اختیاری
    pellet_granule_diameter = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='قطر پلت یا گرانول'
    )
    
    image = models.ImageField(
        upload_to=safe_media_upload_to_flat('products'),
        blank=True,
        null=True,
        verbose_name='تصویر محصول'
    )
    
    lab_analysis = models.TextField(
        verbose_name='آنالیز آزمایشگاهی محصول',
        null=True,
        blank=True
    )
    
    invoice_description = models.TextField(
        verbose_name='شرح محصول برای پیش فاکتور',
        null=True,
        blank=True
    )
    
    # فیلدهای فروش و مالی
    min_sales_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل مقدار سفارش (کیلوگرم)',
        blank=True,
        null=True,
    )
    
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد مالیات بر ارزش افزوده',
        blank=True,
        null=True,
    )
    
    reserve_deposit = models.CharField(
        max_length=255,
        verbose_name='احتیاطی سپرده مربوط',
        blank=True,
        null=True,
    )
    
    tax_code = models.CharField(
        max_length=255,
        verbose_name='کد مالیاتی ماده',
        blank=True,
        null=True,
    )
    
    accounting_code = models.CharField(
        max_length=255,
        verbose_name='کد حسابداری',
        blank=True,
        null=True,
    )
    
    min_inventory = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='حداقل موجودی انبار (کیلوگرم)',
        blank=True,
        null=True,
    )
    
    production_order_point = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name='نقطه سفارش تولید (کیلوگرم)'
    )
    
    transport_conditions = models.TextField(
        verbose_name='شرایط حمل',
        blank=True,
        null=True,
    )
    
    default_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='انبار پیش فرض',
        related_name='products',
        help_text='انبار پیش‌فرض برای ذخیره این محصول'
    )
    
    storage_conditions = models.TextField(
        verbose_name='شرایط نگهداری',
        blank=True,
        null=True,
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
        verbose_name = 'محصول | محصولات'
        verbose_name_plural = 'محصول | محصولات'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.name}"
