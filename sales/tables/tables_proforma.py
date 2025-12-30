import django_tables2 as tables
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.OrderModel import Order
from core.helpers import check_field_access_prefer_edit
import json
import html


class ProformaTable(tables.Table):
    """جدول لیست پیش فاکتورها با استفاده از django-tables2"""
    
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
        from core.OrderFolder.ProformaModel import Proforma as ProformaModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'proforma_number': True,
                'order': True,
                'customer': True,
                'validity_date': True,
                'created_at': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'proforma_number': (ProformaModel, 'proforma_number'),
            'order': (ProformaModel, 'order'),
            'customer': (ProformaModel, 'customer'),
            'validity_date': (ProformaModel, 'validity_date'),
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
    
    proforma_number = tables.Column(
        verbose_name='شماره پیش فاکتور',
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
    
    validity_date = tables.Column(
        verbose_name='تاریخ اعتبار',
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
        model = Proforma
        template_name = 'django_tables2/bootstrap.html'
        fields = ('proforma_number', 'order', 'customer', 'validity_date', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('proforma_number', 'order', 'customer', 'validity_date', 'created_at', 'actions')
    
    def render_proforma_number(self, value, record):
        """نمایش شماره پیش فاکتور"""
        proforma_number = value if value else record.id
        invalidated_icon = ''
        if hasattr(record, 'is_invalidated') and record.is_invalidated:
            invalidated_icon = format_html(
                ' <span class="invalidated-icon" title="این پیش فاکتور به دلیل ویرایش سفارش منسوخ شده است">✕</span>'
            )
        if value:
            return format_html('<span class="badge badge-success">{}</span>{}', value, invalidated_icon)
        return format_html('<span class="badge badge-success">{}</span>{}', record.id, invalidated_icon)
    
    def render_order(self, value, record):
        """نمایش شماره سفارش"""
        invalidated_icon = ''
        if hasattr(record, 'is_invalidated') and record.is_invalidated:
            invalidated_icon = format_html(
                ' <span class="invalidated-icon" title="این پیش فاکتور به دلیل ویرایش سفارش منسوخ شده است"> ✕</span>'
            )
        if value:
            return format_html('<span class="badge badge-success">{}</span>{}', value, invalidated_icon)
        return format_html('-{}', invalidated_icon)
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        return value if value else '-'
    
    def render_validity_date(self, value, record):
        """نمایش تاریخ اعتبار"""
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
            detail_url = reverse('sales:proforma_detail', args=[record.id])
            pdf_url = reverse('sales:proforma_download_pdf', args=[record.id])
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-info" title="جزئیات">جزئیات</a>'
                '<a href="{}" class="btn-outline-success" title="دانلود PDF" style="margin-right: 5px;">دانلود PDF</a>'
                '</div>',
                detail_url,
                pdf_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))


class ApproveProformaTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار آپلود پیش فاکتور مشتری با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        accessor='order.order_number',
        orderable=True,
        order_by='order__order_number',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    proforma_number = tables.Column(
        verbose_name='شماره پیش فاکتور',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    customer = tables.Column(
        verbose_name='مشتری',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    created_at = tables.Column(
        verbose_name='تاریخ ایجاد',
        accessor='order.created_at',
        orderable=True,
        order_by='order__created_at',
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    file_status = tables.Column(
        verbose_name='وضعیت فایل',
        empty_values=(),
        orderable=False,
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
        fields = ('order_number', 'proforma_number', 'customer', 'created_at', 'file_status', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'proforma_number', 'customer', 'created_at', 'file_status', 'actions')
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش"""
        # اگر value وجود نداشت، از record استفاده کن
        if not value:
            if isinstance(record, dict):
                order = record.get('order', None)
            else:
                order = getattr(record, 'order', None)
            
            if order:
                value = getattr(order, 'order_number', None) if hasattr(order, 'order_number') else None
        
        if value:
            return format_html('<span class="badge badge-success">{}</span>', value)
        return '-'
    
    def render_proforma_number(self, record):
        """نمایش شماره پیش فاکتور"""
        # record می‌تواند دیکشنری یا object باشد
        if isinstance(record, dict):
            proforma = record.get('proforma', None)
        else:
            proforma = getattr(record, 'proforma', None)
        
        if proforma:
            proforma_number = getattr(proforma, 'proforma_number', None) if hasattr(proforma, 'proforma_number') else None
            if proforma_number:
                return format_html('<span class="badge badge-success">{}</span>', proforma_number)
        return '-'
    
    def render_customer(self, record):
        """نمایش نام مشتری"""
        # record می‌تواند دیکشنری یا object باشد
        if isinstance(record, dict):
            proforma = record.get('proforma', None)
        else:
            proforma = getattr(record, 'proforma', None)
        
        if proforma:
            customer = getattr(proforma, 'customer', None) if hasattr(proforma, 'customer') else None
            if customer:
                customer_name = getattr(customer, 'name', None) if hasattr(customer, 'name') else None
                if customer_name:
                    return customer_name
        return '-'
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        # اگر value وجود نداشت، از record استفاده کن
        if not value:
            if isinstance(record, dict):
                order = record.get('order', None)
            else:
                order = getattr(record, 'order', None)
            
            if order:
                value = getattr(order, 'created_at', None) if hasattr(order, 'created_at') else None
        
        if value:
            try:
                # برای jDateTimeField از strftime استفاده می‌کنیم
                return value.strftime('%Y/%m/%d')
            except (AttributeError, TypeError):
                # اگر strftime کار نکرد، از str استفاده می‌کنیم
                return str(value)
        return '-'
    
    def render_file_status(self, record):
        """نمایش وضعیت فایل"""
        # record می‌تواند دیکشنری یا object باشد
        if isinstance(record, dict):
            has_file = record.get('has_confirmation_file', False)
        else:
            has_file = getattr(record, 'has_confirmation_file', False)
        
        if has_file:
            return format_html(
                '<div class="file-status uploaded">'
                '<svg style="width: 20px; height: 20px;" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
                '</svg>'
                '<span>آپلود شده</span>'
                '</div>'
            )
        else:
            return format_html(
                '<div class="file-status not-uploaded">'
                '<svg style="width: 20px; height: 20px;" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<path d="M12 8V12M12 16H12.01M21 12C21 16.9706 16.9706 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C16.9706 3 21 7.02944 21 12Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
                '</svg>'
                '<span>آپلود نشده</span>'
                '</div>'
            )
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            # record می‌تواند دیکشنری یا object باشد
            if isinstance(record, dict):
                order = record.get('order', None)
                proforma = record.get('proforma', None)
                order_document = record.get('order_document', None)
                has_file = record.get('has_confirmation_file', False)
            else:
                order = getattr(record, 'order', None)
                proforma = getattr(record, 'proforma', None)
                order_document = getattr(record, 'order_document', None)
                has_file = getattr(record, 'has_confirmation_file', False)
            
            if not order:
                return '-'
            
            order_number = getattr(order, 'order_number', None) if hasattr(order, 'order_number') else None
            if not order_number:
                return '-'
            
            # دریافت شماره پیش فاکتور
            proforma_number = '-'
            if proforma:
                proforma_number = getattr(proforma, 'proforma_number', None) if hasattr(proforma, 'proforma_number') else None
                if not proforma_number:
                    proforma_number = '-'
            
            # دریافت نام مشتری
            customer_name = '-'
            if proforma:
                customer = getattr(proforma, 'customer', None) if hasattr(proforma, 'customer') else None
                if customer:
                    customer_name = getattr(customer, 'name', None) if hasattr(customer, 'name') else None
                    if not customer_name:
                        customer_name = '-'
            
            # دریافت URL فایل
            file_url = ''
            if has_file and order_document:
                attachment = getattr(order_document, 'proforma_confirmation_attachment', None) if hasattr(order_document, 'proforma_confirmation_attachment') else None
                if attachment:
                    try:
                        file_url = attachment.url
                    except:
                        file_url = ''
            
            # Escape کردن مقادیر برای JavaScript - استفاده از HTML entity
            order_number_str = html.escape(str(order_number))
            proforma_number_str = html.escape(str(proforma_number))
            customer_name_str = html.escape(str(customer_name))
            has_file_str = 'true' if has_file else 'false'
            file_url_str = html.escape(str(file_url))
            
            # ایجاد HTML برای دکمه‌ها با data attributes
            buttons_html = '<div class="btn-group">'
            buttons_html += (
                f'<a href="#" class="btn-outline-success" '
                f'data-order-number="{order_number_str}" '
                f'data-proforma-number="{proforma_number_str}" '
                f'data-customer-name="{customer_name_str}" '
                f'data-has-file="{has_file_str}" '
                f'data-file-url="{file_url_str}" '
                f'onclick="event.preventDefault(); event.stopPropagation(); '
                f'openUploadModal(this.getAttribute(\'data-order-number\'), '
                f'this.getAttribute(\'data-proforma-number\'), '
                f'this.getAttribute(\'data-customer-name\'), '
                f'this.getAttribute(\'data-has-file\') === \'true\', '
                f'this.getAttribute(\'data-file-url\')); return false;">'
                f'آپلود فایل</a>'
            )
            
            if has_file and order_document:
                attachment = getattr(order_document, 'proforma_confirmation_attachment', None) if hasattr(order_document, 'proforma_confirmation_attachment') else None
                if attachment:
                    try:
                        buttons_html += f'<a href="{attachment.url}" class="btn-outline-info" target="_blank" style="margin-right: 5px;">دانلود</a>'
                    except:
                        pass
            
            buttons_html += '</div>'
            return mark_safe(buttons_html)
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            import traceback
            error_msg = f'{str(e)} - {traceback.format_exc()}'
            return format_html('<span style="color: red;">خطا: {}</span>', error_msg)


class PendingProformaOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار صدور پیش فاکتور با استفاده از django-tables2"""
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
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
        if value:
            return format_html('<span class="badge badge-success">{}</span>', value)
        return '-'
    
    def render_customer(self, value, record):
        """نمایش نام مشتری"""
        return value if value else '-'
    
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
        """نمایش دکمه ایجاد پیش فاکتور"""
        try:
            create_url = reverse('sales:proforma_create') + f'?order_number={record.order_number}'
            
            html = format_html(
                '<div class="btn-group">'
                '<a href="{}" class="btn-outline-success" title="ایجاد پیش فاکتور">ایجاد پیش فاکتور</a>'
                '</div>',
                create_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
