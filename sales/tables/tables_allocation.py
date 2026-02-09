import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from decimal import Decimal
from core.OrderFolder.OrderModel import Order
from core.helpers import check_field_access_prefer_edit
from core.decimal_utils import to_decimal


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


def format_number_persian(number, decimal_places=0):
    """فرمت کردن عدد با کاما و تبدیل به فارسی (اعشار ثابت)"""
    if number is None:
        return '-'
    try:
        d = Decimal(str(number))
        if decimal_places > 0:
            quantizer = Decimal(10) ** -decimal_places
            formatted = f"{d.quantize(quantizer):,.{decimal_places}f}"
        else:
            formatted = f"{d.quantize(Decimal('1')):,.0f}"
        return convert_to_persian_numbers(formatted)
    except (ValueError, TypeError):
        return str(number)


def calculate_order_total_quantity(order):
    """محاسبه مجموع مقدار محصولات سفارش به کیلوگرم (اعشار ثابت)"""
    total_quantity = Decimal('0')
    for item in order.order_items.all():
        w = item.get_weight_in_kg()
        total_quantity += w
    return total_quantity


def calculate_allocation_total_quantity(order):
    """محاسبه مجموع مقدار تخصیص‌ها به کیلوگرم (اعشار ثابت)"""
    from core.AllocationFolder.AllocationModel import Allocation
    total_quantity = Decimal('0')
    allocations = Allocation.objects.filter(order=order)
    for allocation in allocations:
        for product_info in allocation.product_infos.all():
            quantity = to_decimal(product_info.quantity)
            unit = product_info.unit
            if unit == 'kg':
                total_quantity += quantity
            elif unit == 'ton':
                total_quantity += quantity * 1000
            elif unit == 'gr':
                total_quantity += quantity / 1000
            else:
                total_quantity += quantity
    return total_quantity


class AllocationTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تخصیص با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        # دریافت اطلاعات دسترسی فیلدها
        self.accessible_fields = kwargs.pop('accessible_fields', None)
        user = kwargs.pop('user', None)
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and user is not None:
            self.accessible_fields = self._get_accessible_fields(user)
        
        base_exclude = list(getattr(self.Meta, 'exclude', None) or [])
        if self.accessible_fields:
            exclude_columns = [col for col, access in self.accessible_fields.items() if not access]
            base_exclude = list(set(base_exclude) | set(exclude_columns))
        kwargs['exclude'] = tuple(base_exclude)
        super().__init__(*args, **kwargs)
    
    def _get_accessible_fields(self, user):
        """محاسبه فیلدهای قابل دسترسی برای کاربر"""
        from core.OrderFolder.OrderModel import Order as OrderModel
        from core.PersonFolder import Person as PersonModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'customer': True,
                'allocations_count': True,
                'order_total_quantity': True,
                'allocation_total_quantity': True,
                'status': True,
                'remaining_amount': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': (OrderModel, 'order_number'),
            'customer': (PersonModel, 'name'),
            'allocations_count': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'order_total_quantity': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'allocation_total_quantity': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'status': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'remaining_amount': None,  # محاسبه شده، همیشه نمایش داده می‌شود
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
    
    allocations_count = tables.Column(
        verbose_name='تعداد تخصیص‌ها',
        accessor='allocations_count',
        orderable=True,
        order_by='allocations_count',
        empty_values=(),
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    order_total_quantity = tables.Column(
        verbose_name='مقدار سفارش (کیلوگرم)',
        accessor='order_total_quantity_kg',
        orderable=True,
        order_by='order_total_quantity_kg',
        empty_values=(),
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocation_total_quantity = tables.Column(
        verbose_name='مقدار تخصیص شده (کیلوگرم)',
        accessor='allocation_total_quantity_kg',
        orderable=True,
        order_by='allocation_total_quantity_kg',
        empty_values=(),
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    remaining_amount = tables.Column(
        verbose_name='مقدار باقی مانده (کیلوگرم)',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت',
        empty_values=(),
        orderable=True,
        order_by='allocation_total_quantity_kg',  # sort بر اساس مقدار تخصیص شده
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
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'customer', 'allocations_count', 'order_total_quantity', 'allocation_total_quantity', 'remaining_amount', 'status', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer', 'allocations_count', 'order_total_quantity', 'allocation_total_quantity', 'remaining_amount', 'status', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        return format_html('<span class="code-badge">{}</span>', value)
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        # اگر customer وجود نداشت، از record استفاده کن
        if record.customer:
            return record.customer.name if hasattr(record.customer, 'name') else '-'
        return '-'
    
    def render_allocations_count(self, value, record):
        """نمایش تعداد تخصیص‌ها"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            return format_number_persian(value, decimal_places=0)
        # fallback: محاسبه دستی
        from core.AllocationFolder.AllocationModel import Allocation
        count = Allocation.objects.filter(order=record).count()
        return format_number_persian(count, decimal_places=0)
    
    def render_order_total_quantity(self, value, record):
        """نمایش مقدار سفارش"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            formatted_total = format_number_persian(value, decimal_places=2)
            return format_html('{}', formatted_total)
        # fallback: محاسبه دستی
        total = calculate_order_total_quantity(record)
        formatted_total = format_number_persian(total, decimal_places=2)
        return format_html('{}', formatted_total)
    
    def render_allocation_total_quantity(self, value, record):
        """نمایش مقدار تخصیص شده"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            formatted_total = format_number_persian(value, decimal_places=2)
            return format_html('{}', formatted_total)
        # fallback: محاسبه دستی
        total = calculate_allocation_total_quantity(record)
        formatted_total = format_number_persian(total, decimal_places=2)
        return format_html('{}', formatted_total)
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        # استفاده از مقادیر annotate شده اگر موجود باشند
        if hasattr(record, 'order_total_quantity_kg') and hasattr(record, 'allocation_total_quantity_kg'):
            order_total = to_decimal(record.order_total_quantity_kg)
            allocation_total = to_decimal(record.allocation_total_quantity_kg)
        else:
            order_total = calculate_order_total_quantity(record)
            allocation_total = calculate_allocation_total_quantity(record)
        is_complete = abs(order_total - allocation_total) < Decimal('0.001')
        
        if is_complete:
            return format_html(
                '<span class="status-badge status-complete">تکمیل شده</span>'
            )
        else:
            return format_html(
                '<span class="status-badge status-incomplete">در انتظار</span>'
            )
    
    def render_remaining_amount(self, value, record):
        """نمایش مقدار باقی مانده"""
        # استفاده از مقادیر annotate شده اگر موجود باشند
        if hasattr(record, 'order_total_quantity_kg') and hasattr(record, 'allocation_total_quantity_kg'):
            order_total = to_decimal(record.order_total_quantity_kg)
            allocation_total = to_decimal(record.allocation_total_quantity_kg)
        else:
            order_total = calculate_order_total_quantity(record)
            allocation_total = calculate_allocation_total_quantity(record)
        remaining = order_total - allocation_total
        formatted_remaining = format_number_persian(remaining, decimal_places=2)
        return format_html('{}', formatted_remaining)
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            from core.AllocationFolder.AllocationModel import Allocation
            from django.utils.safestring import mark_safe
            
            create_url = reverse('sales:allocation_create', args=[record.order_number])
            allocations = Allocation.objects.filter(order=record).select_related('order')
            
            # ساخت HTML به صورت مستقیم
            html_parts = [
                f'<a href="{create_url}" class="btn-outline-primary">ایجاد تخصیص جدید</a>'
            ]
            
            for allocation in allocations:
                edit_url = reverse('sales:allocation_edit', args=[record.order_number, allocation.allocation_number])
                html_parts.append(
                    f'<a href="{edit_url}" class="btn-outline-primary" style="font-size: 0.8rem; margin-right: 5px;">ویرایش {allocation.allocation_number}</a>'
                )
            
            # ترکیب تمام قسمت‌های HTML
            inner_html = ''.join(html_parts)
            return format_html(
                '<div style="display: flex; gap: 10px; flex-wrap: wrap;">{}</div>',
                mark_safe(inner_html)
            )
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class ApproveAllocationTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تأیید تخصیص با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        # دریافت اطلاعات دسترسی فیلدها
        self.accessible_fields = kwargs.pop('accessible_fields', None)
        user = kwargs.pop('user', None)
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and user is not None:
            self.accessible_fields = self._get_accessible_fields(user)
        
        base_exclude = list(getattr(self.Meta, 'exclude', None) or [])
        if self.accessible_fields:
            exclude_columns = [col for col, access in self.accessible_fields.items() if not access]
            base_exclude = list(set(base_exclude) | set(exclude_columns))
        kwargs['exclude'] = tuple(base_exclude)
        super().__init__(*args, **kwargs)
    
    def _get_accessible_fields(self, user):
        """محاسبه فیلدهای قابل دسترسی برای کاربر"""
        from core.OrderFolder.OrderModel import Order as OrderModel
        from core.PersonFolder import Person as PersonModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'customer': True,
                'allocations_count': True,
                'order_total_quantity': True,
                'allocation_total_quantity': True,
                'balance_status': True,
                'inquiry_status': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': (OrderModel, 'order_number'),
            'customer': (PersonModel, 'name'),
            'allocations_count': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'order_total_quantity': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'allocation_total_quantity': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'balance_status': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'inquiry_status': None,  # محاسبه شده، همیشه نمایش داده می‌شود
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
    
    allocations_count = tables.Column(
        verbose_name='تعداد تخصیص‌ها',
        accessor='allocations_count',
        orderable=True,
        order_by='allocations_count',
        empty_values=(),
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    order_total_quantity = tables.Column(
        verbose_name='مقدار سفارش (کیلوگرم)',
        accessor='order_total_quantity_kg',
        orderable=True,
        order_by='order_total_quantity_kg',
        empty_values=(),
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    allocation_total_quantity = tables.Column(
        verbose_name='مقدار تخصیص شده (کیلوگرم)',
        accessor='allocation_total_quantity_kg',
        orderable=True,
        order_by='allocation_total_quantity_kg',
        empty_values=(),
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    balance_status = tables.Column(
        verbose_name='وضعیت برابری',
        empty_values=(),
        orderable=True,
        order_by='allocation_total_quantity_kg',  # sort بر اساس مقدار تخصیص شده
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    inquiry_status = tables.Column(
        verbose_name='وضعیت استعلام',
        accessor='all_inquired_status',
        empty_values=(),
        orderable=True,
        order_by='all_inquired_status',  # استفاده از فیلد annotate شده
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
        model = Order
        template_name = 'django_tables2/bootstrap.html'
        fields = ('order_number', 'customer', 'allocations_count', 'order_total_quantity', 'allocation_total_quantity', 'balance_status', 'inquiry_status', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer', 'allocations_count', 'order_total_quantity', 'allocation_total_quantity', 'balance_status', 'inquiry_status', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش به صورت badge"""
        return format_html('<span class="code-badge">{}</span>', value)
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        # اگر customer وجود نداشت، از record استفاده کن
        if record.customer:
            return record.customer.name if hasattr(record.customer, 'name') else '-'
        return '-'
    
    def render_allocations_count(self, value, record):
        """نمایش تعداد تخصیص‌ها"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            return format_number_persian(value, decimal_places=0)
        # fallback: محاسبه دستی
        from core.AllocationFolder.AllocationModel import Allocation
        count = Allocation.objects.filter(order=record).count()
        return format_number_persian(count, decimal_places=0)
    
    def render_order_total_quantity(self, value, record):
        """نمایش مقدار سفارش"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            formatted_total = format_number_persian(value, decimal_places=2)
            return format_html('{}', formatted_total)
        # fallback: محاسبه دستی
        total = calculate_order_total_quantity(record)
        formatted_total = format_number_persian(total, decimal_places=2)
        return format_html('{}', formatted_total)
    
    def render_allocation_total_quantity(self, value, record):
        """نمایش مقدار تخصیص شده"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            formatted_total = format_number_persian(value, decimal_places=2)
            return format_html('{}', formatted_total)
        # fallback: محاسبه دستی
        total = calculate_allocation_total_quantity(record)
        formatted_total = format_number_persian(total, decimal_places=2)
        return format_html('{}', formatted_total)
    
    def render_balance_status(self, value, record):
        """نمایش وضعیت برابری"""
        # استفاده از مقادیر annotate شده اگر موجود باشند
        if hasattr(record, 'order_total_quantity_kg') and hasattr(record, 'allocation_total_quantity_kg'):
            order_total = to_decimal(record.order_total_quantity_kg)
            allocation_total = to_decimal(record.allocation_total_quantity_kg)
        else:
            order_total = calculate_order_total_quantity(record)
            allocation_total = calculate_allocation_total_quantity(record)
        is_balanced = abs(order_total - allocation_total) < Decimal('0.001')
        
        if is_balanced:
            return format_html(
                '<span class="status-badge status-balanced">برابر است</span>'
            )
        else:
            return format_html(
                '<span class="status-badge status-unbalanced">برابر نیست</span>'
            )
    
    def render_inquiry_status(self, value, record):
        """نمایش وضعیت استعلام"""
        # استفاده از مقدار annotate شده اگر موجود باشد
        if value is not None:
            all_inquired = bool(value)
        elif hasattr(record, 'all_inquired_status'):
            all_inquired = record.all_inquired_status
        else:
            # fallback: محاسبه دستی
            from core.AllocationFolder.AllocationModel import Allocation
            allocations = Allocation.objects.filter(order=record)
            all_inquired = all(alloc.allocation_status == 'pending_shipping' for alloc in allocations) if allocations.exists() else False
        
        if all_inquired:
            return format_html(
                '<span class="status-badge status-inquired">همه استعلام شده</span>'
            )
        else:
            return format_html(
                '<span class="status-badge status-not-inquired">در انتظار استعلام</span>'
            )
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            detail_url = reverse('sales:approve_allocation_detail', args=[record.order_number])
            
            return format_html(
                '<a href="{}" class="btn-outline-primary">مشاهده و تأیید</a>',
                detail_url
            )
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))

