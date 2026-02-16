import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from core.helpers import check_field_access_prefer_edit
from core.AllocationFolder.AllocationModel import Allocation
from core.OrderFolder.OrderModel import Order
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.TransportFolder.TransportModel import Transport
from sales.views.allocation_list_view import get_delivery_address_info


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


def render_iran_plate(plate_number):
    """نمایش پلاک به سبک پلاک ایران (فراخوانی ماژول plate_display)."""
    from distribution.plate_display import render_iran_plate_html
    return render_iran_plate_html(plate_number)


class VehicleRecruitmentTable(tables.Table):
    """جدول لیست تخصیص‌های در انتظار جذب خودرو با استفاده از django-tables2"""
    
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
        from core.AllocationFolder.AllocationModel import Allocation as AllocationModel
        from core.OrderFolder.OrderModel import Order as OrderModel
        from core.PersonFolder.DeliveryAddressModel import DeliveryAddress as DeliveryAddressModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'allocation_number': True,
                'order_number': True,
                'shipping_method': True,
                'delivery_info': True,
                'transports_count': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'allocation_number': (AllocationModel, 'allocation_number'),
            'order_number': (OrderModel, 'order_number'),
            'shipping_method': None,  # همیشه نمایش داده می‌شود
            'delivery_info': (DeliveryAddressModel, 'recipient_name'),  # بررسی بر اساس یکی از فیلدهای delivery
            'transports_count': None,  # محاسبه شده
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
    
    allocation_number = tables.Column(
        verbose_name='شماره تخصیص',
        accessor='allocation.allocation_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        accessor='allocation.order.order_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    shipping_method = tables.Column(
        verbose_name='شیوه اعلام بار',
        accessor='allocation.shipping_announcement_method',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    delivery_info = tables.Column(
        verbose_name='اطلاعات آدرس تحویل',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    transports_count = tables.Column(
        verbose_name='تعداد حمل‌ها',
        accessor='transports_count',
        empty_values=(),
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
        template_name = 'django_tables2/bootstrap.html'
        fields = ('allocation_number', 'order_number', 'shipping_method', 'delivery_info', 'transports_count', 'actions')
        attrs = {
            'class': 'data-table searchable-table',
            'thead': {'class': ''}
        }
        sequence = ('allocation_number', 'order_number', 'shipping_method', 'delivery_info', 'transports_count', 'actions')
    
    def render_allocation_number(self, value, record):
        """نمایش شماره تخصیص به صورت badge"""
        if value:
            return format_html('<span class="code-badge">{}</span>', value)
        # fallback به record
        allocation = getattr(record, 'allocation', None)
        if allocation and allocation.allocation_number:
            return format_html('<span class="code-badge">{}</span>', allocation.allocation_number)
        return '-'
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش"""
        if value:
            return format_html('<span class="code-badge">{}</span>', value)
        # fallback به record
        allocation = getattr(record, 'allocation', None)
        if allocation and allocation.order:
            return format_html('<span class="code-badge">{}</span>', allocation.order.order_number)
        return '-'
    
    def render_shipping_method(self, value, record):
        """نمایش شیوه اعلام بار"""
        # همیشه از allocation استفاده می‌کنیم چون نیاز به get_display داریم
        allocation = getattr(record, 'allocation', None)
        if allocation and allocation.shipping_announcement_method:
            return allocation.get_shipping_announcement_method_display()
        return '-'
    
    def render_delivery_info(self, record):
        """نمایش دکمه جزئیات آدرس تحویل"""
        import json
        allocation = getattr(record, 'allocation', None)
        if not allocation:
            return '-'
        
        # دریافت اطلاعات آدرس تحویل
        delivery_info = None
        if allocation.delivery_postal_code:
            delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
        
        if not delivery_info:
            return format_html('<span style="color: var(--gray-400);">اطلاعات آدرس یافت نشد</span>')
        
        # بررسی دسترسی فیلدها
        accessible_delivery_fields = getattr(self, 'accessible_delivery_fields', {})
        
        # آماده‌سازی داده‌ها برای JSON (فقط فیلدهای قابل دسترسی)
        delivery_data = {
            'recipient_name': delivery_info.get('recipient_name', '-') if accessible_delivery_fields.get('recipient_name', True) else None,
            'recipient_national_id': delivery_info.get('recipient_national_id', '-') if accessible_delivery_fields.get('recipient_national_id', True) else None,
            'unique_delivery_id': delivery_info.get('unique_delivery_id', '-') if accessible_delivery_fields.get('unique_delivery_id', True) else None,
            'address': delivery_info.get('address', '-') if accessible_delivery_fields.get('address', True) else None,
            'landline_phone': delivery_info.get('landline_phone', '-'),
            'mobile_phone': delivery_info.get('mobile_phone', '-'),
            'accessible_fields': accessible_delivery_fields
        }
        
        # تبدیل به JSON و escape کردن برای استفاده در HTML attribute
        delivery_data_json = json.dumps(delivery_data, ensure_ascii=False)
        # Escape کردن quotes برای استفاده در HTML attribute (فقط double quotes)
        delivery_data_json_escaped = delivery_data_json.replace('"', '&quot;')
        
        return format_html(
            '<button type="button" '
            'class="btn-outline-info delivery-detail-btn" '
            'data-delivery-info="{}" '
            'onclick="showDeliveryInfoModal(this)">'
            'جزئیات آدرس تحویل'
            '</button>',
            delivery_data_json_escaped
        )
    
    def render_transports_count(self, value, record):
        """نمایش تعداد حمل‌ها"""
        # استفاده از value اگر موجود باشد (از accessor)
        if value is not None:
            transports_count = value
        else:
            # fallback: محاسبه از allocation
            allocation = getattr(record, 'allocation', None)
            if not allocation:
                return '-'
            transports_count = Transport.objects.filter(allocation=allocation).count()
        
        return format_html(
            '<span class="transports-count">{} حمل</span>',
            transports_count
        )
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        allocation = getattr(record, 'allocation', None)
        if not allocation:
            return '-'
        
        try:
            buttons = []
            
            # دکمه ایجاد حمل (فقط اگر تخصیص هنوز در وضعیت pending_vehicle_recruitment باشد)
            if allocation.allocation_status == 'pending_vehicle_recruitment':
                buttons.append(
                    format_html(
                        '<button type="button" '
                        'class="btn-outline-primary" '
                        'onclick="showCreateTransportModal(\'{}\')">'
                        'ایجاد حمل'
                        '</button>',
                        allocation.allocation_number
                    )
                )
            
            if not buttons:
                return '-'
            
            return format_html(
                '<div style="display: flex; gap: 10px; flex-wrap: wrap;">{}</div>',
                mark_safe(''.join(str(button) for button in buttons))
            )
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class VehicleEntryTable(tables.Table):
    """جدول لیست حمل‌های در انتظار ورود به کارخانه با استفاده از django-tables2"""
    
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
                'waybill_number': True,
                'allocation_number': True,
                'vehicle_type': True,
                'plate_number': True,
                'driver_name': True,
                'driver_national_id': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'waybill_number': None,  # همیشه نمایش داده می‌شود
            'allocation_number': None,  # همیشه نمایش داده می‌شود
            'vehicle_type': (TruckInfoModel, 'vehicle_type'),
            'plate_number': (TruckInfoModel, 'plate_number'),
            'driver_name': (PersonModel, 'name'),
            'driver_national_id': (PersonModel, 'national_id'),
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
    
    waybill_number = tables.Column(
        verbose_name='شناسه حمل',
        accessor='waybill_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocation_number = tables.Column(
        verbose_name='شناسه تخصیص',
        accessor='allocation.allocation_number',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    vehicle_type = tables.Column(
        verbose_name='نوع ماشین',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    plate_number = tables.Column(
        verbose_name='پلاک خودرو',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    driver_name = tables.Column(
        verbose_name='نام راننده',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    driver_national_id = tables.Column(
        verbose_name='شماره ملی راننده',
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
        fields = ('waybill_number', 'allocation_number', 'vehicle_type', 'plate_number', 'driver_name', 'driver_national_id', 'actions')
        attrs = {
            'class': 'data-table searchable-table',
            'thead': {'class': ''}
        }
        sequence = ('waybill_number', 'allocation_number', 'vehicle_type', 'plate_number', 'driver_name', 'driver_national_id', 'actions')
    
    def render_waybill_number(self, value, record):
        """نمایش شناسه حمل به صورت badge"""
        if value:
            return format_html('<span class="code-badge">{}</span>', value)
        # fallback به record.transport
        transport = getattr(record, 'transport', None)
        if transport and transport.waybill_number:
            return format_html('<span class="code-badge">{}</span>', transport.waybill_number)
        return '-'
    
    def render_allocation_number(self, value, record):
        """نمایش شناسه تخصیص به صورت badge"""
        if value:
            return format_html('<span class="code-badge">{}</span>', value)
        # fallback به record.transport
        transport = getattr(record, 'transport', None)
        if transport and transport.allocation and transport.allocation.allocation_number:
            return format_html('<span class="code-badge">{}</span>', transport.allocation.allocation_number)
        return '-'
    
    def render_vehicle_type(self, value, record):
        """نمایش نوع ماشین"""
        vehicle_type = getattr(record, 'vehicle_type', None)
        if vehicle_type:
            return vehicle_type
        return '-'
    
    def render_plate_number(self, value, record):
        """نمایش پلاک خودرو به سبک پلاک ایران"""
        plate_number = getattr(record, 'plate_number', None)
        return render_iran_plate(plate_number)
    
    def render_driver_name(self, value, record):
        """نمایش نام راننده"""
        driver_name = getattr(record, 'driver_name', None)
        if driver_name:
            return driver_name
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_driver_national_id(self, value, record):
        """نمایش شماره ملی راننده"""
        driver_national_id = getattr(record, 'driver_national_id', None)
        if driver_national_id:
            return format_html('<span class="code-badge">{}</span>', driver_national_id)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_actions(self, record):
        """نمایش دکمه عملیات"""
        transport = getattr(record, 'transport', None)
        if not transport:
            return '-'
        
        try:
            return format_html(
                '<button type="button" '
                'class="btn-outline-primary" '
                'onclick="showVehicleEntryModal(\'{}\')">'
                'ثبت ورود'
                '</button>',
                transport.waybill_number
            )
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class LoadingExitTable(tables.Table):
    """جدول لیست حمل‌های در انتظار بارگیری با استفاده از django-tables2"""
    
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
        from core.TransportFolder.TruckInfoModel import TruckInfo as TruckInfoModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'product_name': True,
                'allocated_quantity': True,
                'unit': True,
                'plate_number': True,
                'vehicle_type': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': None,  # همیشه نمایش داده می‌شود
            'product_name': None,  # همیشه نمایش داده می‌شود
            'allocated_quantity': None,  # همیشه نمایش داده می‌شود
            'unit': None,  # همیشه نمایش داده می‌شود
            'plate_number': (TruckInfoModel, 'plate_number'),
            'vehicle_type': (TruckInfoModel, 'vehicle_type'),
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
    
    product_name = tables.Column(
        verbose_name='نوع محصول',
        accessor='product_name',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocated_quantity = tables.Column(
        verbose_name='مقدار تخصیص‌یافته',
        accessor='allocated_quantity',
        empty_values=(),
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    unit = tables.Column(
        verbose_name='واحد',
        accessor='unit',
        empty_values=(),
        orderable=True,
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
    
    vehicle_type = tables.Column(
        verbose_name='نوع ماشین',
        accessor='vehicle_type',
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
        fields = ('order_number', 'product_name', 'allocated_quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'product_name', 'allocated_quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        if value and value != 'نامشخص':
            return format_html('<span class="code-badge">{}</span>', value)
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_product_name(self, value, record):
        """نمایش نام محصول"""
        if value and value != 'نامشخص':
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_allocated_quantity(self, value, record):
        """نمایش مقدار تخصیص‌یافته"""
        if value and value != 'نامشخص':
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_unit(self, value, record):
        """نمایش واحد"""
        if value:
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_plate_number(self, value, record):
        """نمایش پلاک خودرو به سبک پلاک ایران"""
        return render_iran_plate(value)
    
    def render_vehicle_type(self, value, record):
        """نمایش نوع ماشین"""
        if value:
            return value
        return format_html('<span style="color: var(--gray-400);">-</span>')
    
    def render_actions(self, record):
        """نمایش دکمه عملیات"""
        transport = getattr(record, 'transport', None)
        if not transport:
            return '-'
        
        try:
            return format_html(
                '<a href="{}" class="btn-outline-primary">ورود به جزئیات خروج کالا</a>',
                reverse('distribution:register_loading_exit', args=[transport.waybill_number])
            )
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))