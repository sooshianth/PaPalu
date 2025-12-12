import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from core.PersonFolder import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from core.helpers import check_field_access_prefer_edit
from typing import Optional, Dict
from core.OrderFolder.OrderModel import Order
import jdatetime


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


def format_number_persian(number, decimal_places=0):
    """فرمت کردن عدد با کاما و تبدیل به فارسی"""
    if number is None:
        return '-'
    try:
        # تبدیل به float
        num_float = float(number)
        # فرمت با کاما
        if decimal_places > 0:
            formatted = f"{num_float:,.{decimal_places}f}"
        else:
            formatted = f"{num_float:,.0f}"
        # تبدیل به فارسی
        return convert_to_persian_numbers(formatted)
    except (ValueError, TypeError):
        return str(number)


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
                'activity_fields': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'national_id': ('Person', 'national_id'),
            'name': ('Person', 'name'),
            'nature': ('Person', 'nature'),
            'mobile_number': ('PhoneNumber', 'number'),
            'activity_fields': ('Person', 'activity_fields'),
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
        orderable=True,
        order_by='mobile_number_sort',  # استفاده از accessor سفارشی برای sort
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    activity_fields = tables.Column(
        verbose_name='حیطه فعالیت',
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
        model = Person
        template_name = 'django_tables2/bootstrap.html'
        fields = ('national_id', 'name', 'nature', 'mobile_number', 'activity_fields', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('national_id', 'name', 'nature', 'mobile_number', 'activity_fields', 'actions')
    
    def render_nature(self, value, record):
        """نمایش نوع شخص به صورت badge"""
        # اگر value None باشد یا خالی باشد، از record استفاده کن
        if value is None or value == '':
            value = getattr(record, 'nature', None)
        
        # اگر هنوز None است، از record.nature استفاده کن
        if value is None:
            value = record.nature if hasattr(record, 'nature') else None
        
        if value == 'legal':
            return format_html('<span class="badge badge-primary">حقوقی</span>')
        elif value == 'natural':
            return format_html('<span class="badge badge-success">حقیقی</span>')
        elif value:
            # اگر مقدار دیگری دارد، آن را نمایش بده
            return format_html('<span class="badge badge-secondary">{}</span>', value)
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
    
    def render_activity_fields(self, record):
        """نمایش حیطه‌های فعالیت"""
        # استفاده از prefetch شده برای جلوگیری از query اضافی
        activity_fields = record.activity_fields.all()
        if activity_fields.exists():
            # نمایش همه حیطه‌های فعالیت به صورت badge
            badges = []
            for activity in activity_fields:
                badges.append(format_html(
                    '<span class="badge badge-info" style="margin-left: 3px; margin-bottom: 3px; display: inline-block;">{}</span>',
                    str(activity)
                ))
            return format_html(''.join(badges))
        return format_html('<span class="text-muted">-</span>')
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            edit_url = reverse('sales:edit_customer', args=[record.national_id])
            detail_url = reverse('sales:customer_detail', args=[record.national_id])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info customer-detail-link" data-customer-id="{}" title="جزئیات">جزئیات</a>'
                '<a href="{}" class="btn-outline-warning" title="ویرایش" style="margin-right: 5px;">ویرایش</a>'
                '</div>',
                detail_url,
                record.national_id,
                edit_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class OrderTable(tables.Table):
    """جدول لیست سفارش‌ها با استفاده از django-tables2"""
    
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
        from core.OrderFolder.OrderModel import Order as OrderModel
        from core.OrderFolder.OrderItemModel import OrderItem as OrderItemModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'status': True,
                'total_purchase_cost': True,
                'total_order_weight': True,
                'registered_by': True,
                'created_at': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': None,  # همیشه نمایش داده می‌شود
            'status': (OrderModel, 'status'),
            'total_purchase_cost': (OrderItemModel, 'total_purchase_cost'),
            'total_order_weight': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'registered_by': None,  # همیشه نمایش داده می‌شود
            'created_at': None,  # همیشه نمایش داده می‌شود
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
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت',
        orderable=True,
        empty_values=(),
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    total_purchase_cost = tables.Column(
        verbose_name='بهای تمام شده خرید (ریال)',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    total_order_weight = tables.Column(
        verbose_name='وزن کل سفارش (کیلوگرم)',
        empty_values=(),
        orderable=True,
        order_by='total_order_weight',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    registered_by = tables.Column(
        verbose_name='ثبت‌کننده',
        accessor='registered_by.username',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    created_at = tables.Column(
        verbose_name='تاریخ ایجاد',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    class Meta:
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'status', 'total_purchase_cost', 'total_order_weight', 'registered_by', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'status', 'total_purchase_cost', 'total_order_weight', 'registered_by', 'created_at', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        return format_html('<span class="code-badge">{}</span>', value)
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        # همیشه از record استفاده کن تا مطمئن شویم که وضعیت را می‌خوانیم
        status_value = getattr(record, 'status', None)
        if not status_value:
            status_value = value
        
        # اگر هنوز None است، از record مستقیماً بخوان
        if not status_value:
            try:
                status_value = record.status
            except:
                pass
        
        # استفاده از get_status_display برای دریافت نمایش فارسی
        try:
            status_display = record.get_status_display() if hasattr(record, 'get_status_display') else None
        except:
            status_display = None
        
        # تعریف رنگ‌ها و متن‌های فارسی برای هر وضعیت
        status_badges = {
            'pending': ('badge-pending', 'در انتظار'),
            'confirmed': ('badge-confirmed', 'تایید شده'),
            'processing': ('badge-processing', 'در حال پردازش'),
            'pending_proforma_issue': ('badge-pending-proforma', 'در انتظار صدور پیش فاکتور'),
            'pending_customer_proforma_upload': ('badge-pending-upload', 'در انتظار آپلود پیش فاکتور مشتری'),
            'pending_transaction_receipt_upload': ('badge-pending-receipt', 'در انتظار بارگذاری رسید تراکنش'),
            'pending_accounting_approval': ('badge-pending-accounting', 'در انتظار تایید حسابداری'),
            'pending_payment_approval': ('badge-pending-payment', 'در انتظار تایید پرداخت'),
            'pending_allocation': ('badge-pending-allocation', 'در انتظار تخصیص'),
            'pending_allocation_approval': ('badge-pending-allocation-approval', 'در انتظار تأیید تخصیص'),
            'pending_factory': ('badge-pending-factory', 'در انتظار کارخانه'),
            'pending_unloading_approval': ('badge-pending-unloading', 'در انتظار تایید تخلیه'),
            'pending_settlement': ('badge-pending-settlement', 'در انتظار تسویه'),
            'completed': ('badge-completed', 'تکمیل شده'),
            'cancelled': ('badge-cancelled', 'لغو شده'),
            'archived': ('badge-archived', 'بایگانی شده'),
        }
        
        if status_value and status_value in status_badges:
            badge_class, badge_text = status_badges[status_value]
            return format_html('<span class="badge {}">{}</span>', badge_class, badge_text)
        elif status_value:
            # اگر وضعیت وجود دارد اما در status_badges نیست، از get_status_display استفاده کن
            display_text = status_display or status_value.replace('_', ' ').title()
            # برای وضعیت‌های ناشناخته از رنگ پیش‌فرض استفاده کن
            return format_html('<span class="badge badge-unknown">{}</span>', display_text)
        else:
            return format_html('<span class="badge badge-archived">-</span>')
    
    def render_total_purchase_cost(self, value, record):
        """نمایش بهای تمام شده خرید"""
        if value is None:
            return format_number_persian(0, decimal_places=0)
        return format_number_persian(value, decimal_places=0)
    
    def render_total_order_weight(self, value, record):
        """نمایش وزن کل سفارش"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            total_weight = float(value)
        else:
            # fallback: محاسبه از اقلام
            try:
                total_weight = 0
                for item in record.order_items.all():
                    weight_kg = item.get_weight_in_kg()
                    total_weight += weight_kg
            except:
                return '-'
        
        if total_weight > 0:
            # نمایش به صورت عدد با دو رقم اعشار و فرمت فارسی (همیشه کیلوگرم)
            kg_formatted = format_number_persian(total_weight, decimal_places=2)
            return f"{kg_formatted} کیلوگرم"
        else:
            return '-'
    
    def render_registered_by(self, value, record):
        """نمایش ثبت‌کننده"""
        if value:
            return value
        return '-'
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        # استفاده از record برای اطمینان از دریافت مقدار صحیح
        if hasattr(record, 'created_at') and record.created_at:
            dt = record.created_at
            # اگر jdatetime.datetime است
            if isinstance(dt, jdatetime.datetime):
                # اگر ساعت دارد (نه 00:00:00)
                if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
                    # نمایش تاریخ و ساعت (بدون ثانیه)
                    return dt.strftime('%Y-%m-%d %H:%M')
                else:
                    # فقط تاریخ
                    return dt.strftime('%Y-%m-%d')
            # اگر jdatetime.date است
            elif isinstance(dt, jdatetime.date):
                return dt.strftime('%Y-%m-%d')
        
        # fallback: استفاده از value
        if value:
            if isinstance(value, jdatetime.datetime):
                if value.hour != 0 or value.minute != 0 or value.second != 0:
                    return value.strftime('%Y-%m-%d %H:%M')
                else:
                    return value.strftime('%Y-%m-%d')
            elif isinstance(value, jdatetime.date):
                return value.strftime('%Y-%m-%d')
        
        return '-'
    
    actions = tables.Column(
        verbose_name='عملیات',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        from django.urls import reverse
        from core.RBACModel import user_has_task, TaskChoices
        from sales.views.order_views import can_edit_order
        
        buttons = []
        
        # دکمه جزئیات (popup)
        detail_url = reverse('sales:order_detail', args=[record.order_number])
        buttons.append(
            format_html(
                '<a href="{}" class="btn-outline-info order-detail-link" data-order-number="{}" title="جزئیات">جزئیات</a>',
                detail_url,
                record.order_number
            )
        )
        
        # دکمه ویرایش (فقط اگر کاربر دسترسی داشته باشد و سفارش قابل ویرایش باشد)
        if hasattr(self, 'user') and self.user:
            has_permission = user_has_task(self.user, TaskChoices.SALES_EDIT_ORDER.value)
            is_editable = can_edit_order(record)
            if has_permission and is_editable:
                edit_url = reverse('sales:order_edit', args=[record.order_number])
                buttons.append(
                    format_html(
                        '<a href="{}" class="btn-outline-warning">ویرایش</a>',
                        edit_url
                    )
                )
        
        # استفاده از btn-group برای نمایش دکمه‌ها کنار هم
        return format_html(
            '<div class="btn-group">{}</div>',
            mark_safe(''.join(buttons))
        )


class ProductTable(tables.Table):
    """جدول لیست محصولات با استفاده از django-tables2"""
    
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
        from core.ProductFolder.ProductModel import Product as ProductModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'image': True,
                'code': True,
                'name': True,
                'category': True,
                'grade': True,
                'physical_shape': True,
                'main_application': True,
                'main_unit': True,
                'is_custom': True,
                'created_at': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'image': (ProductModel, 'image'),
            'code': (ProductModel, 'code'),
            'name': (ProductModel, 'name'),
            'category': (ProductModel, 'category'),
            'grade': (ProductModel, 'grade'),
            'physical_shape': (ProductModel, 'physical_shape'),
            'main_application': (ProductModel, 'main_application'),
            'main_unit': (ProductModel, 'main_unit'),
            'is_custom': (ProductModel, 'is_custom'),
            'created_at': None,  # همیشه نمایش داده می‌شود
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
    
    image = tables.Column(
        verbose_name='تصویر',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    code = tables.Column(
        verbose_name='کد محصول',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    name = tables.Column(
        verbose_name='نام محصول',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    category = tables.Column(
        verbose_name='گروه',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    grade = tables.Column(
        verbose_name='گرید',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    physical_shape = tables.Column(
        verbose_name='شکل فیزیکی',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    main_application = tables.Column(
        verbose_name='کاربرد',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    main_unit = tables.Column(
        verbose_name='واحد اصلی',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    is_custom = tables.Column(
        verbose_name='نوع',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_at = tables.Column(
        verbose_name='تاریخ ایجاد',
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
        from core.ProductFolder.ProductModel import Product
        model = Product
        template_name = 'django_tables2/bootstrap.html'
        fields = ('image', 'code', 'name', 'category', 'grade', 'physical_shape', 'main_application', 'main_unit', 'is_custom', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('image', 'code', 'name', 'category', 'grade', 'physical_shape', 'main_application', 'main_unit', 'is_custom', 'created_at', 'actions')
    
    def render_image(self, record):
        """نمایش تصویر محصول"""
        if record.image:
            return format_html(
                '<img src="{}" alt="{}" class="product-image-thumb">',
                record.image.url,
                record.name
            )
        else:
            return format_html(
                '<div class="product-image-thumb" style="background-color: var(--gray-200); display: flex; align-items: center; justify-content: center; color: var(--gray-600);">-</div>'
            )
    
    def render_code(self, value, record):
        """نمایش کد محصول"""
        return format_html('<code style="background-color: var(--gray-100); padding: 3px 6px; border-radius: 4px;">{}</code>', value)
    
    def render_name(self, value, record):
        """نمایش نام محصول با لینک به جزئیات"""
        detail_url = reverse('sales:product_detail', args=[record.id])
        return format_html(
            '<a href="{}" style="color: var(--primary-green); text-decoration: none; font-weight: 500;">{}</a>',
            detail_url,
            value
        )
    
    def render_category(self, value, record):
        """نمایش گروه محصول"""
        if value:
            if record.subcategory:
                return format_html('{}<br><small style="color: var(--gray-600);">{}</small>', value, record.subcategory)
            return value
        return '-'
    
    def render_grade(self, value, record):
        """نمایش گرید"""
        return value if value else '-'
    
    def render_physical_shape(self, value, record):
        """نمایش شکل فیزیکی"""
        return value if value else '-'
    
    def render_main_application(self, value, record):
        """نمایش کاربرد اصلی"""
        if value:
            try:
                display_value = record.get_main_application_display()
                return format_html('<span class="badge badge-info">{}</span>', display_value)
            except:
                return format_html('<span class="badge badge-info">{}</span>', value)
        else:
            return format_html('<span class="badge badge-secondary">-</span>')
    
    def render_main_unit(self, value, record):
        """نمایش واحد اصلی"""
        return value if value else '-'
    
    def render_is_custom(self, value, record):
        """نمایش نوع محصول"""
        if value:
            return format_html('<span class="badge badge-warning">سفارشی</span>')
        else:
            return format_html('<span class="badge badge-secondary">استاندارد</span>')
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        # استفاده از record برای اطمینان از دریافت مقدار صحیح
        if hasattr(record, 'created_at') and record.created_at:
            dt = record.created_at
            # اگر jdatetime.datetime است
            if isinstance(dt, jdatetime.datetime):
                # اگر ساعت دارد (نه 00:00:00)
                if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
                    # نمایش تاریخ و ساعت (بدون ثانیه)
                    formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                else:
                    # فقط تاریخ
                    formatted_date = dt.strftime('%Y-%m-%d')
                return convert_to_persian_numbers(formatted_date)
            # اگر jdatetime.date است
            elif isinstance(dt, jdatetime.date):
                formatted_date = dt.strftime('%Y-%m-%d')
                return convert_to_persian_numbers(formatted_date)
        
        # fallback: استفاده از value
        if value:
            try:
                if isinstance(value, jdatetime.datetime):
                    if value.hour != 0 or value.minute != 0 or value.second != 0:
                        formatted_date = value.strftime('%Y-%m-%d %H:%M')
                    else:
                        formatted_date = value.strftime('%Y-%m-%d')
                    return convert_to_persian_numbers(formatted_date)
                elif isinstance(value, jdatetime.date):
                    formatted_date = value.strftime('%Y-%m-%d')
                    return convert_to_persian_numbers(formatted_date)
            except (AttributeError, TypeError):
                return str(value)
        return '-'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:product_detail', args=[record.id])
            edit_url = reverse('sales:edit_product', args=[record.id])
            delete_url = reverse('sales:delete_product', args=[record.id])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="جزئیات">جزئیات</a>'
                '<a href="{}" class="btn-outline-warning" title="ویرایش" style="margin-right: 5px;">ویرایش</a>'
                '<a href="{}" class="btn-outline-danger" title="حذف" style="margin-right: 5px;" onclick="return confirm(\'آیا از حذف این محصول اطمینان دارید؟\')">حذف</a>'
                '</div>',
                detail_url,
                edit_url,
                delete_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class ProductPriceTable(tables.Table):
    """جدول لیست قیمت‌گذاری محصولات با استفاده از django-tables2"""
    
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
        from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo as ProductFinancialInfoModel
        from core.ProductFolder.ProductModel import Product as ProductModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'product_code': True,
                'product_name': True,
                'price': True,
                'deadline': True,
                'loading_date': True,
                'condition': True,
                'created_at': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'product_code': (ProductModel, 'code'),
            'product_name': (ProductModel, 'name'),
            'price': (ProductFinancialInfoModel, 'price'),
            'deadline': (ProductFinancialInfoModel, 'deadline'),
            'loading_date': (ProductFinancialInfoModel, 'loading_date'),
            'condition': (ProductFinancialInfoModel, 'condition'),
            'created_at': None,  # همیشه نمایش داده می‌شود
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
    
    product_code = tables.Column(
        verbose_name='کد محصول',
        accessor='product.code',
        orderable=True,
        order_by='product__code',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    product_name = tables.Column(
        verbose_name='نام محصول',
        accessor='product.name',
        orderable=True,
        order_by='product__name',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    price = tables.Column(
        verbose_name='قیمت (ریال)',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    deadline = tables.Column(
        verbose_name='مهلت اعتبار',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    loading_date = tables.Column(
        verbose_name='مدت زمان بارگیری',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    condition = tables.Column(
        verbose_name='شرط',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    created_at = tables.Column(
        verbose_name='تاریخ ایجاد',
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
        from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo
        model = ProductFinancialInfo
        template_name = 'django_tables2/bootstrap.html'
        fields = ('product_code', 'product_name', 'price', 'deadline', 'loading_date', 'condition', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('product_code', 'product_name', 'price', 'deadline', 'loading_date', 'condition', 'created_at', 'actions')
    
    def render_product_code(self, value, record):
        """نمایش کد محصول"""
        return format_html('<code style="background-color: var(--gray-100); padding: 3px 6px; border-radius: 4px;">{}</code>', value)
    
    def render_product_name(self, value, record):
        """نمایش نام محصول با لینک به جزئیات"""
        detail_url = reverse('sales:product_detail', args=[record.product.id])
        return format_html(
            '<a href="{}" style="color: var(--primary-green); text-decoration: none; font-weight: 500;">{}</a>',
            detail_url,
            value
        )
    
    def render_price(self, value, record):
        """نمایش قیمت"""
        if value:
            # فرمت با اعداد فارسی و کاما
            price_formatted = format_number_persian(value, decimal_places=0)
            return format_html(
                '<strong style="color: var(--primary-green);">{}</strong>'
                '<span style="color: var(--gray-600); font-size: 0.85rem;"> ریال</span>',
                price_formatted
            )
        return '-'
    
    def render_deadline(self, value, record):
        """نمایش مهلت اعتبار"""
        if value:
            try:
                # برای jDateTimeField از strftime استفاده می‌کنیم - با ساعت
                if hasattr(value, 'hour'):
                    formatted_date = value.strftime('%Y/%m/%d %H:%M')
                else:
                    formatted_date = value.strftime('%Y/%m/%d')
                return convert_to_persian_numbers(formatted_date)
            except (AttributeError, TypeError):
                # اگر strftime کار نکرد، از str استفاده می‌کنیم
                return str(value)
        return '-'
    
    def render_loading_date(self, value, record):
        """نمایش مدت زمان بارگیری"""
        if value:
            # loading_date اکنون یک CharField است و به صورت متن ذخیره می‌شود
            return str(value)
        return '-'
    
    def render_condition(self, value, record):
        """نمایش شرط"""
        if value:
            condition_text = str(value)
            return format_html(
                '<span style="max-width: 200px; display: inline-block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{}">{}</span>',
                condition_text,
                condition_text[:50] + '...' if len(condition_text) > 50 else condition_text
            )
        return '-'
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        # استفاده از record برای اطمینان از دریافت مقدار صحیح
        if hasattr(record, 'created_at') and record.created_at:
            dt = record.created_at
            # اگر jdatetime.datetime است
            if isinstance(dt, jdatetime.datetime):
                # اگر ساعت دارد (نه 00:00:00)
                if dt.hour != 0 or dt.minute != 0 or dt.second != 0:
                    # نمایش تاریخ و ساعت (بدون ثانیه)
                    formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                else:
                    # فقط تاریخ
                    formatted_date = dt.strftime('%Y-%m-%d')
                return convert_to_persian_numbers(formatted_date)
            # اگر jdatetime.date است
            elif isinstance(dt, jdatetime.date):
                formatted_date = dt.strftime('%Y-%m-%d')
                return convert_to_persian_numbers(formatted_date)
        
        # fallback: استفاده از value
        if value:
            try:
                if isinstance(value, jdatetime.datetime):
                    if value.hour != 0 or value.minute != 0 or value.second != 0:
                        formatted_date = value.strftime('%Y-%m-%d %H:%M')
                    else:
                        formatted_date = value.strftime('%Y-%m-%d')
                    return convert_to_persian_numbers(formatted_date)
                elif isinstance(value, jdatetime.date):
                    formatted_date = value.strftime('%Y-%m-%d')
                    return convert_to_persian_numbers(formatted_date)
            except (AttributeError, TypeError):
                # اگر strftime کار نکرد، از str استفاده می‌کنیم
                return str(value)
        return '-'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:product_detail', args=[record.product.id])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="جزئیات محصول">جزئیات</a>'
                '</div>',
                detail_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class UnloadApprovalOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تایید تخلیه با استفاده از django-tables2"""
    
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
        from core.OrderFolder.OrderModel import Order as OrderModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'customer': True,
                'created_at': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': None,  # همیشه نمایش داده می‌شود
            'customer': (OrderModel, 'customer'),
            'created_at': None,  # همیشه نمایش داده می‌شود
            'actions': None,  # عملیات همیشه نمایش داده می‌شود
        }
        
        accessible_fields = {}
        for display_name, mapping in field_mapping.items():
            if mapping is None:
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
        
        columns_to_exclude = []
        for column_name in list(self.columns.columns.keys()):
            if column_name in self.accessible_fields:
                if not self.accessible_fields[column_name]:
                    columns_to_exclude.append(column_name)
        
        for column_name in columns_to_exclude:
            if column_name in self.columns.columns:
                del self.columns.columns[column_name]
        
        if columns_to_exclude:
            if not hasattr(self._meta, 'exclude') or self._meta.exclude is None:
                self._meta.exclude = tuple(columns_to_exclude)
            else:
                existing_exclude = set(self._meta.exclude) if self._meta.exclude else set()
                existing_exclude.update(columns_to_exclude)
                self._meta.exclude = tuple(existing_exclude)
            
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
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    customer = tables.Column(
        verbose_name='مشتری',
        accessor='customer.name',
        orderable=True,
        order_by='customer__name',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocations = tables.Column(
        verbose_name='تخصیص‌ها',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    transports = tables.Column(
        verbose_name='حمل‌ها',
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
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'customer', 'allocations', 'transports', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer', 'allocations', 'transports', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        return format_html('<span class="code-badge">{}</span>', value)
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        return '-'
    
    def render_allocations(self, record):
        """نمایش شماره تخصیص‌های مربوط به سفارش"""
        from core.AllocationFolder.AllocationModel import Allocation
        allocations = Allocation.objects.filter(order=record).values_list('allocation_number', flat=True)
        if allocations:
            badges = [f'<span class="code-badge" style="margin: 2px;">{alloc}</span>' for alloc in allocations]
            return format_html('<div style="display: flex; flex-wrap: wrap; gap: 4px;">{}</div>', mark_safe(' '.join(badges)))
        return '-'
    
    def render_transports(self, record):
        """نمایش شماره حمل‌های مربوط به سفارش (از طریق تخصیص‌ها)"""
        from core.AllocationFolder.AllocationModel import Allocation
        from core.TransportFolder.TransportModel import Transport
        allocations = Allocation.objects.filter(order=record)
        transports = Transport.objects.filter(allocation__in=allocations).values_list('waybill_number', flat=True)
        if transports:
            badges = [f'<span class="code-badge" style="margin: 2px;">{trans}</span>' for trans in transports]
            return format_html('<div style="display: flex; flex-wrap: wrap; gap: 4px;">{}</div>', mark_safe(' '.join(badges)))
        return '-'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:unload_approval_detail', args=[record.order_number])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="تایید تخلیه">تایید تخلیه</a>'
                '</div>',
                detail_url
            )
            return html
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class PendingSettlementOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تسویه با استفاده از django-tables2"""
    
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
        from core.OrderFolder.OrderModel import Order as OrderModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'customer_name': True,
                'order_weight': True,
                'delivered_weight': True,
                'difference_amount': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': None,  # همیشه نمایش داده می‌شود
            'customer_name': (OrderModel, 'customer'),
            'order_weight': None,  # محاسبه شده
            'delivered_weight': None,  # محاسبه شده
            'difference_amount': None,  # محاسبه شده
            'actions': None,  # عملیات همیشه نمایش داده می‌شود
        }
        
        accessible_fields = {}
        for display_name, mapping in field_mapping.items():
            if mapping is None:
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
        
        columns_to_exclude = []
        for column_name in list(self.columns.columns.keys()):
            if column_name in self.accessible_fields:
                if not self.accessible_fields[column_name]:
                    columns_to_exclude.append(column_name)
        
        for column_name in columns_to_exclude:
            if column_name in self.columns.columns:
                del self.columns.columns[column_name]
        
        if columns_to_exclude:
            if not hasattr(self._meta, 'exclude') or self._meta.exclude is None:
                self._meta.exclude = tuple(columns_to_exclude)
            else:
                existing_exclude = set(self._meta.exclude) if self._meta.exclude else set()
                existing_exclude.update(columns_to_exclude)
                self._meta.exclude = tuple(existing_exclude)
            
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
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    customer_name = tables.Column(
        verbose_name='نام مشتری',
        accessor='customer.name',
        orderable=True,
        order_by='customer__name',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    order_weight = tables.Column(
        verbose_name='وزن سفارش (کیلوگرم)',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    delivered_weight = tables.Column(
        verbose_name='وزن تحویلی (کیلوگرم)',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    difference_amount = tables.Column(
        verbose_name='مبلغ اختلاف (ریال)',
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
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'customer_name', 'order_weight', 'delivered_weight', 'difference_amount', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer_name', 'order_weight', 'delivered_weight', 'difference_amount', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        return format_html('<span class="code-badge">{}</span>', value)
    
    def render_customer_name(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        return '-'
    
    def render_order_weight(self, record):
        """محاسبه و نمایش وزن کل سفارش"""
        try:
            from decimal import Decimal
            
            # محاسبه مستقیم وزن سفارش
            order_weight = Decimal('0')
            for item in record.order_items.all():
                weight_kg = item.get_weight_in_kg()
                order_weight += Decimal(str(weight_kg))
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            weight_value = float(order_weight)
            weight_formatted = format_number_persian(weight_value, decimal_places=2)
            
            # نمایش وزن (حتی اگر صفر باشد)
            return format_html('<strong>{}</strong>', weight_formatted)
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_delivered_weight(self, record):
        """محاسبه و نمایش وزن تحویلی از مجموع وزن‌های خالص حمل‌ها"""
        try:
            from core.AllocationFolder.AllocationModel import Allocation
            from core.TransportFolder.TransportModel import Transport
            from decimal import Decimal
            
            # محاسبه مستقیم وزن تحویلی
            allocations = Allocation.objects.filter(order=record)
            transports = Transport.objects.filter(allocation__in=allocations)
            delivered_weight = sum(
                Decimal(str(t.net_weight or 0)) for t in transports
            )
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            weight_value = float(delivered_weight)
            weight_formatted = format_number_persian(weight_value, decimal_places=2)
            
            # نمایش وزن (حتی اگر صفر باشد)
            return format_html('<strong>{}</strong>', weight_formatted)
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_difference_amount(self, record):
        """محاسبه و نمایش مبلغ اختلاف"""
        try:
            from core.AllocationFolder.AllocationModel import Allocation
            from core.TransportFolder.TransportModel import Transport
            from decimal import Decimal
            
            # محاسبه وزن سفارش
            order_weight = Decimal('0')
            for item in record.order_items.all():
                weight_kg = item.get_weight_in_kg()
                order_weight += Decimal(str(weight_kg))
            
            # محاسبه وزن تحویلی
            allocations = Allocation.objects.filter(order=record)
            transports = Transport.objects.filter(allocation__in=allocations)
            delivered_weight = sum(
                Decimal(str(t.net_weight or 0)) for t in transports
            )
            
            # محاسبه اختلاف وزن
            weight_difference = delivered_weight - order_weight
            
            # محاسبه میانگین وزن‌دار فی فروش
            total_price = Decimal('0')
            total_weight_for_avg = Decimal('0')
            
            for item in record.order_items.all():
                if item.unit_price and item.quantity:
                    item_weight = Decimal(str(item.get_weight_in_kg()))
                    item_price = Decimal(str(item.unit_price))
                    total_price += item_weight * item_price
                    total_weight_for_avg += item_weight
            
            # محاسبه میانگین فی
            if total_weight_for_avg > 0:
                weighted_avg_price = total_price / total_weight_for_avg
            else:
                weighted_avg_price = Decimal('0')
            
            # محاسبه مبلغ اختلاف
            difference_amount = weight_difference * weighted_avg_price
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            amount_value = float(difference_amount)
            amount_formatted = format_number_persian(amount_value, decimal_places=0)
            
            # نمایش با رنگ مناسب (حتی اگر صفر باشد)
            if difference_amount > 0:
                return format_html(
                    '<strong style="color: var(--primary-green);">+{}</strong>',
                    amount_formatted
                )
            elif difference_amount < 0:
                return format_html(
                    '<strong style="color: #dc3545;">{}</strong>',
                    amount_formatted
                )
            else:
                return format_html('<strong>{}</strong>', format_number_persian(0, decimal_places=0))
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:settlement_detail', args=[record.order_number])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="تسویه حساب">تسویه حساب</a>'
                '</div>',
                detail_url
            )
            return html
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class PendingSettlementApprovalOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تایید تسویه کامل با استفاده از django-tables2"""
    
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
        from core.OrderFolder.OrderModel import Order as OrderModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'customer_name': True,
                'order_weight': True,
                'delivered_weight': True,
                'difference_amount': True,
                'settled_amount': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': None,  # همیشه نمایش داده می‌شود
            'customer_name': (OrderModel, 'customer'),
            'order_weight': None,  # محاسبه شده
            'delivered_weight': None,  # محاسبه شده
            'difference_amount': None,  # محاسبه شده
            'settled_amount': None,  # محاسبه شده
            'actions': None,  # عملیات همیشه نمایش داده می‌شود
        }
        
        accessible_fields = {}
        for display_name, mapping in field_mapping.items():
            if mapping is None:
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
        
        columns_to_exclude = []
        for column_name in list(self.columns.columns.keys()):
            if column_name in self.accessible_fields:
                if not self.accessible_fields[column_name]:
                    columns_to_exclude.append(column_name)
        
        for column_name in columns_to_exclude:
            if column_name in self.columns.columns:
                del self.columns.columns[column_name]
        
        if columns_to_exclude:
            if not hasattr(self._meta, 'exclude') or self._meta.exclude is None:
                self._meta.exclude = tuple(columns_to_exclude)
            else:
                existing_exclude = set(self._meta.exclude) if self._meta.exclude else set()
                existing_exclude.update(columns_to_exclude)
                self._meta.exclude = tuple(existing_exclude)
            
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
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    customer_name = tables.Column(
        verbose_name='نام مشتری',
        accessor='customer.name',
        orderable=True,
        order_by='customer__name',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    order_weight = tables.Column(
        verbose_name='وزن سفارش (کیلوگرم)',
        empty_values=(),
        accessor='_order_weight',
        orderable=True,
        order_by='_order_weight',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    delivered_weight = tables.Column(
        verbose_name='وزن تحویلی (کیلوگرم)',
        empty_values=(),
        accessor='_delivered_weight',
        orderable=True,
        order_by='_delivered_weight',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    difference_amount = tables.Column(
        verbose_name='مبلغ اختلاف (ریال)',
        empty_values=(),
        accessor='_difference_amount',
        orderable=True,
        order_by='_difference_amount',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    settled_amount = tables.Column(
        verbose_name='مبلغ تسویه شده (ریال)',
        empty_values=(),
        accessor='_settled_amount',
        orderable=True,
        order_by='_settled_amount',
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
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'customer_name', 'order_weight', 'delivered_weight', 'difference_amount', 'settled_amount', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer_name', 'order_weight', 'delivered_weight', 'difference_amount', 'settled_amount', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        return format_html('<span class="code-badge">{}</span>', value)
    
    def render_customer_name(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        return '-'
    
    def render_order_weight(self, value, record):
        """نمایش وزن کل سفارش"""
        try:
            # استفاده از مقدار محاسبه شده در view
            if value is not None:
                order_weight = value
            else:
                order_weight = getattr(record, '_order_weight', None)
                if order_weight is None:
                    # fallback: محاسبه از scratch
                    from decimal import Decimal
                    order_weight = Decimal('0')
                    for item in record.order_items.all():
                        weight_kg = item.get_weight_in_kg()
                        order_weight += Decimal(str(weight_kg))
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            weight_value = float(order_weight)
            weight_formatted = format_number_persian(weight_value, decimal_places=2)
            
            # نمایش وزن (حتی اگر صفر باشد)
            return format_html('<strong>{}</strong>', weight_formatted)
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_delivered_weight(self, value, record):
        """نمایش وزن تحویلی از مجموع وزن‌های خالص حمل‌ها"""
        try:
            # استفاده از مقدار محاسبه شده در view
            if value is not None:
                delivered_weight = value
            else:
                delivered_weight = getattr(record, '_delivered_weight', None)
                if delivered_weight is None:
                    # fallback: محاسبه از scratch
                    from core.AllocationFolder.AllocationModel import Allocation
                    from core.TransportFolder.TransportModel import Transport
                    from decimal import Decimal
                    
                    allocations = Allocation.objects.filter(order=record)
                    transports = Transport.objects.filter(allocation__in=allocations)
                    delivered_weight = sum(
                        Decimal(str(t.net_weight or 0)) for t in transports
                    )
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            weight_value = float(delivered_weight)
            weight_formatted = format_number_persian(weight_value, decimal_places=2)
            
            # نمایش وزن (حتی اگر صفر باشد)
            return format_html('<strong>{}</strong>', weight_formatted)
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_difference_amount(self, value, record):
        """نمایش مبلغ اختلاف"""
        try:
            # استفاده از مقدار محاسبه شده در view
            if value is not None:
                difference_amount = value
            else:
                difference_amount = getattr(record, '_difference_amount', None)
                if difference_amount is None:
                    # fallback: محاسبه از scratch
                    from core.AllocationFolder.AllocationModel import Allocation
                    from core.TransportFolder.TransportModel import Transport
                    from decimal import Decimal
                    
                    order_weight = Decimal('0')
                    for item in record.order_items.all():
                        weight_kg = item.get_weight_in_kg()
                        order_weight += Decimal(str(weight_kg))
                    
                    allocations = Allocation.objects.filter(order=record)
                    transports = Transport.objects.filter(allocation__in=allocations)
                    delivered_weight = sum(
                        Decimal(str(t.net_weight or 0)) for t in transports
                    )
                    
                    weight_difference = delivered_weight - order_weight
                    
                    total_price = Decimal('0')
                    total_weight_for_avg = Decimal('0')
                    
                    for item in record.order_items.all():
                        if item.unit_price and item.quantity:
                            item_weight = Decimal(str(item.get_weight_in_kg()))
                            item_price = Decimal(str(item.unit_price))
                            total_price += item_weight * item_price
                            total_weight_for_avg += item_weight
                    
                    if total_weight_for_avg > 0:
                        weighted_avg_price = total_price / total_weight_for_avg
                    else:
                        weighted_avg_price = Decimal('0')
                    
                    difference_amount = weight_difference * weighted_avg_price
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            amount_value = float(difference_amount)
            amount_formatted = format_number_persian(amount_value, decimal_places=0)
            
            # نمایش با رنگ مناسب (حتی اگر صفر باشد)
            if difference_amount > 0:
                return format_html(
                    '<strong style="color: var(--primary-green);">+{}</strong>',
                    amount_formatted
                )
            elif difference_amount < 0:
                return format_html(
                    '<strong style="color: #dc3545;">{}</strong>',
                    amount_formatted
                )
            else:
                return format_html('<strong>{}</strong>', format_number_persian(0, decimal_places=0))
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_settled_amount(self, value, record):
        """نمایش مبلغ تسویه شده"""
        try:
            # استفاده از مقدار محاسبه شده در view
            if value is not None:
                settled_amount = value
            else:
                settled_amount = getattr(record, '_settled_amount', None)
                if settled_amount is None:
                    # fallback: محاسبه از scratch
                    from core.SettlementFolder.SettlementModel import Settlement
                    from django.db.models import Sum
                    from decimal import Decimal
                    
                    settlement = Settlement.objects.filter(
                        order=record,
                        settlement_type='weight_discrepancy'
                    ).first()
                    
                    if settlement:
                        settled_amount = settlement.transaction_documents.aggregate(
                            total=Sum('document_amount')
                        )['total'] or Decimal('0')
                    else:
                        settled_amount = Decimal('0')
            
            # تبدیل به float و فرمت کردن با اعداد فارسی
            amount_value = float(settled_amount)
            amount_formatted = format_number_persian(amount_value, decimal_places=0)
            
            return format_html('<strong style="color: var(--dark-green);">{}</strong>', amount_formatted)
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:settlement_approval_detail', args=[record.order_number])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="تایید تسویه کامل">تایید تسویه کامل</a>'
                '</div>',
                detail_url
            )
            return html
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))