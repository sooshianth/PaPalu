import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from core.OrderFolder.InvoiceModel import Invoice
from core.helpers import check_field_access_prefer_edit
import json
import html


class InvoiceTable(tables.Table):
    """جدول لیست فاکتورها با استفاده از django-tables2"""
    
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
        from core.OrderFolder.InvoiceModel import Invoice as InvoiceModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'tax_invoice_number': True,
                'order': True,
                'customer': True,
                'issue_date': True,
                'created_at': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'tax_invoice_number': (InvoiceModel, 'tax_invoice_number'),
            'order': (InvoiceModel, 'order'),
            'customer': (InvoiceModel, 'customer'),
            'issue_date': (InvoiceModel, 'issue_date'),
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
    

    tax_invoice_number = tables.Column(
        verbose_name='شماره صورتحساب مالیاتی',
        orderable=True,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    order = tables.Column(
        verbose_name='شماره سفارش',
        accessor='order.order_number',
        orderable=True,
        order_by='order__order_number',
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
    
    issue_date = tables.Column(
        verbose_name='تاریخ صدور',
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
        model = Invoice
        template_name = 'django_tables2/bootstrap.html'
        fields = ('tax_invoice_number', 'order', 'customer', 'issue_date', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('tax_invoice_number', 'order', 'customer', 'issue_date', 'created_at', 'actions')
    
    def render_tax_invoice_number(self, value, record):
        """نمایش شماره صورتحساب مالیاتی"""
        if value:
            return format_html('<span class="badge badge-success">{}</span>', value)
        return format_html('<span class="badge badge-success">{}</span>', record.id)
    
    def render_order(self, value, record):
        """نمایش شماره سفارش"""
        if value:
            return format_html('<span class="badge badge-success">{}</span>', value)
        return '-'
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        return value if value else '-'
    
    def render_issue_date(self, value, record):
        """نمایش تاریخ صدور"""
        if value:
            try:
                # برای jDateField از strftime استفاده می‌کنیم
                return value.strftime('%Y/%m/%d')
            except (AttributeError, TypeError):
                # اگر strftime کار نکرد، از str استفاده می‌کنیم
                return str(value)
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
            detail_url = reverse('sales:invoice_detail', args=[record.id])
            download_url = reverse('sales:invoice_download_pdf', args=[record.id])
            
            # بررسی اینکه آیا اطلاعات فاکتور کامل است
            is_complete = (
                record.order is not None and
                record.tax_invoice_number is not None and
                record.tax_invoice_number.strip() != '' and
                record.customer_tax_type is not None and
                record.issue_date is not None and
                record.customer is not None and
                record.company is not None
            )
            
            if is_complete:
                html = format_html(
                    '<div class="btn-group">'
                    '<a href="{}" class="btn-outline-info" title="جزئیات">جزئیات</a>'
                    '<a href="{}" class="btn-outline-info" style="color: #28a745; border-color: #28a745;" title="دانلود PDF">دانلود PDF</a>'
                    '</div>',
                    detail_url,
                    download_url
                )
            else:
                html = format_html(
                    '<div class="btn-group">'
                    '<a href="{}" class="btn-outline-info" title="جزئیات">جزئیات</a>'
                    '<a href="{}" class="btn-outline-info" style="opacity: 0.5; cursor: not-allowed; color: #28a745; border-color: #28a745;" title="لطفاً ابتدا اطلاعات فاکتور را تکمیل کنید" onclick="event.preventDefault();">دانلود PDF</a>'
                    '</div>',
                    detail_url,
                    download_url
                )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


