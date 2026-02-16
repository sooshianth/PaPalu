import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.utils.safestring import mark_safe
from distribution.plate_display import render_iran_plate_html


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


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
            'class': 'data-table searchable-table',
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
                    '<a href="{}" class="btn-outline-primary" target="_blank">چاپ بارنامه</a>',
                    reverse('distribution:print_waybill_pdf', args=[transport.waybill_number])
                )
            )
            
            # دکمه خودرو خارج شد - باز کردن modal
            buttons.append(
                format_html(
                    '<button type="button" class="btn-outline-primary" onclick="showExitConfirmModal(\'{}\')">خودرو خارج شد</button>',
                    transport.waybill_number
                )
            )
            
            return format_html(
                '<div style="display: flex; gap: 5px; flex-wrap: wrap; justify-content: center;">{}</div>',
                mark_safe(''.join(str(button) for button in buttons))
            )
        except Exception as e:
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))

