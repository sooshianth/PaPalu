from django.db import models
from django.core.exceptions import ValidationError
from django_jalali.db import models as jmodels


class CompanyInfo(models.Model):
    """
    مدل اطلاعات شرکت تامین نهاده سیمرغ
    این مدل به صورت Singleton است (فقط یک رکورد)
    """
    
    name = models.CharField(
        max_length=255,
        verbose_name='نام شرکت',
        default='تامین نهاده سیمرغ'
    )
    
    national_id = models.CharField(
        max_length=11,
        verbose_name='شماره ملی',
        null=True,
        blank=True,
        help_text='شماره ملی شرکت (11 رقم)'
    )
    
    registration_number = models.CharField(
        max_length=50,
        verbose_name='شماره ثبت',
        null=True,
        blank=True,
        help_text='شماره ثبت شرکت'
    )
    
    economic_code = models.CharField(
        max_length=50,
        verbose_name='کد اقتصادی',
        null=True,
        blank=True,
        help_text='کد اقتصادی شرکت'
    )
    
    address = models.TextField(
        verbose_name='آدرس',
        null=True,
        blank=True,
        help_text='آدرس کامل شرکت'
    )
    
    postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی',
        null=True,
        blank=True,
        help_text='کد پستی شرکت'
    )
    
    phone_number = models.CharField(
        max_length=20,
        verbose_name='شماره تلفن',
        null=True,
        blank=True,
        help_text='شماره تلفن اصلی شرکت'
    )
    
    fax_number = models.CharField(
        max_length=20,
        verbose_name='شماره فکس',
        null=True,
        blank=True,
        help_text='شماره فکس شرکت'
    )
    
    email = models.EmailField(
        verbose_name='ایمیل',
        null=True,
        blank=True,
        help_text='ایمیل شرکت'
    )
    
    website = models.URLField(
        verbose_name='وب‌سایت',
        null=True,
        blank=True,
        help_text='آدرس وب‌سایت شرکت'
    )
    
    tax_province = models.CharField(
        max_length=100,
        verbose_name='استان مالیاتی',
        null=True,
        blank=True,
        help_text='استان محل ثبت مالیاتی'
    )
    
    tax_city = models.CharField(
        max_length=100,
        verbose_name='شهر مالیاتی',
        null=True,
        blank=True,
        help_text='شهر محل ثبت مالیاتی'
    )
    
    tax_address = models.TextField(
        verbose_name='آدرس مالیاتی',
        null=True,
        blank=True,
        help_text='آدرس محل ثبت مالیاتی'
    )
    
    tax_postal_code = models.CharField(
        max_length=10,
        verbose_name='کد پستی مالیاتی',
        null=True,
        blank=True,
        help_text='کد پستی محل ثبت مالیاتی'
    )
    
    proforma_notes = models.TextField(
        verbose_name='ملاحظات پیش فاکتور',
        null=True,
        blank=True,
        help_text='ملاحظات پیش‌فرض که در فرم صدور پیش فاکتور نمایش داده می‌شود'
    )
    
    invoice_notes = models.TextField(
        verbose_name='ملاحظات فاکتور',
        null=True,
        blank=True,
        help_text='ملاحظات پیش‌فرض که در فرم صدور فاکتور نمایش داده می‌شود'
    )
    
    # Timestamps
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ به‌روزرسانی',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Settings | اطلاعات شرکت'
        verbose_name_plural = 'Settings | اطلاعات شرکت'
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """اعتبارسنجی: فقط یک رکورد باید وجود داشته باشد"""
        if not self.pk:
            # اگر رکورد جدید است، بررسی کن که آیا رکورد دیگری وجود دارد
            if CompanyInfo.objects.exists():
                raise ValidationError('فقط یک رکورد اطلاعات شرکت می‌تواند وجود داشته باشد. لطفاً رکورد موجود را ویرایش کنید.')
        super().clean()
    
    def save(self, *args, **kwargs):
        """ذخیره با اعتبارسنجی singleton"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_company_info(cls):
        """
        دریافت اطلاعات شرکت (singleton)
        اگر رکوردی وجود نداشته باشد، یک رکورد پیش‌فرض ایجاد می‌کند
        """
        company_info, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'name': 'تامین نهاده سیمرغ'
            }
        )
        return company_info

