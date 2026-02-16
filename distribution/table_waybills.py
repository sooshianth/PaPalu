import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from core.helpers import check_field_access_prefer_edit
from core.PersonFolder.PersonModel import Person
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from distribution.plate_display import render_iran_plate_html


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


class WaybillTable(tables.Table):
    """جدول لیست حمل‌های در انتظار بارنامه با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        # دریافت اطلاعات دسترسی فیلدها
        self.accessible_fields = kwargs.pop('accessible_fields', None)
        self.user = kwargs.pop('user', None)
        
        super().__init__(*args, **kwargs)
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and self.user is not None:
            self.accessible_fields = self._get_accessible_fields(self.user)
        
        # فیلتر کردن ستون‌ها بر اساس دسترسی
        if self.accessible_fields:
            self._filter_columns_by_access()
    
    def _get_accessible_fields(self, user):
        """محاسبه فیلدهای قابل دسترسی برای کاربر"""
        from core.PersonFolder.PersonModel import Person as PersonModel
        from core.TransportFolder.TruckInfoModel import TruckInfo as TruckInfoModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'allocation_number': True,
                'vehicle_entry_time': True,
                'empty_weight': True,
                'gross_weight': True,
                'driver_name': True,
                'driver_mobile': True,
                'plate_number': True,
                'driver_national_id': True,
                'carrier_name': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': None,  # همیشه نمایش داده می‌شود
            'allocation_number': None,  # همیشه نمایش داده می‌شود
            'vehicle_entry_time': None,  # همیشه نمایش داده می‌شود
            'empty_weight': None,  # همیشه نمایش داده می‌شود
            'gross_weight': None,  # همیشه نمایش داده می‌شود
            'driver_name': (PersonModel, 'name'),
            'driver_mobile': None,  # همیشه نمایش داده می‌شود
            'plate_number': (TruckInfoModel, 'plate_number'),
            'driver_national_id': (PersonModel, 'national_id'),
            'carrier_name': None,  # همیشه نمایش داده می‌شود
            'actions': None,  # عملیات همیشه نمایش داده می‌شود
        }
        
        accessible_fields = {}
        for display_name, mapping in field_mapping.items():
            if mapping is None:
                # فیلدهایی که نیازی به بررسی دسترسی ندارند
                accessible_fields[display_name] = True
            else:
                model_class, model_field_name = mapping
                accessible_fields[display_name] = check_field_access_prefer_edit(
                    user,
                    model_class,
                    model_field_name,
                )
        
        return accessible_fields
    
    def _filter_columns_by_access(self):
        """فیلتر کردن ستون‌ها بر اساس دسترسی کاربر"""
        if not self.accessible_fields:
            return
        
        # تعیین ستون‌هایی که باید حذف شوند
        columns_to_exclude = []
        for column_name in list(self.columns.columns.keys()):
            if column_name in self.accessible_fields:
                if not self.accessible_fields[column_name]:
                    columns_to_exclude.append(column_name)
        
        # حذف ستون‌ها از columns
        for column_name in columns_to_exclude:
            if column_name in self.columns.columns:
                del self.columns.columns[column_name]
        
        # به‌روزرسانی Meta برای exclude کردن ستون‌ها
        if columns_to_exclude:
            # استفاده از exclude در Meta
            if not hasattr(self._meta, 'exclude') or self._meta.exclude is None:
                self._meta.exclude = tuple(columns_to_exclude)
            else:
                # ترکیب exclude موجود با ستون‌های جدید
                existing_exclude = set(self._meta.exclude) if self._meta.exclude else set()
                existing_exclude.update(columns_to_exclude)
                self._meta.exclude = tuple(existing_exclude)
            
            # به‌روزرسانی fields و sequence
            if hasattr(self._meta, 'fields') and self._meta.fields:
                self._meta.fields = tuple(
                    field for field in self._meta.fields 
                    if field not in columns_to_exclude
                )
            
            if hasattr(self._meta, 'sequence') and self._meta.sequence:
                self._meta.sequence = tuple(
                    field for field in self._meta.sequence 
                    if field not in columns_to_exclude
                )
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        accessor='order_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocation_number = tables.Column(
        verbose_name='شناسه تخصیص',
        accessor='allocation_id',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    vehicle_entry_time = tables.Column(
        verbose_name='تاریخ و ساعت ورود',
        accessor='vehicle_entry_time',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    empty_weight = tables.Column(
        verbose_name='وزن خالی',
        accessor='empty_weight',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    gross_weight = tables.Column(
        verbose_name='وزن پر',
        accessor='gross_weight',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    driver_name = tables.Column(
        verbose_name='نام راننده',
        accessor='driver_name',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    driver_mobile = tables.Column(
        verbose_name='شماره همراه راننده',
        accessor='driver_mobile',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    plate_number = tables.Column(
        verbose_name='پلاک خودرو',
        accessor='plate_number',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    driver_national_id = tables.Column(
        verbose_name='کد ملی راننده',
        accessor='driver_national_id',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    carrier_name = tables.Column(
        verbose_name='اسم باربری',
        accessor='carrier_name',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    class Meta:
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'allocation_number', 'vehicle_entry_time', 'empty_weight', 'gross_weight', 
                 'driver_name', 'driver_mobile', 'plate_number', 'driver_national_id', 'carrier_name', 'actions')
        attrs = {
            'class': 'data-table searchable-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'allocation_number', 'vehicle_entry_time', 'empty_weight', 'gross_weight',
                   'driver_name', 'driver_mobile', 'plate_number', 'driver_national_id', 'carrier_name', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        if value and value != 'نامشخص':
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_allocation_number(self, value, record):
        """نمایش شناسه تخصیص به صورت badge"""
        if value and value != 'نامشخص':
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_vehicle_entry_time(self, value, record):
        """نمایش تاریخ و ساعت ورود"""
        if value:
            from django.template.defaultfilters import date
            return date(value, "Y/m/d H:i")
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_empty_weight(self, value, record):
        """نمایش وزن خالی"""
        if value:
            persian_weight = convert_to_persian_numbers(f"{value:,.3f}")
            return format_html('{} کیلوگرم', persian_weight)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_gross_weight(self, value, record):
        """نمایش وزن پر"""
        if value:
            persian_weight = convert_to_persian_numbers(f"{value:,.3f}")
            return format_html('{} کیلوگرم', persian_weight)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_driver_name(self, value, record):
        """نمایش نام راننده"""
        if value and value != 'نامشخص':
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_driver_mobile(self, value, record):
        """نمایش شماره همراه راننده"""
        if value and value != 'نامشخص':
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_plate_number(self, value, record):
        """نمایش پلاک خودرو به سبک پلاک ایران"""
        if value and value != 'نامشخص':
            return render_iran_plate_html(value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_driver_national_id(self, value, record):
        """نمایش کد ملی راننده"""
        if value and value != 'نامشخص':
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_carrier_name(self, value, record):
        """نمایش اسم باربری"""
        if value and value != 'نامشخص':
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_actions(self, record):
        """نمایش دکمه عملیات"""
        transport = getattr(record, 'transport', None)
        if not transport:
            return '-'
        
        try:
            return format_html(
                '<a href="{}" class="btn-outline-primary">ثبت بارنامه</a>',
                reverse('distribution:register_waybill', args=[transport.waybill_number])
            )
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class ExitTable(tables.Table):
    """جدول لیست حمل‌های در انتظار خروج با استفاده از django-tables2"""
    
    waybill_number = tables.Column(
        verbose_name='شناسه حمل',
        accessor='transport.waybill_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    order_number = tables.Column(
        verbose_name='شناسه سفارش',
        accessor='order_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocation_number = tables.Column(
        verbose_name='شناسه تخصیص',
        accessor='allocation_id',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    plate_number = tables.Column(
        verbose_name='پلاک',
        accessor='plate_number',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    product_name = tables.Column(
        verbose_name='محصول',
        accessor='product_name',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    quantity = tables.Column(
        verbose_name='مقدار (کیلوگرم)',
        accessor='quantity',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    class Meta:
        template_name = 'django_tables2/bootstrap.html'
        fields = ('waybill_number', 'order_number', 'allocation_number', 'plate_number', 'product_name', 'quantity', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('waybill_number', 'order_number', 'allocation_number', 'plate_number', 'product_name', 'quantity', 'actions')
    
    def render_waybill_number(self, value, record):
        """نمایش شناسه حمل به صورت badge"""
        if value:
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_order_number(self, value, record):
        """نمایش شناسه سفارش به صورت badge"""
        if value and value != 'نامشخص':
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_allocation_number(self, value, record):
        """نمایش شناسه تخصیص به صورت badge"""
        if value and value != 'نامشخص':
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_plate_number(self, value, record):
        """نمایش پلاک خودرو به سبک پلاک ایران"""
        if value and value != 'نامشخص':
            return render_iran_plate_html(value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_product_name(self, value, record):
        """نمایش نام محصول"""
        if value and value != 'نامشخص':
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_quantity(self, value, record):
        """نمایش مقدار"""
        if value and value > 0:
            persian_quantity = convert_to_persian_numbers(f"{value:,.3f}")
            return persian_quantity
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        transport = getattr(record, 'transport', None)
        if not transport:
            return '-'
        
        try:
            buttons = []
            
            # دکمه چاپ بارنامه
            buttons.append(
                format_html(
                    '<a href="{}" class="btn-primary" target="_blank">چاپ بارنامه</a>',
                    reverse('distribution:print_waybill_pdf', args=[transport.waybill_number])
                )
            )
            
            # دکمه خودرو خارج شد
            buttons.append(
                format_html(
                    '<a href="{}" class="btn-success" onclick="return confirm(\'آیا مطمئن هستید که خودرو خارج شده است؟\');">خودرو خارج شد</a>',
                    reverse('distribution:mark_vehicle_exited', args=[transport.waybill_number])
                )
            )
            
            return format_html(
                '<div style="display: flex; gap: 5px; flex-wrap: wrap; justify-content: center;">{}</div>',
                mark_safe(''.join(str(button) for button in buttons))
            )
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))

