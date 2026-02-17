import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from decimal import Decimal
from core.OrderFolder.OrderModel import Order
from core.helpers import check_field_access_prefer_edit
from core.decimal_utils import to_decimal


def to_persian_digits(text):
    """تبدیل اعداد انگلیسی به فارسی بدون کاما"""
    if text is None:
        return ''
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


def persian_number_with_comma(value):
    """فرمت کردن عدد با کاما و تبدیل به فارسی (برای مبالغ، اعشار ثابت)"""
    if value is None:
        return '-'
    d = to_decimal(value)
    formatted = f"{d.quantize(Decimal('1')):,.0f}"
    return to_persian_digits(formatted)


def has_rejected_transaction(record):
    """بررسی اینکه آیا تراکنش رد شده وجود دارد"""
    from core.SettlementFolder.SettlementModel import Settlement
    from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
    
    try:
        settlement = Settlement.objects.get(order=record)
        return settlement.transaction_documents.filter(approval_status='rejected').exists()
    except Settlement.DoesNotExist:
        return False


def get_row_class(record):
    """بررسی و برگرداندن کلاس CSS برای ردیف"""
    if has_rejected_transaction(record):
        return 'has-rejected-transaction'
    return ''


class TransactionReceiptOrderTable(tables.Table):
    """جدول لیست سفارش‌های در انتظار بارگذاری رسید تراکنش با استفاده از django-tables2"""
    
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
        from core.SettlementFolder.SettlementModel import Settlement as SettlementModel
        
        # superuser به همه فیلدها دسترسی دارد
        if user.is_superuser:
            return {
                'order_number': True,
                'order_type': True,
                'status': True,
                'registered_by': True,
                'original_document_amount': True,
                'remaining_amount': True,
                'customer_name': True,
                'customer_national_id': True,
                'actions': True,
            }
        
        # فیلدهایی که در لیست نمایش داده می‌شوند
        field_mapping = {
            'order_number': (OrderModel, 'order_number'),
            'order_type': (OrderModel, 'order_type'),
            'status': (OrderModel, 'status'),
            'registered_by': None,  # همیشه نمایش داده می‌شود
            'original_document_amount': (SettlementModel, 'original_document_amount'),
            'remaining_amount': None,  # محاسبه شده، همیشه نمایش داده می‌شود
            'customer_name': (PersonModel, 'name'),
            'customer_national_id': (PersonModel, 'national_id'),
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
    
    original_document_amount = tables.Column(
        verbose_name='مبلغ کل سند مبدا',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    remaining_amount = tables.Column(
        verbose_name='مبلغ باقیمانده',
        empty_values=(),
        orderable=False,
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
        empty_values=(),
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    customer_national_id = tables.Column(
        verbose_name='کد یا شناسه ملی مشتری',
        accessor='customer.national_id',
        orderable=True,
        order_by='customer__national_id',
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
        fields = ('order_number', 'order_type', 'status', 'customer_name', 'customer_national_id', 'original_document_amount', 'remaining_amount', 'registered_by', 'actions')
        attrs = {
            'class': 'data-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'order_type', 'status', 'customer_name', 'customer_national_id', 'original_document_amount', 'remaining_amount', 'registered_by', 'actions')
        row_attrs = {
            'class': get_row_class
        }
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش با رنگ قرمز اگر تراکنش رد شده وجود دارد"""
        persian_value = to_persian_digits(value) if value else '-'
        if has_rejected_transaction(record):
            return format_html('<strong style="color: #dc3545;">{}</strong>', persian_value)
        return format_html('<strong>{}</strong>', persian_value)
    
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
    
    def render_original_document_amount(self, value, record):
        """نمایش مبلغ کل سند مبدا"""
        from core.SettlementFolder.SettlementModel import Settlement
        try:
            # استفاده از prefetch_related که در view تنظیم شده
            # Django به صورت خودکار از prefetch_related استفاده می‌کند
            settlements = record.settlements.all()
            if settlements:
                settlement = settlements[0]
                if settlement.original_document_amount:
                    formatted_amount = persian_number_with_comma(settlement.original_document_amount)
                    return format_html('{} ریال', formatted_amount)
        except (AttributeError, IndexError):
            # در صورت بروز خطا، از query استفاده کن
            try:
                settlement = Settlement.objects.filter(order=record).first()
                if settlement and settlement.original_document_amount:
                    formatted_amount = persian_number_with_comma(settlement.original_document_amount)
                    return format_html('{} ریال', formatted_amount)
            except:
                pass
        return '-'
    
    def render_remaining_amount(self, value, record):
        """نمایش مبلغ باقیمانده"""
        from core.SettlementFolder.SettlementModel import Settlement
        try:
            # استفاده از prefetch_related که در view تنظیم شده
            settlements = record.settlements.all()
            if settlements:
                settlement = settlements[0]
                if settlement.original_document_amount:
                    # محاسبه مجموع همه تراکنش‌های موجود (چه تایید شده و چه نشده)
                    # استفاده از prefetch_related برای transaction_documents
                    documents = settlement.transaction_documents.all()
                    all_documents_total = sum(to_decimal(doc.document_amount) for doc in documents)
                    remaining = to_decimal(settlement.original_document_amount) - all_documents_total
                    formatted_amount = persian_number_with_comma(remaining)
                    return format_html('{} ریال', formatted_amount)
        except (AttributeError, IndexError):
            # در صورت بروز خطا، از query استفاده کن
            try:
                settlement = Settlement.objects.filter(order=record).prefetch_related('transaction_documents').first()
                if settlement and settlement.original_document_amount:
                    all_documents_total = settlement.transaction_documents.aggregate(total=Sum('document_amount'))['total'] or 0
                    remaining = to_decimal(settlement.original_document_amount) - to_decimal(all_documents_total)
                    formatted_amount = persian_number_with_comma(remaining)
                    return format_html('{} ریال', formatted_amount)
            except:
                pass
        return '-'
    
    def render_customer_name(self, value, record):
        """نمایش نام مشتری"""
        if value:
            return value
        if record.customer:
            return record.customer.name if hasattr(record.customer, 'name') else '-'
        return '-'
    
    def render_customer_national_id(self, value, record):
        """نمایش کد یا شناسه ملی مشتری"""
        if value:
            return to_persian_digits(value)
        if record.customer:
            national_id = record.customer.national_id if hasattr(record.customer, 'national_id') else None
            return to_persian_digits(national_id) if national_id else '-'
        return '-'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        try:
            upload_url = reverse('sales:transaction_receipt_upload', args=[record.order_number])
            
            if has_rejected_transaction(record):
                html = format_html(
                    '<a href="{}" class="btn-outline-info" title="ثبت رسید تراکنش">ثبت رسید تراکنش</a><br><small style="color: #dc3545; font-weight: 600; display: block; margin-top: 5px;">⚠️ تراکنش رد شده دارد - باید ویرایش شود</small>',
                    upload_url
                )
            else:
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
            'class': 'data-table searchable-table',
            'thead': {'class': ''}
        }
        sequence = ('order_number', 'customer', 'created_at', 'actions')
        row_attrs = {
            'class': lambda record: 'has-rejected-transaction' if hasattr(record, '_has_rejected') and record._has_rejected else ''
        }
    
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
            
            # بررسی اینکه آیا تراکنش رد شده وجود دارد
            from core.SettlementFolder.SettlementModel import Settlement
            from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
            
            has_rejected = False
            try:
                settlement = Settlement.objects.get(order=record)
                has_rejected = settlement.transaction_documents.filter(approval_status='rejected').exists()
            except Settlement.DoesNotExist:
                pass
            
            html = format_html(
                '<a href="{}" class="btn-outline-info" title="مشاهده و تأیید">مشاهده و تأیید</a>',
                detail_url
            )
            return html
        except Exception as e:
            # در صورت بروز خطا، یک پیام خطا برگردان
            return format_html('<span style="color: red;">خطا: {}</span>', str(e))
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش با رنگ قرمز اگر تراکنش رد شده وجود دارد"""
        # بررسی اینکه آیا تراکنش رد شده وجود دارد
        from core.SettlementFolder.SettlementModel import Settlement
        from core.SettlementFolder.TransactionDocumentModel import TransactionDocument
        
        has_rejected = False
        try:
            settlement = Settlement.objects.get(order=record)
            has_rejected = settlement.transaction_documents.filter(approval_status='rejected').exists()
        except Settlement.DoesNotExist:
            pass
        
        if has_rejected:
            return format_html('<strong style="color: #dc3545;">{}</strong>', value)
        return format_html('<strong>{}</strong>', value)


