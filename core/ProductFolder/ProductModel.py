from django.db import models
from django_jalali.db import models as jmodels


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
        #TODO
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
    
    physical_shape = models.ForeignKey(
        PhysicalShape,
        on_delete=models.SET_NULL,
        verbose_name='شکل فیزیکی',
        related_name='products',
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
        verbose_name='ضریب تبدیل اصلی به فرعی'
    )
    
    expiration_date = jmodels.jDateField(
        blank=True,
        null=True,
        verbose_name='تاریخ انقضا'
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
        upload_to='products/',
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

