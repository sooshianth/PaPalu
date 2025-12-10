import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport


class UploadFarePaymentDocsTable(tables.Table):
    """جدول لیست حمل‌های در انتظار بارگذاری اسناد پرداخت"""
    
    transport_number = tables.Column(
        verbose_name='شماره حمل',
        linkify=lambda record: ('accounting:upload_fare_payment_docs_detail', {'transport_number': record.transport_number}) if record.transport_number else None,
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order = tables.Column(
        verbose_name='شماره سفارش',
        accessor='purchase_order__order_number',
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
        model = PurchaseTransport
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
        materials = record.purchase_order.materials.select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials]
            if len(names) > 2:
                return format_html('{}, ...', ', '.join(names[:2]))
            return ', '.join(names)
        return '—'
    
    def render_transport_number(self, value):
        """نمایش شماره حمل به صورت bold"""
        if value:
            return format_html('<strong>{}</strong>', value)
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
        detail_url = reverse('accounting:upload_fare_payment_docs_detail', kwargs={'transport_number': record.transport_number})
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">جزئیات</a>',
            detail_url
        )
