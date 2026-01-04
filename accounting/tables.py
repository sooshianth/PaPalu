import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from core.TransportFolder.TransportModel import Transport


class UploadFarePaymentDocsTable(tables.Table):
    """جدول لیست حمل‌های در انتظار بارگذاری اسناد پرداخت"""
    
    def __init__(self, *args, detail_url_name='accounting:upload_fare_payment_docs_detail', **kwargs):
        super().__init__(*args, **kwargs)
        self.detail_url_name = detail_url_name
    
    transport_number = tables.Column(
        verbose_name='شماره حمل',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order = tables.Column(
        verbose_name='شماره سفارش',
        accessor='allocation.order.order_number',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    raw_materials = tables.Column(
        verbose_name='نوع ماده اولیه',
        orderable=False,
        empty_values=(),
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    net_weight = tables.Column(
        verbose_name='مقدار تحویلی (خالص)',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    freight_payment = tables.Column(
        verbose_name='کرایه پرداختی نهایی',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت حمل',
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
        model = Transport
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('transport_number', 'purchase_order', 'raw_materials', 'net_weight', 'freight_payment', 'status', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'id': 'uploadFarePaymentDocsTable',
            'style': 'border-collapse:collapse;font-size:.88rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('transport_number', 'purchase_order', 'raw_materials', 'net_weight', 'freight_payment', 'status', 'actions')
    
    def render_raw_materials(self, record):
        """نمایش مواد اولیه سفارش"""
        if not record.purchase_order:
            return '—'
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials if m.raw_material]
            if len(names) > 2:
                return format_html('{}, ...', ', '.join(names[:2]))
            return ', '.join(names) if names else '—'
        return '—'
    
    def render_transport_number(self, value, record):
        """نمایش شماره حمل به صورت bold با لینک"""
        if value:
            detail_url = reverse(self.detail_url_name, kwargs={'transport_number': value})
            return format_html('<strong><a href="{}">{}</a></strong>', detail_url, value)
        return '—'
    
    def render_net_weight(self, value):
        """نمایش وزن خالص با فرمت عددی"""
        if value:
            formatted_value = '{:,.2f}'.format(float(value))
            return format_html('<span dir="ltr">{}</span> کیلوگرم', formatted_value)
        return '—'
    
    def render_freight_payment(self, value):
        """نمایش کرایه پرداختی نهایی (جهت کنترل)"""
        if value:
            formatted_value = '{:,.0f}'.format(float(value))
            return format_html('<span dir="ltr">{}</span> ریال', formatted_value)
        return '—'
    
    def render_status(self, record):
        """نمایش وضعیت حمل"""
        return record.get_status_display()
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        if not record.transport_number:
            return format_html('<span class="text-muted">شماره حمل ناموجود</span>')
        detail_url = reverse(self.detail_url_name, kwargs={'transport_number': record.transport_number})
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">جزئیات</a>',
            detail_url
        )
