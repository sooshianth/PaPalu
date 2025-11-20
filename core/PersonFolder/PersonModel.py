from django.db import models
from django_jalali.db import models as jmodels


class Person(models.Model):
    """مدل شخص"""

    TYPE_CHOICES = [
        ('customer', 'مشتری'),
        ('contact_person', 'تماس گیرنده'),
        ('supplier', 'تامین'),
        ('driver', 'راننده'),
        ('employee', 'کارمند'),
    ]

    NATURE_CHOICES = [
        ('legal', 'حقوقی'),
        ('natural', 'حقیقی'),
    ]

    USER_TYPE_CHOICES = [
        ('admin', 'مدیر'),
        ('user', 'کاربر'),
        ('guest', 'میهمان'),
    ]

    # فیلدهای پایه
    national_id = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name='کد ملی')
        
    type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        verbose_name='نوع شخص', 
        null=True, 
        blank=True)
        
    accounting_code = models.CharField(
        max_length=50,
        verbose_name='کد شخص (حسابدار ی)', 
        null=True, 
        blank=True)

    name = models.CharField(
        max_length=50, 
        verbose_name='نام شخص', 
        null=True, 
        blank=True)

    nature = models.CharField(
        max_length=10, 
        choices=NATURE_CHOICES, 
        verbose_name='نوع (حقوقی/حقیقی)', 
        null=True, 
        blank=True)

    registration_number = models.CharField(
        max_length=50, 
        verbose_name='شماره ثبت شرکت', 
        null=True, 
        blank=True)

    birth_date = jmodels.jDateField(
        verbose_name='تاریخ تولد شخص', 
        null=True, blank=True)

    user_type = models.CharField(
        max_length=20, 
        choices=USER_TYPE_CHOICES, 
        verbose_name='نوع کاربری شخص', 
        null=True, 
        blank=True)

    sales_expert = models.CharField(
        max_length=100, 
        verbose_name='کارشناس فروش', 
        null=True,
        blank=True)

    description = models.TextField(
        verbose_name='توضیحات شخص', 
        null=True, 
        blank=True)
    
    phone_number = models.CharField(
        max_length=20,
        verbose_name='شماره تلفن شخص',
        null=True,
        blank=True
    )
    
    # فیلد معرف
    introducer = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='معرف'
    )

    class Meta:
        verbose_name = 'شخص | اشخاص'
        verbose_name_plural = 'شخص | اشخاص'
        ordering = ['name']

    def __str__(self):
        return self.name or self.national_id or str(self.pk)