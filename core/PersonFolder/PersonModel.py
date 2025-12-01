from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.utils.translation import gettext_lazy as _
from core.WarehouseFolder.WarehouseModel import Warehouse


FIELD_OF_ACTIVITY = [
    ('chicken', 'مرغدار'),
    ('livestock', 'دامدار'),
    ('factory', 'کارخانه خوراک'),
    ('fish', 'پرورش آبزیان'),
    ('corporation', 'تعاونی'),
    ('association', 'اتحادیه'),
    ('dealer', 'دلال'),
    ('aggressive', 'مزاحم'),
    ('other', 'سایر')
]


class ActivityField(models.Model):
    """مدل حیطه فعالیت"""
    
    code = models.CharField(
        max_length=50,
        choices=FIELD_OF_ACTIVITY,
        unique=True,
        verbose_name='کد'
    )
    
    class Meta:
        verbose_name = _("حیطه فعالیت")
        verbose_name_plural = _("حیطه های فعالیت")
        ordering = ['code']
    
    def __str__(self):
        return dict(FIELD_OF_ACTIVITY).get(self.code, self.code)


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


    # فیلدهای پایه
    national_id = models.CharField(
        max_length=10,
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

    activity_fields = models.ManyToManyField(
        ActivityField,
        blank=True,
        related_name='persons',
        verbose_name='حیطه‌های فعالیت'
    )

    sales_expert = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='persons',
        verbose_name='کارشناس فروش'
    )

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
    
    # انبار (برای مشتریان، نوع انبار باید consumer باشد)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='persons',
        verbose_name='انبار',
        help_text='برای مشتریان، نوع انبار باید مصرف‌کننده باشد'
    )
    
    # فیلد وضعیت (فعال/غیرفعال)
    is_active = models.BooleanField(
        default=True,
        verbose_name='وضعیت',
        help_text='آیا مشتری فعال است؟'
    )

    class Meta:
        verbose_name = 'شخص | اشخاص'
        verbose_name_plural = 'شخص | اشخاص'
        ordering = ['name']

    def __str__(self):
        return self.name or self.national_id or str(self.pk)