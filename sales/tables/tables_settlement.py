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


class UnloadApprovalOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار تایید تخلیه با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        # دریافت اطلاعات دسترسی فیلدها
        self.accessible_fields = kwargs.pop('accessible_fields', None)
        user = kwargs.pop('user', None)
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and user is not None:
            self.accessible_fields = self._get_accessible_fields(user)
        
        # اضافه کردن ستون‌های غیرقابل دسترس به exclude قبل از super().__init__()
        if self.accessible_fields:
            exclude_columns = [col for col, access in self.accessible_fields.items() if not access]
            if exclude_columns:
                existing_exclude = list(getattr(self._meta, 'exclude', []) or [])
                existing_exclude.extend(exclude_columns)
                self._meta.exclude = tuple(existing_exclude)
        
        super().__init__(*args, **kwargs)
    
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
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and user is not None:
            self.accessible_fields = self._get_accessible_fields(user)
        
        # اضافه کردن ستون‌های غیرقابل دسترس به exclude قبل از super().__init__()
        if self.accessible_fields:
            exclude_columns = [col for col, access in self.accessible_fields.items() if not access]
            if exclude_columns:
                existing_exclude = list(getattr(self._meta, 'exclude', []) or [])
                existing_exclude.extend(exclude_columns)
                self._meta.exclude = tuple(existing_exclude)
        
        super().__init__(*args, **kwargs)
    
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
        
        # اگر accessible_fields داده نشده و user داده شده، محاسبه کن
        if self.accessible_fields is None and user is not None:
            self.accessible_fields = self._get_accessible_fields(user)
        
        # اضافه کردن ستون‌های غیرقابل دسترس به exclude قبل از super().__init__()
        if self.accessible_fields:
            exclude_columns = [col for col, access in self.accessible_fields.items() if not access]
            if exclude_columns:
                existing_exclude = list(getattr(self._meta, 'exclude', []) or [])
                existing_exclude.extend(exclude_columns)
                self._meta.exclude = tuple(existing_exclude)
        
        super().__init__(*args, **kwargs)
    
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
