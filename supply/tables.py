import django_tables2 as tables
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrder


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


class SupplierTable(tables.Table):
    """جدول لیست تأمین‌کنندگان با استفاده از django-tables2"""
    
    national_id = tables.Column(
        verbose_name='کد ملی',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    name = tables.Column(
        verbose_name='نام تأمین‌کننده',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    nature = tables.Column(
        verbose_name='نوع',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    registration_number = tables.Column(
        verbose_name='شماره ثبت',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    phone_number = tables.Column(
        verbose_name='شماره تلفن',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if accessible_fields:
            self.columns['national_id'].column.visible = accessible_fields.get('national_id', False)
            self.columns['name'].column.visible = accessible_fields.get('name', False)
            self.columns['nature'].column.visible = accessible_fields.get('nature', False)
            self.columns['registration_number'].column.visible = accessible_fields.get('registration_number', False)
            self.columns['phone_number'].column.visible = accessible_fields.get('phone_number', False)
            # Always show actions column if any field is visible
            self.columns['actions'].column.visible = any(accessible_fields.values())
    
    class Meta:
        model = Person
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('national_id', 'name', 'nature', 'registration_number', 'phone_number', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'id': 'suppliersTable',
            'style': 'border-collapse:collapse;font-size:.88rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('national_id', 'name', 'nature', 'registration_number', 'phone_number', 'actions')
    
    def render_name(self, value):
        """نمایش نام به صورت bold"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_nature(self, value):
        """نمایش نوع شخص به صورت badge"""
        if value == 'legal':
            return format_html('<span class="badge badge-legal">حقوقی</span>')
        elif value == 'natural':
            return format_html('<span class="badge badge-natural">حقیقی</span>')
        return '—'
    
    def render_registration_number(self, value):
        """نمایش شماره ثبت یا خط تیره"""
        return value or '—'
    
    def render_phone_number(self, value):
        """نمایش شماره تلفن یا خط تیره"""
        return value or '—'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        detail_url = reverse('supply:supplier_detail', args=[record.national_id])
        return format_html(
            '<div class="btn-group">'
            '<a href="{}" class="btn btn-info btn-sm">جزئیات</a>'
            '</div>',
            detail_url
        )


class ProcurementPurchaseOrderTable(tables.Table):
    """جدول سفارش‌های خرید procurement با استفاده از django-tables2"""
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت فعلی',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    materials_list = tables.Column(
        verbose_name='نام مواد اولیه',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    supplier = tables.Column(
        verbose_name='نام تأمین‌کننده',
        accessor='supplier.name',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_by = tables.Column(
        verbose_name='کاربر ثبت کننده',
        accessor='created_by',
        orderable=True,
        empty_values=(),
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_at = tables.DateTimeColumn(
        verbose_name='تاریخ ایجاد',
        format='Y-m-d',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if accessible_fields:
            # Show columns based on field access permissions
            self.columns['order_number'].column.visible = accessible_fields.get('order_number', False)
            self.columns['status'].column.visible = accessible_fields.get('status', False)
            # materials_list requires checking both ProcurementPurchaseOrderMaterial.raw_material and RawMaterial.name
            self.columns['materials_list'].column.visible = accessible_fields.get('materials_list', False)
            self.columns['supplier'].column.visible = accessible_fields.get('supplier', False)
            self.columns['created_by'].column.visible = accessible_fields.get('created_by', False)
            self.columns['created_at'].column.visible = accessible_fields.get('created_at', False)
            # Always show actions if any field is visible
            self.columns['actions'].column.visible = any(accessible_fields.values())
    
    class Meta:
        model = ProcurementPurchaseOrder
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('order_number', 'status', 'materials_list', 'supplier', 'created_by', 'created_at', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.85rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('order_number', 'status', 'materials_list', 'supplier', 'created_by', 'created_at', 'actions')
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        status_class = f'status-{record.status}'
        return format_html(
            '<span class="status-badge {}">{}</span>',
            status_class,
            record.get_status_display()
        )
    
    def render_materials_list(self, record):
        """نمایش لیست مواد اولیه با جزئیات FK از RawMaterial"""
        materials = record.materials.select_related('raw_material').all()
        if materials:
            items = []
            for m in materials:
                rm = m.raw_material
                # نمایش: شناسه - نام (شکل فیزیکی)
                display_text = f"{rm.raw_material_id or 'N/A'} - {rm.name or 'بدون نام'}"
                if rm.physical_form:
                    display_text += f" ({rm.get_physical_form_display()})"
                items.append((display_text,))
            
            inner_html = format_html_join(
                '',
                '<div style="padding:4px 8px;background:#e3f2fd;border-radius:4px;margin:2px;font-size:0.75rem;border-right:3px solid #1976d2">{}</div>',
                items
            )
            return format_html('<div style="display:flex;flex-direction:column;gap:2px">{}</div>', inner_html)
        return '—'
    
    def render_supplier(self, value):
        """نمایش نام تأمین‌کننده"""
        return value or '—'
    
    def render_created_by(self, record):
        """نمایش نام کاربر ثبت کننده"""
        if record.created_by:
            return record.created_by.get_full_name() or record.created_by.username
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        detail_url = reverse('supply:procurement_purchase_order_detail', args=[record.order_number])
        return format_html(
            '<a href="{}" class="btn btn-secondary btn-sm">جزئیات</a>',
            detail_url
        )


class RepresentativeTable(tables.Table):
    """جدول نمایندگان"""
    
    name = tables.Column(verbose_name='نام', orderable=True)
    position = tables.Column(verbose_name='سمت', orderable=False)
    mobile_number = tables.Column(verbose_name='موبایل', orderable=False)
    phone_number = tables.Column(verbose_name='تلفن', orderable=False)
    confirmation_letter = tables.Column(verbose_name='نامه تایید', empty_values=(), orderable=False)
    
    class Meta:
        model = Representative
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('name', 'position', 'mobile_number', 'phone_number', 'confirmation_letter')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'font-size:.88rem'
        }
    
    def render_position(self, value):
        return value or '—'
    
    def render_mobile_number(self, value):
        return value or '—'
    
    def render_phone_number(self, value):
        return value or '—'
    
    def render_confirmation_letter(self, record):
        if record.confirmation_letter:
            return format_html('<a href="{}" target="_blank">مشاهده</a>', record.confirmation_letter.url)
        return '—'


class BankAccountTable(tables.Table):
    """جدول حساب‌های بانکی"""
    
    bank_name = tables.Column(verbose_name='بانک', orderable=False)
    account_number = tables.Column(verbose_name='شماره حساب', orderable=False)
    shaba_number = tables.Column(verbose_name='شماره شبا', orderable=False)
    
    class Meta:
        model = BankAccount
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('bank_name', 'account_number', 'shaba_number')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'font-size:.88rem'
        }
    
    def render_bank_name(self, value):
        return value or '—'
    
    def render_account_number(self, value):
        return value or '—'
    
    def render_shaba_number(self, value):
        return value or '—'


class PaymentPreferenceTable(tables.Table):
    """جدول ترجیحات پرداخت"""
    
    payment_method = tables.Column(verbose_name='روش', orderable=False)
    payment_term_days = tables.Column(verbose_name='شرایط (روز)', orderable=False)
    credit_limit = tables.Column(verbose_name='سقف اعتبار (ریال)', orderable=False)
    notes = tables.Column(verbose_name='توضیحات', orderable=False)
    
    class Meta:
        model = PaymentPreference
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('payment_method', 'payment_term_days', 'credit_limit', 'notes')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'font-size:.88rem'
        }
    
    def render_payment_method(self, record):
        return record.get_payment_method_display() or '—'
    
    def render_payment_term_days(self, value):
        return value or '—'
    
    def render_credit_limit(self, value):
        if value:
            return format_number_persian(value, decimal_places=0)
        return '—'
    
    def render_notes(self, value):
        return value or '—'


class SocialNetworkTable(tables.Table):
    """جدول شبکه‌های اجتماعی"""
    
    platform = tables.Column(verbose_name='پلتفرم', orderable=False)
    handle = tables.Column(verbose_name='شناسه', orderable=False)
    url = tables.Column(verbose_name='آدرس', empty_values=(), orderable=False)
    
    class Meta:
        model = SocialNetwork
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('platform', 'handle', 'url')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'font-size:.88rem'
        }
    
    def render_platform(self, record):
        return record.get_platform_display() or '—'
    
    def render_handle(self, value):
        return value or '—'
    
    def render_url(self, record):
        if record.url:
            return format_html('<a href="{}" target="_blank">{}</a>', record.url, record.url)
        return '—'


class AttachmentTable(tables.Table):
    """جدول پیوست‌ها"""
    
    doc_type = tables.Column(verbose_name='نوع', orderable=False)
    file = tables.Column(verbose_name='فایل', empty_values=(), orderable=False)
    description = tables.Column(verbose_name='توضیح', orderable=False)
    
    class Meta:
        model = Attachment
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('doc_type', 'file', 'description')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'font-size:.88rem'
        }
    
    def render_doc_type(self, record):
        return record.get_doc_type_display() or '—'
    
    def render_file(self, record):
        if record.file:
            return format_html('<a href="{}" target="_blank">دانلود</a>', record.file.url)
        return '—'
    
    def render_description(self, value):
        return value or '—'


class PurchaseTransportTable(tables.Table):
    """جدول حمل‌های خرید با استفاده از django-tables2"""
    
    transport_number = tables.Column(
        verbose_name='شماره حمل',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order = tables.Column(
        verbose_name='شماره سفارش',
        accessor='purchase_order.order_number',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order_status = tables.Column(
        verbose_name='وضعیت سفارش',
        accessor='purchase_order.status',
        orderable=False,
        empty_values=(),
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    transport_type = tables.Column(
        verbose_name='نوع حمل',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    vehicle_type = tables.Column(
        verbose_name='نوع ماشین',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت حمل',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    plate_number = tables.Column(
        verbose_name='پلاک',
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    expected_arrival_date = tables.DateColumn(
        verbose_name='تاریخ پیش‌بینی ورود',
        format='Y-m-d',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_at = tables.DateTimeColumn(
        verbose_name='تاریخ ایجاد',
        format='Y-m-d',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    actions = tables.Column(
        verbose_name='عملیات',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if accessible_fields:
            # Show columns based on field access permissions
            self.columns['transport_number'].column.visible = accessible_fields.get('transport_number', False)
            self.columns['purchase_order'].column.visible = accessible_fields.get('purchase_order', False)
            self.columns['purchase_order_status'].column.visible = accessible_fields.get('purchase_order_status', False)
            self.columns['transport_type'].column.visible = accessible_fields.get('transport_type', False)
            self.columns['vehicle_type'].column.visible = accessible_fields.get('vehicle_type', False)
            self.columns['status'].column.visible = accessible_fields.get('status', False)
            self.columns['plate_number'].column.visible = accessible_fields.get('plate_number', False)
            self.columns['expected_arrival_date'].column.visible = accessible_fields.get('expected_arrival_date', False)
            self.columns['created_at'].column.visible = accessible_fields.get('created_at', False)
            # Always show actions if any field is visible
            self.columns['actions'].column.visible = any(accessible_fields.values())
    
    class Meta:
        from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
        model = PurchaseTransport
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('transport_number', 'purchase_order', 'purchase_order_status', 'transport_type', 'vehicle_type', 'status', 'plate_number', 'expected_arrival_date', 'created_at', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.85rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('transport_number', 'purchase_order', 'purchase_order_status', 'transport_type', 'vehicle_type', 'status', 'plate_number', 'expected_arrival_date', 'created_at', 'actions')
    
    def render_purchase_order_status(self, record):
        """نمایش وضعیت سفارش خرید"""
        if record.purchase_order:
            status_class = f'status-{record.purchase_order.status}'
            return format_html(
                '<span class="status-badge {}">{}</span>',
                status_class,
                record.purchase_order.get_status_display()
            )
        return '—'
    
    def render_transport_type(self, record):
        """نمایش نوع حمل"""
        return record.get_transport_type_display() or '—'
    
    def render_vehicle_type(self, record):
        """نمایش نوع ماشین"""
        return record.get_vehicle_type_display() or '—'
    
    def render_status(self, value, record):
        """نمایش وضعیت حمل به صورت badge"""
        status_class = f'status-{record.status}'
        return format_html(
            '<span class="status-badge {}">{}</span>',
            status_class,
            record.get_status_display()
        )
    
    def render_plate_number(self, value):
        """نمایش پلاک با ترتیب معکوس 67 | الف | 12345 و سبک badge"""
        if not value:
            return '—'
        try:
            parts = str(value).split('-')
            if len(parts) == 3:
                first, letter, last = parts
                display = f"{last} | {letter} | {first}"
            else:
                display = value
            return format_html('<span class="plate-badge"><span class="ir-flag"></span><span class="seg">{}</span></span>', display)
        except Exception:
            return value
    
    def render_expected_arrival_date(self, value):
        """نمایش تاریخ پیش‌بینی"""
        return value or '—'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        detail_url = reverse('supply:purchase_transport_detail', args=[record.transport_number])
        return format_html(
            '<a href="{}" class="btn btn-secondary btn-sm">جزئیات</a>',
            detail_url
        )


class PurchaseTransportStatusLogTable(tables.Table):
    """جدول تاریخچه وضعیت حمل خرید"""
    
    old_status = tables.Column(verbose_name='از وضعیت', orderable=False)
    new_status = tables.Column(verbose_name='به وضعیت', orderable=False)
    changed_at = tables.DateTimeColumn(verbose_name='زمان', format='Y-m-d H:i', orderable=False)
    changed_by_name = tables.Column(verbose_name='کاربر', empty_values=(), orderable=False)
    note = tables.Column(verbose_name='یادداشت', orderable=False)
    
    class Meta:
        from core.SupplyFolder.PurchaseTransportModel import PurchaseTransportStatusLog
        model = PurchaseTransportStatusLog
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('old_status', 'new_status', 'changed_at', 'changed_by_name', 'note')
        attrs = {
            'class': 'table table-hover table-bordered log-table',
            'style': 'font-size:.8rem'
        }
    
    def render_old_status(self, value):
        return value or '—'
    
    def render_new_status(self, value):
        return value or '—'
    
    def render_changed_by_name(self, record):
        if record.changed_by:
            return record.changed_by.get_full_name() or record.changed_by.username
        return '—'
    
    def render_note(self, value):
        return value or '—'


class ProcurementPurchaseOrderStatusLogTable(tables.Table):
    """جدول تاریخچه وضعیت سفارش خرید"""
    
    old_status = tables.Column(verbose_name='از وضعیت', orderable=False)
    new_status = tables.Column(verbose_name='به وضعیت', orderable=False)
    changed_at = tables.DateTimeColumn(verbose_name='زمان', format='Y-m-d H:i', orderable=False)
    changed_by_name = tables.Column(verbose_name='کاربر', empty_values=(), orderable=False)
    note = tables.Column(verbose_name='یادداشت', orderable=False)
    
    class Meta:
        from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrderStatusLog
        model = ProcurementPurchaseOrderStatusLog
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('old_status', 'new_status', 'changed_at', 'changed_by_name', 'note')
        attrs = {
            'class': 'table table-hover table-bordered log-table',
            'style': 'font-size:.8rem'
        }
    
    def render_old_status(self, value):
        return value or '—'
    
    def render_new_status(self, value):
        return value or '—'
    
    def render_changed_by_name(self, record):
        if record.changed_by:
            return record.changed_by.get_full_name() or record.changed_by.username
        return '—'
    
    def render_note(self, value):
        return value or '—'


class GuardExitTable(tables.Table):
    """جدول حمل‌های در انتظار تایید خروج توسط نگهبان"""
    
    transport_number = tables.Column(
        verbose_name='شماره حمل',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order = tables.Column(
        verbose_name='شماره سفارش',
        accessor='purchase_order.order_number',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    plate_number = tables.Column(
        verbose_name='پلاک',
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    vehicle_type = tables.Column(
        verbose_name='نوع ماشین',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    net_weight = tables.Column(
        verbose_name='وزن خالص (کیلوگرم)',
        orderable=False,
        visible=False,
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
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if accessible_fields:
            if hasattr(self.base_columns, 'transport_number'):
                self.base_columns['transport_number'].visible = accessible_fields.get('transport_number', False)
            if hasattr(self.base_columns, 'purchase_order'):
                self.base_columns['purchase_order'].visible = accessible_fields.get('purchase_order', False)
            if hasattr(self.base_columns, 'plate_number'):
                self.base_columns['plate_number'].visible = accessible_fields.get('plate_number', False)
            if hasattr(self.base_columns, 'vehicle_type'):
                self.base_columns['vehicle_type'].visible = accessible_fields.get('vehicle_type', False)
            if hasattr(self.base_columns, 'net_weight'):
                self.base_columns['net_weight'].visible = accessible_fields.get('net_weight', False)
    
    def render_vehicle_type(self, record):
        return record.get_vehicle_type_display() or '—'
    
    def render_plate_number(self, value):
        return value or '—'
    
    def render_net_weight(self, value):
        if value:
            formatted = format_number_persian(value, decimal_places=3)
            return format_html('{} کیلوگرم', formatted)
        return '—'
    
    def render_actions(self, record):
        identifier = record.transport_number or record.transport_id
        exit_url = reverse('supply:guard_vehicle_exit', args=[identifier])
        return format_html(
            '<a href="{}" class="btn btn-success btn-sm">تایید خروج خودرو</a>',
            exit_url
        )
    
    class Meta:
        from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
        model = PurchaseTransport
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('transport_number', 'purchase_order', 'plate_number', 'vehicle_type', 'net_weight', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.85rem'
        }
        sequence = ('transport_number', 'purchase_order', 'plate_number', 'vehicle_type', 'net_weight', 'actions')


class RawMaterialTable(tables.Table):
    """جدول فهرست مواد اولیه"""
    
    raw_material_id = tables.Column(
        verbose_name='شناسه',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    name = tables.Column(
        verbose_name='نام',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    physical_form = tables.Column(
        verbose_name='شکل فیزیکی',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    primary_unit = tables.Column(
        verbose_name='واحد اصلی',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    secondary_unit = tables.Column(
        verbose_name='واحد فرعی',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    conversion_factor = tables.Column(
        verbose_name='ضریب تبدیل',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت',
        orderable=True,
        visible=False,  # Will be set dynamically
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    created_at = tables.DateTimeColumn(
        verbose_name='تاریخ ایجاد',
        format='Y-m-d H:i',
        orderable=True,
        visible=False,  # Will be set dynamically
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
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Set column visibility based on field access permissions
        if accessible_fields:
            self.columns['raw_material_id'].column.visible = accessible_fields.get('raw_material_id', False)
            self.columns['name'].column.visible = accessible_fields.get('name', False)
            self.columns['physical_form'].column.visible = accessible_fields.get('physical_form', False)
            self.columns['primary_unit'].column.visible = accessible_fields.get('primary_unit', False)
            self.columns['secondary_unit'].column.visible = accessible_fields.get('secondary_unit', False)
            self.columns['conversion_factor'].column.visible = accessible_fields.get('conversion_factor', False)
            self.columns['status'].column.visible = accessible_fields.get('status', False)
            self.columns['created_at'].column.visible = accessible_fields.get('created_at', False)
            # Always show actions column if any field is visible
            self.columns['actions'].column.visible = any(accessible_fields.values()) if accessible_fields else True
    
    class Meta:
        from core.RawMaterialFolder.RawMaterialModel import RawMaterial
        model = RawMaterial
        template_name = 'django_tables2/bootstrap.html'
        fields = ('raw_material_id', 'name', 'physical_form', 'primary_unit', 'secondary_unit', 'conversion_factor', 'status', 'created_at', 'actions')
        attrs = {
            'class': 'data-table',
            'id': 'materialsTable',
            'thead': {'class': ''}
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('raw_material_id', 'name', 'physical_form', 'primary_unit', 'secondary_unit', 'conversion_factor', 'status', 'created_at', 'actions')
    
    def render_physical_form(self, record):
        return record.get_physical_form_display() or '—'
    
    def render_primary_unit(self, record):
        return record.get_primary_unit_display() or '—'
    
    def render_secondary_unit(self, record):
        return record.get_secondary_unit_display() or '—'
    
    def render_status(self, record):
        return format_html('<span class="status-chip">{}</span>', record.get_status_display() or '—')
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        detail_url = reverse('supply:raw_material_detail', args=[record.raw_material_id])
        edit_url = reverse('supply:raw_material_edit', args=[record.raw_material_id])
        return format_html(
            '<div class="btn-group">'
            '<a href="{}" class="btn-outline-info raw-material-detail-link" data-raw-material-id="{}" title="جزئیات">جزئیات</a>'
            '<a href="{}" class="btn-outline-warning" title="ویرایش" style="margin-right: 5px;">ویرایش</a>'
            '</div>',
            detail_url,
            record.raw_material_id,
            edit_url
        )


class LogisticConfirmationTable(tables.Table):
    """جدول لیست حمل‌های در انتظار تایید لجستیک"""
    
    transport_number = tables.Column(
        verbose_name='شماره حمل',
        linkify=lambda record: ('supply:logistic_confirmation_detail', {'transport_number': record.transport_number}) if record.transport_number else None,
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order = tables.Column(
        verbose_name='شماره سفارش خرید',
        accessor='purchase_order__order_number',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    supplier = tables.Column(
        verbose_name='تأمین‌کننده',
        accessor='purchase_order__supplier__name',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    raw_materials = tables.Column(
        verbose_name='نوع ماده اولیه',
        orderable=False,
        empty_values=(),
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    vehicle_type = tables.Column(
        verbose_name='نوع خودرو',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    plate_number = tables.Column(
        verbose_name='پلاک',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    driver = tables.Column(
        verbose_name='راننده',
        accessor='driver__name',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    net_weight = tables.Column(
        verbose_name='وزن خالص (کیلوگرم)',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    delivery_date = tables.DateColumn(
        verbose_name='تاریخ تحویل',
        format='Y-m-d',
        orderable=True,
        visible=False,
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
    
    def __init__(self, *args, accessible_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        if accessible_fields:
            if hasattr(self.base_columns, 'transport_number'):
                self.base_columns['transport_number'].visible = accessible_fields.get('transport_number', False)
            if hasattr(self.base_columns, 'purchase_order'):
                self.base_columns['purchase_order'].visible = accessible_fields.get('purchase_order', False)
            if hasattr(self.base_columns, 'supplier'):
                self.base_columns['supplier'].visible = accessible_fields.get('purchase_order', False)
            if hasattr(self.base_columns, 'raw_materials'):
                self.base_columns['raw_materials'].visible = accessible_fields.get('purchase_order', False)
            if hasattr(self.base_columns, 'vehicle_type'):
                self.base_columns['vehicle_type'].visible = accessible_fields.get('vehicle_type', False)
            if hasattr(self.base_columns, 'plate_number'):
                self.base_columns['plate_number'].visible = accessible_fields.get('plate_number', False)
            if hasattr(self.base_columns, 'driver'):
                self.base_columns['driver'].visible = accessible_fields.get('driver', False)
            if hasattr(self.base_columns, 'net_weight'):
                self.base_columns['net_weight'].visible = accessible_fields.get('net_weight', False)
            if hasattr(self.base_columns, 'delivery_date'):
                self.base_columns['delivery_date'].visible = accessible_fields.get('created_at', False)
    
    class Meta:
        from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
        model = PurchaseTransport
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('transport_number', 'purchase_order', 'supplier', 'raw_materials', 'vehicle_type', 'plate_number', 'driver', 'net_weight', 'delivery_date', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'id': 'logisticConfirmationTable',
            'style': 'border-collapse:collapse;font-size:.88rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('transport_number', 'purchase_order', 'supplier', 'raw_materials', 'vehicle_type', 'plate_number', 'driver', 'net_weight', 'delivery_date', 'actions')
    
    def render_raw_materials(self, record):
        """نمایش مواد اولیه سفارش (ممکن چندتا باشد)"""
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
    
    def render_vehicle_type(self, record):
        """نمایش نوع خودرو"""
        return record.get_vehicle_type_display() if record.vehicle_type else '—'
    
    def render_plate_number(self, value):
        """نمایش پلاک با ترتیب معکوس 67 | الف | 12345 و سبک badge"""
        if not value:
            return '—'
        try:
            parts = str(value).split('-')
            if len(parts) == 3:
                first, letter, last = parts
                display = f"{last} | {letter} | {first}"
            else:
                display = value
            return format_html('<span class="plate-badge"><span class="ir-flag"></span><span class="seg">{}</span></span>', display)
        except Exception:
            return value
    
    def render_driver(self, value):
        """نمایش راننده"""
        return value or '—'
    
    def render_net_weight(self, value):
        """نمایش وزن خالص با فرمت عددی"""
        if value:
            # Convert to float and format it as Persian number
            formatted_value = format_number_persian(value, decimal_places=2)
            return format_html('{}', formatted_value)
        return '—'
    
    def render_delivery_date(self, value):
        """نمایش تاریخ تحویل"""
        if value:
            return value.strftime('%Y/%m/%d')
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        if not record.transport_number:
            return format_html('<span class="text-muted">شماره حمل ناموجود</span>')
        detail_url = reverse('supply:logistic_confirmation_detail', kwargs={'transport_number': record.transport_number})
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">تایید لجستیک</a>',
            detail_url
        )


class UploadFarePaymentDocsTable(tables.Table):
    """جدول لیست حمل‌های در انتظار بارگذاری اسناد پرداخت"""
    
    transport_number = tables.Column(
        verbose_name='شماره حمل',
        linkify=lambda record: ('supply:upload_fare_payment_docs_detail', {'transport_number': record.transport_number}) if record.transport_number else None,
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
        from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
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
            formatted_value = format_number_persian(value, decimal_places=2)
            return format_html('{} کیلوگرم', formatted_value)
        return '—'
    
    def render_freight_payment(self, value):
        """نمایش کرایه پرداختی نهایی (جهت کنترل)"""
        if value:
            formatted_value = format_number_persian(value, decimal_places=0)
            return format_html('{} ریال', formatted_value)
        return '—'
    
    def render_status(self, record):
        """نمایش وضعیت حمل"""
        return record.get_status_display()
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        if not record.transport_number:
            return format_html('<span class="text-muted">شماره حمل ناموجود</span>')
        detail_url = reverse('supply:upload_fare_payment_docs_detail', kwargs={'transport_number': record.transport_number})
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">جزئیات</a>',
            detail_url
        )
