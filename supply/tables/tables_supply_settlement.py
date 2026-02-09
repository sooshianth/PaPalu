import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from decimal import Decimal
from core.OrderFolder.OrderModel import Order


class PendingSupplySettlementOrderTable(tables.Table):
    """جدول سفارش‌های خرید در انتظار تسویه"""
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        accessor='order_number',
        orderable=True
    )
    
    supplier_name = tables.Column(
        verbose_name='تأمین‌کننده',
        accessor='customer__name',
        orderable=True
    )
    
    order_weight = tables.Column(
        verbose_name='وزن سفارش (کیلوگرم)',
        accessor='_order_weight',
        orderable=False
    )
    
    delivered_weight = tables.Column(
        verbose_name='وزن تحویلی (کیلوگرم)',
        accessor='_delivered_weight',
        orderable=False
    )
    
    difference_amount = tables.Column(
        verbose_name='مبلغ اختلاف (ریال)',
        accessor='_difference_amount',
        orderable=False
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        orderable=False,
        empty_values=()
    )
    
    class Meta:
        model = Order
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('order_number', 'supplier_name', 'order_weight', 'delivered_weight', 'difference_amount', 'actions')
        attrs = {
            'class': 'table table-striped table-hover'
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.accessible_fields = kwargs.pop('accessible_fields', {})
        super().__init__(*args, **kwargs)
    
    def render_order_number(self, value, record):
        """رندر شماره سفارش"""
        if self.accessible_fields.get('order_number', False):
            return format_html('<strong>{}</strong>', value)
        return '-'
    
    def render_supplier_name(self, value, record):
        """رندر نام تأمین‌کننده"""
        if self.accessible_fields.get('supplier_name', False):
            return format_html('{}', value or '-')
        return '-'
    
    def render_order_weight(self, value, record):
        """رندر وزن سفارش (اعشار ثابت)"""
        if self.accessible_fields.get('order_weight', False):
            d = Decimal(str(value or 0)).quantize(Decimal('0.01'))
            return format_html('{:,.2f}', d)
        return '-'
    
    def render_delivered_weight(self, value, record):
        """رندر وزن تحویلی (اعشار ثابت)"""
        if self.accessible_fields.get('delivered_weight', False):
            d = Decimal(str(value or 0)).quantize(Decimal('0.01'))
            return format_html('{:,.2f}', d)
        return '-'
    
    def render_difference_amount(self, value, record):
        """رندر مبلغ اختلاف (اعشار ثابت)"""
        if self.accessible_fields.get('difference_amount', False):
            amount = Decimal(str(value or 0)).quantize(Decimal('1'))
            if amount > 0:
                # سرک (مثبت) - سبز
                return format_html(
                    '<span style="color: #28a745; font-weight: 600;">{:,.0f} ریال</span>',
                    amount
                )
            elif amount < 0:
                # کسری (منفی) - قرمز
                return format_html(
                    '<span style="color: #dc3545; font-weight: 600;">{:,.0f} ریال</span>',
                    amount
                )
            else:
                return format_html('<span>۰ ریال</span>')
        return '-'
    
    def render_actions(self, value, record):
        """رندر دکمه‌های عملیات"""
        if self.accessible_fields.get('actions', False):
            detail_url = reverse('supply:supply_settlement_detail', kwargs={'order_number': record.order_number})
            return format_html(
                '<a href="{}" class="btn btn-sm btn-primary">جزئیات تسویه</a>',
                detail_url
            )
        return '-'


class PendingSupplySettlementApprovalOrderTable(tables.Table):
    """جدول سفارش‌های خرید در انتظار تایید تسویه کامل"""
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        accessor='order_number',
        orderable=True
    )
    
    supplier_name = tables.Column(
        verbose_name='تأمین‌کننده',
        accessor='customer__name',
        orderable=True
    )
    
    order_weight = tables.Column(
        verbose_name='وزن سفارش (کیلوگرم)',
        accessor='_order_weight',
        orderable=False
    )
    
    delivered_weight = tables.Column(
        verbose_name='وزن تحویلی (کیلوگرم)',
        accessor='_delivered_weight',
        orderable=False
    )
    
    difference_amount = tables.Column(
        verbose_name='مبلغ اختلاف (ریال)',
        accessor='_difference_amount',
        orderable=False
    )
    
    settled_amount = tables.Column(
        verbose_name='مبلغ تسویه شده (ریال)',
        accessor='_settled_amount',
        orderable=False
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        orderable=False,
        empty_values=()
    )
    
    class Meta:
        model = Order
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('order_number', 'supplier_name', 'order_weight', 'delivered_weight', 'difference_amount', 'settled_amount', 'actions')
        attrs = {
            'class': 'table table-striped table-hover'
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.accessible_fields = kwargs.pop('accessible_fields', {})
        super().__init__(*args, **kwargs)
    
    def render_order_number(self, value, record):
        """رندر شماره سفارش"""
        if self.accessible_fields.get('order_number', False):
            return format_html('<strong>{}</strong>', value)
        return '-'
    
    def render_supplier_name(self, value, record):
        """رندر نام تأمین‌کننده"""
        if self.accessible_fields.get('supplier_name', False):
            return format_html('{}', value or '-')
        return '-'
    
    def render_order_weight(self, value, record):
        """رندر وزن سفارش (اعشار ثابت)"""
        if self.accessible_fields.get('order_weight', False):
            d = Decimal(str(value or 0)).quantize(Decimal('0.01'))
            return format_html('{:,.2f}', d)
        return '-'
    
    def render_delivered_weight(self, value, record):
        """رندر وزن تحویلی (اعشار ثابت)"""
        if self.accessible_fields.get('delivered_weight', False):
            d = Decimal(str(value or 0)).quantize(Decimal('0.01'))
            return format_html('{:,.2f}', d)
        return '-'
    
    def render_difference_amount(self, value, record):
        """رندر مبلغ اختلاف (اعشار ثابت)"""
        if self.accessible_fields.get('difference_amount', False):
            amount = Decimal(str(value or 0)).quantize(Decimal('1'))
            if amount > 0:
                # سرک (مثبت) - سبز
                return format_html(
                    '<span style="color: #28a745; font-weight: 600;">{:,.0f} ریال</span>',
                    amount
                )
            elif amount < 0:
                # کسری (منفی) - قرمز
                return format_html(
                    '<span style="color: #dc3545; font-weight: 600;">{:,.0f} ریال</span>',
                    amount
                )
            else:
                return format_html('<span>۰ ریال</span>')
        return '-'
    
    def render_settled_amount(self, value, record):
        """رندر مبلغ تسویه شده (اعشار ثابت)"""
        if self.accessible_fields.get('settled_amount', False):
            d = Decimal(str(value or 0)).quantize(Decimal('1'))
            return format_html(
                '<span style="color: #28a745; font-weight: 600;">{:,.0f} ریال</span>',
                d
            )
        return '-'
    
    def render_actions(self, value, record):
        """رندر دکمه‌های عملیات"""
        if self.accessible_fields.get('actions', False):
            detail_url = reverse('supply:supply_settlement_approval_detail', kwargs={'order_number': record.order_number})
            return format_html(
                '<a href="{}" class="btn btn-sm btn-success">جزئیات تایید</a>',
                detail_url
            )
        return '-'
