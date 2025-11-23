import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from core.PersonFolder import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from access.helpers import check_field_access_prefer_edit
from typing import Optional, Dict


class CustomerTable(tables.Table):
    """جدول لیست مشتریان با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        # دریافت اطلاعات دسترسی فیلدها
        self.accessible_fields = kwargs.pop('accessible_fields', None)
        user = kwargs.pop('user', None)
        
        super().__init__(*args, **kwargs)
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and user is not None:
            self.accessible_fields = self._get_accessible_fields(user)
        
        # فیلتر کردن ستون‌ها بر اساس دسترسی
        if self.accessible_fields:
            self._filter_columns_by_access()
    
    def _get_accessible_fields(self, user):
        """محاسبه فیلدهای قابل دسترسی برای کاربر"""
        from core.PersonFolder import Person as PersonModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'national_id': True,
                'name': True,
                'nature': True,
                'mobile_number': True,
                'status': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'national_id': ('Person', 'national_id'),
            'name': ('Person', 'name'),
            'nature': ('Person', 'nature'),
            'mobile_number': ('PhoneNumber', 'number'),
            'status': ('Person', 'is_active'),
            'actions': None,  # عملیات همیشه نمایش داده می‌شود
        }
        
        accessible_fields = {}
        for display_name, mapping in field_mapping.items():
            if mapping is None:
                # فیلدهایی که نیازی به بررسی دسترسی ندارند
                accessible_fields[display_name] = True
            else:
                model_name, model_field_name = mapping
                if model_name == 'Person':
                    model_class = PersonModel
                elif model_name == 'PhoneNumber':
                    from core.PersonFolder.PhoneNumberModel import PhoneNumber as PhoneNumberModel
                    model_class = PhoneNumberModel
                else:
                    accessible_fields[display_name] = False
                    continue
                
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
    
    national_id = tables.Column(
        verbose_name='شناسه مشتری',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    name = tables.Column(
        verbose_name='نام یا عنوان شخص',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    nature = tables.Column(
        verbose_name='نوع شخص',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    mobile_number = tables.Column(
        verbose_name='شماره همراه',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت',
        accessor='is_active',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
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
        model = Person
        template_name = 'django_tables2/bootstrap.html'
        fields = ('national_id', 'name', 'nature', 'mobile_number', 'status', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('national_id', 'name', 'nature', 'mobile_number', 'status', 'actions')
    
    def render_nature(self, value):
        """نمایش نوع شخص به صورت badge"""
        if value == 'legal':
            return format_html('<span class="badge badge-primary">حقوقی</span>')
        elif value == 'natural':
            return format_html('<span class="badge badge-success">حقیقی</span>')
        else:
            return format_html('<span class="badge badge-secondary">-</span>')
    
    def render_mobile_number(self, record):
        """دریافت شماره همراه از PhoneNumber"""
        person_content_type = ContentType.objects.get_for_model(Person)
        try:
            person_national_id_int = int(record.national_id)
        except (ValueError, TypeError):
            person_national_id_int = record.national_id
        
        mobile_phone = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=person_national_id_int,
            phone_type='mobile',
            is_primary=True
        ).first()
        
        if mobile_phone:
            return mobile_phone.number
        return '-'
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        if value:
            return format_html('<span class="badge badge-success">فعال</span>')
        else:
            return format_html('<span class="badge badge-secondary">غیرفعال</span>')
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            edit_url = reverse('sales:edit_customer', args=[record.national_id])
            # برای جزئیات از همان صفحه ویرایش استفاده می‌کنیم
            detail_url = reverse('sales:edit_customer', args=[record.national_id])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="جزئیات">جزئیات</a>'
                '<a href="{}" class="btn-outline-warning" title="ویرایش" style="margin-right: 5px;">ویرایش</a>'
                '</div>',
                detail_url,
                edit_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))

