import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from core.OrderFolder.OrderModel import Order
from access.helpers import check_field_access_prefer_edit


class TransactionReceiptOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار بارگذاری رسید تراکنش با استفاده از django-tables2"""
    
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
                'order_type': True,
                'status': True,
                'registered_by': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': (OrderModel, 'order_number'),
            'order_type': (OrderModel, 'order_type'),
            'status': (OrderModel, 'status'),
            'registered_by': None,  # همیشه نمایش داده می‌شود
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
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    order_type = tables.Column(
        verbose_name='نوع سفارش',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
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
    
    registered_by = tables.Column(
        verbose_name='کاربر ثبت‌کننده',
        accessor='registered_by',
        orderable=True,
        order_by='registered_by',
        empty_values=(),
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
        fields = ('order_number', 'order_type', 'status', 'registered_by', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'order_type', 'status', 'registered_by', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش"""
        return format_html('<strong>{}</strong>', value)
    
    def render_order_type(self, value, record):
        """نمایش نوع سفارش به صورت badge"""
        # استفاده از get_order_type_display برای دریافت نمایش فارسی
        try:
            if hasattr(record, 'get_order_type_display'):
                display_value = record.get_order_type_display()
            else:
                display_value = value
        except:
            display_value = value
        
        if value == 'purchase':
            return format_html('<span class="badge badge-primary">خرید</span>')
        elif value == 'sale':
            return format_html('<span class="badge badge-success">فروش</span>')
        elif display_value:
            return format_html('<span class="badge badge-secondary">{}</span>', display_value)
        else:
            return format_html('<span class="badge badge-secondary">-</span>')
    
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
            'pending_vehicle_recruitment': ('badge-pending-vehicle', 'در انتظار جذب خودرو'),
            'pending_vehicle_entry': ('badge-pending-vehicle-entry', 'در انتظار ورود خودرو به کارخانه'),
            'pending_loading': ('badge-pending-loading', 'در انتظار بارگیری'),
            'pending_waybill': ('badge-pending-waybill', 'در انتظار بارنامه'),
            'pending_exit': ('badge-pending-exit', 'در انتظار خروج'),
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
    
    def render_registered_by(self, value, record):
        """نمایش کاربر ثبت‌کننده"""
        if record.registered_by:
            # استفاده از get_full_name اگر وجود داشته باشد، در غیر این صورت از username
            full_name = record.registered_by.get_full_name() if hasattr(record.registered_by, 'get_full_name') else ''
            if full_name:
                return full_name
            # اگر get_full_name خالی بود، از username استفاده کن
            username = record.registered_by.username if hasattr(record.registered_by, 'username') else '-'
            return username
        return '-'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            upload_url = reverse('sales:transaction_receipt_upload', args=[record.order_number])
            
            html = format_html(
                '<a href="{}" class="btn-outline-info" title="ثبت رسید تراکنش">ثبت رسید تراکنش</a>',
                upload_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class ApproveTransactionReceiptTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تأیید حسابداری با استفاده از django-tables2"""
    
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
        from core.PersonFolder import Person as PersonModel
        
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
            'order_number': (OrderModel, 'order_number'),
            'customer': (PersonModel, 'name'),
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
        empty_values=(),
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
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'customer', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer', 'created_at', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش"""
        return format_html('<strong>{}</strong>', value)
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        # اگر customer وجود نداشت، از record استفاده کن
        if record.customer:
            return record.customer.name if hasattr(record.customer, 'name') else '-'
        return '-'
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        if value:
            try:
                # برای jDateTimeField از strftime استفاده می‌کنیم
                return value.strftime('%Y/%m/%d')
            except (AttributeError, TypeError):
                # اگر strftime کار نکرد، از str استفاده می‌کنیم
                return str(value)
        return '-'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:approve_transaction_receipt_detail', args=[record.order_number])
            
            html = format_html(
                '<a href="{}" class="btn-outline-info" title="مشاهده و تأیید">مشاهده و تأیید</a>',
                detail_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))

