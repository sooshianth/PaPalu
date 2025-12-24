import django_tables2 as tables
from django.utils.html import format_html, format_html_join
from django.urls import reverse
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from core.OrderFolder.OrderModel import Order


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
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    name = tables.Column(
        verbose_name='نام تأمین‌کننده',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
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
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
        }
    )
    
    phone_number = tables.Column(
        verbose_name='شماره تلفن',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-right'},
            'th': {'class': 'text-right'}
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
        template_name = 'django_tables2/bootstrap.html'
        fields = ('national_id', 'name', 'nature', 'registration_number', 'phone_number', 'actions')
        attrs = {
            'class': 'data-table',
            'id': 'suppliersTable',
            'thead': {'class': ''}
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('national_id', 'name', 'nature', 'registration_number', 'phone_number', 'actions')
    
    def render_national_id(self, value, record):
        """نمایش کد ملی به صورت badge"""
        return format_html('<span class="badge badge-green">{}</span>', value)
    
    def render_name(self, value, record):
        """نمایش نام به صورت bold"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_nature(self, value, record):
        """نمایش نوع شخص به صورت badge"""
        # اگر value None باشد یا خالی باشد، از record استفاده کن
        if value is None or value == '':
            value = getattr(record, 'nature', None)
        
        # اگر هنوز None است، از record.nature استفاده کن
        if value is None:
            value = record.nature if hasattr(record, 'nature') else None
        
        if value == 'legal':
            return format_html('<span class="badge badge-nature badge-nature-legal">حقوقی</span>')
        elif value == 'natural':
            return format_html('<span class="badge badge-nature badge-nature-natural">حقیقی</span>')
        elif value:
            # اگر مقدار دیگری دارد، آن را نمایش بده
            return format_html('<span class="badge badge-nature">{}</span>', value)
        else:
            return format_html('<span class="badge badge-nature">-</span>')
    
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
            '<a href="{}" class="btn-outline-info supplier-detail-link" data-supplier-id="{}" title="جزئیات">جزئیات</a>'
            '</div>',
            detail_url,
            record.national_id
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
        accessor='customer.name',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_by = tables.Column(
        verbose_name='کاربر ثبت کننده',
        accessor='registered_by',
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
    
    total_weight = tables.Column(
        verbose_name='وزن کل',
        empty_values=(),
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
            self.columns['total_weight'].column.visible = accessible_fields.get('total_weight', False)
            # Always show actions if any field is visible
            self.columns['actions'].column.visible = any(accessible_fields.values())
    
    class Meta:
        model = Order
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('order_number', 'status', 'materials_list', 'supplier', 'created_by', 'created_at', 'total_weight', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.85rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('order_number', 'status', 'materials_list', 'total_weight', 'supplier', 'created_by', 'created_at', 'actions')
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        status_class = f'status-{record.status}'
        return format_html(
            '<span class="status-badge {}">{}</span>',
            status_class,
            record.get_status_display()
        )
    
    def render_order_number(self, value, record):
        """نمایش شماره سفارش"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_materials_list(self, record):
        """نمایش لیست مواد اولیه با وزن"""
        materials = record.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
        if materials:
            items = []
            for m in materials:
                rm = m.raw_material
                # محاسبه وزن ماده اولیه
                weight_kg = m.get_weight_in_kg()
                # نمایش: شناسه - نام (وزن)
                display_text = f"{rm.raw_material_id or 'N/A'} - {rm.name or 'بدون نام'}"
                if weight_kg > 0:
                    # فرمت وزن با اعداد فارسی
                    weight_formatted = format_number_persian(weight_kg, decimal_places=2)
                    display_text += f" ({weight_formatted} کیلوگرم)"
                items.append((format_html('<strong>{}</strong>', display_text),))
            
            inner_html = format_html_join(
                '',
                '<div style="padding:4px 8px;background:#e3f2fd;border-radius:4px;margin:2px;font-size:0.75rem;border-right:3px solid #1976d2">{}</div>',
                items
            )
            return format_html('<div style="display:flex;flex-direction:column;gap:2px">{}</div>', inner_html)
        return '—'
    
    def render_total_weight(self, record):
        """نمایش وزن کل سفارش"""
        total_weight = 0
        materials = record.order_items.filter(raw_material__isnull=False).all()
        for m in materials:
            weight_kg = m.get_weight_in_kg()
            total_weight += weight_kg
        
        if total_weight > 0:
            # فرمت وزن با اعداد فارسی
            weight_formatted = format_number_persian(total_weight, decimal_places=2)
            return format_html('<strong>{}</strong>', f"{weight_formatted} کیلوگرم")
        return '—'
    
    def render_supplier(self, value):
        """نمایش نام تأمین‌کننده"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_created_by(self, record):
        """نمایش نام کاربر ثبت کننده"""
        if record.registered_by:
            name = record.registered_by.get_full_name() or record.registered_by.username
            return format_html('<strong>{}</strong>', name)
        return '—'
    
    def render_created_at(self, value, record):
        """نمایش تاریخ ایجاد"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        detail_url = reverse('supply:procurement_purchase_order_detail', args=[record.order_number])
        return format_html(
            '<a href="{}" class="btn-outline-info">جزئیات</a>',
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


class TransportTable(tables.Table):
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
        accessor='allocation.order.order_number',
        orderable=True,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    purchase_order_status = tables.Column(
        verbose_name='وضعیت سفارش',
        accessor='allocation.order.status',
        orderable=False,
        empty_values=(),
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    raw_materials = tables.Column(
        verbose_name='مواد اولیه',
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
            self.columns['raw_materials'].column.visible = accessible_fields.get('raw_materials', False)
            self.columns['transport_type'].column.visible = accessible_fields.get('transport_type', False)
            self.columns['vehicle_type'].column.visible = accessible_fields.get('vehicle_type', False)
            self.columns['status'].column.visible = accessible_fields.get('status', False)
            self.columns['plate_number'].column.visible = accessible_fields.get('plate_number', False)
            self.columns['expected_arrival_date'].column.visible = accessible_fields.get('expected_arrival_date', False)
            self.columns['created_at'].column.visible = accessible_fields.get('created_at', False)
            # Always show actions if any field is visible
            self.columns['actions'].column.visible = any(accessible_fields.values()) if accessible_fields else True
        else:
            # اگر accessible_fields None باشد، همه ستون‌ها را نمایش بده (برای سوپریوزر یا کاربران بدون محدودیت)
            # ستون‌ها به صورت پیش‌فرض visible هستند، فقط actions را مطمئن می‌کنیم
            self.columns['actions'].column.visible = True
    
    class Meta:
        from core.TransportFolder.TransportModel import Transport
        model = Transport
        template_name = 'django_tables2/bootstrap.html'
        # فیلدهای مورد نیاز برای لیست حمل‌ها
        fields = ('purchase_order', 'created_at', 'raw_materials', 'transport_type', 'vehicle_type', 'status', 'actions')
        attrs = {
            'class': 'data-table',
            'id': 'transportsTable',
            'thead': {'class': ''}
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        # ستون‌های مورد نیاز: شماره سفارش، تاریخ ثبت، مواد اولیه، نوع حمل، نوع ماشین، وضعیت، جزئیات
        sequence = ('purchase_order', 'created_at', 'raw_materials', 'transport_type', 'vehicle_type', 'status', 'actions')
    
    def render_purchase_order_status(self, record):
        """نمایش وضعیت سفارش خرید"""
        if record.allocation and record.allocation.order:
            status_class = f'status-{record.allocation.order.status}'
            return format_html(
                '<span class="status-badge {}">{}</span>',
                status_class,
                record.allocation.order.get_status_display()
            )
        return '—'
    
    def render_raw_materials(self, record):
        """نمایش مواد اولیه حمل با مقدار تخصیص یافته"""
        from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
        materials = RawMaterialInfo.objects.filter(transport=record).select_related('raw_material', 'order_item').all()
        if materials:
            items = []
            for m in materials:
                rm = m.raw_material
                # نمایش: نام ماده اولیه (مقدار تخصیص یافته + واحد)
                display_text = f"{rm.name or 'بدون نام'}"
                if m.allocated_quantity:
                    weight_formatted = format_number_persian(m.allocated_quantity, decimal_places=2)
                    unit_display = m.get_weight_unit_display()
                    display_text += f" ({weight_formatted} {unit_display})"
                items.append((format_html('<strong>{}</strong>', display_text),))
            
            inner_html = format_html_join(
                '',
                '<div style="padding:4px 8px;background:#e3f2fd;border-radius:4px;margin:2px;font-size:0.75rem;border-right:3px solid #1976d2">{}</div>',
                items
            )
            return format_html('<div style="display:flex;flex-direction:column;gap:2px">{}</div>', inner_html)
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
        """نمایش پلاک با فرمت جدید: 11|345ب12"""
        if not value:
            return '—'
        try:
            # فرمت جدید: 11|345ب12
            if '|' in str(value):
                parts = str(value).split('|')
                if len(parts) == 2:
                    iran = parts[0]
                    rest = parts[1]
                    # استخراج 3 رقم، 1 حرف، 2 رقم از rest
                    import re
                    match = re.match(r'(\d{3})([آ-یA-Za-z])(\d{2})', rest)
                    if match:
                        middle, letter, last = match.groups()
                        display = f"{iran}|{middle}{letter}{last}"
                    else:
                        display = value
                else:
                    display = value
            # فرمت قدیمی: 11-345-ب-12
            elif '-' in str(value):
                parts = str(value).split('-')
                if len(parts) == 4:
                    iran, middle, letter, last = parts
                    display = f"{iran}|{middle}{letter}{last}"
                elif len(parts) == 3:
                    first, letter, last = parts
                    display = f"{last} | {letter} | {first}"
                else:
                    display = value
            else:
                display = value
            return format_html('<span class="plate-badge"><span class="ir-flag"></span><span class="seg">{}</span></span>', display)
        except Exception:
            return value or '—'
    
    def render_expected_arrival_date(self, value):
        """نمایش تاریخ پیش‌بینی"""
        return value or '—'
    
    def render_actions(self, record):
        """نمایش دکمه‌های عملیات"""
        # اگر transport_number None است، از pk استفاده کن
        identifier = record.transport_number or str(record.pk)
        detail_url = reverse('supply:purchase_transport_detail', args=[identifier])
        return format_html(
            '<a href="{}" class="btn-outline-info">جزئیات</a>',
            detail_url
        )


class TransportStatusLogTable(tables.Table):
    """جدول تاریخچه وضعیت حمل - بدون مدل (برای سازگاری)"""
    
    old_status = tables.Column(verbose_name='از وضعیت', orderable=False)
    new_status = tables.Column(verbose_name='به وضعیت', orderable=False)
    changed_at = tables.DateTimeColumn(verbose_name='زمان', format='Y-m-d H:i', orderable=False)
    changed_by_name = tables.Column(verbose_name='کاربر', empty_values=(), orderable=False)
    note = tables.Column(verbose_name='یادداشت', orderable=False)
    
    class Meta:
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
        if hasattr(record, 'changed_by') and record.changed_by:
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
        from core.OrderFolder.OrderModel import OrderStatusLog
        model = OrderStatusLog
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


class GuardExitTable(TransportTable):
    """جدول حمل‌های در انتظار تایید خروج توسط نگهبان"""
    
    raw_materials = tables.Column(
        verbose_name='نام ماده اولیه',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    quantity = tables.Column(
        verbose_name='مقدار',
        empty_values=(),
        orderable=False,
        visible=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    unit = tables.Column(
        verbose_name='واحد',
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
        
        # ستون‌های مورد نیاز: شماره سفارش، نوع ماده اولیه، مقدار، واحد، پلاک، نوع ماشین
        # این ستون‌ها باید همیشه نمایش داده شوند
        required_columns = ['purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions']
        
        # همیشه ستون‌های مورد نیاز را نمایش بده
        for col_name in required_columns:
            if col_name in ['raw_materials', 'quantity', 'unit']:
                # ستون‌های custom که در base_columns تعریف شده‌اند
                if col_name in self.base_columns:
                    self.base_columns[col_name].visible = True
            elif col_name in self.columns:
                # ستون‌های عادی
                self.columns[col_name].column.visible = True
    
    def render_raw_materials(self, record):
        """نمایش لیست مواد اولیه از سفارش خرید"""
        if not record.purchase_order:
            return '—'
        # استفاده از order_items به جای materials
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials if m.raw_material]
            return format_html('<br>'.join(names)) if names else '—'
        return '—'
    
    def render_quantity(self, record):
        """نمایش مقدار سفارش"""
        if not record.purchase_order:
            return '—'
        # استفاده از order_items به جای materials
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).all()
        if materials:
            quantities = [str(m.quantity) for m in materials if m.quantity]
            return format_html('<br>'.join(quantities)) if quantities else '—'
        return '—'
    
    def render_unit(self, record):
        """نمایش واحد سفارش"""
        if not record.purchase_order:
            return '—'
        # استفاده از order_items به جای materials
        materials = record.purchase_order.order_items.filter(raw_material__isnull=False).all()
        if materials:
            units = [m.get_weight_unit_display() or '—' for m in materials]
            return format_html('<br>'.join(units)) if units else '—'
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه تایید خروج خودرو"""
        # استفاده از transport_number یا pk در صورت None بودن
        transport_id = record.transport_number
        if not transport_id or transport_id == 'None' or str(transport_id).strip() == '':
            transport_id = str(record.pk)
        exit_url = reverse('supply:guard_vehicle_exit', args=[str(transport_id)])
        return format_html(
            '<a href="{}" class="btn btn-success btn-sm">تایید خروج خودرو</a>',
            exit_url
        )
    
    class Meta(TransportTable.Meta):
        sequence = ('purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')
        fields = ('purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')


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
        verbose_name='شماره سفارش',
        accessor='allocation.order.order_number',
        orderable=True,
        visible=True,  # همیشه نمایش داده می‌شود
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    supplier = tables.Column(
        verbose_name='تأمین‌کننده',
        accessor='purchase_order__customer__name',
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
        verbose_name='تاریخ خروج خودرو',
        format='Y-m-d',
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
        
        # ستون‌های مورد نیاز: شماره سفارش، نوع ماده اولیه، پلاک خودرو، مقدار تحویلی، تاریخ خروج، وضعیت، عملیات
        # این ستون‌ها باید همیشه نمایش داده شوند
        required_columns = ['purchase_order', 'raw_materials', 'plate_number', 'net_weight', 'delivery_date', 'status', 'actions']
        
        # همیشه ستون‌های مورد نیاز را نمایش بده
        for col_name in required_columns:
            if col_name in ['raw_materials']:
                # ستون‌های custom که در base_columns تعریف شده‌اند
                if col_name in self.base_columns:
                    self.base_columns[col_name].visible = True
            elif col_name in self.columns:
                # ستون‌های عادی
                self.columns[col_name].column.visible = True
    
    class Meta:
        from core.TransportFolder.TransportModel import Transport
        model = Transport
        template_name = 'django_tables2/bootstrap4.html'
        # فیلدهای مورد نیاز برای لیست حمل‌های در انتظار تسویه
        fields = ('purchase_order', 'raw_materials', 'plate_number', 'net_weight', 'delivery_date', 'status', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'id': 'logisticConfirmationTable',
            'style': 'border-collapse:collapse;font-size:.88rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        # ستون‌های مورد نیاز: شماره سفارش، نوع ماده اولیه، پلاک خودرو، مقدار تحویلی (خالص)، تاریخ خروج خودرو، وضعیت حمل، عملیات
        sequence = ('purchase_order', 'raw_materials', 'plate_number', 'net_weight', 'delivery_date', 'status', 'actions')
    
    def render_raw_materials(self, record):
        """نمایش مواد اولیه سفارش (ممکن چندتا باشد)"""
        if not record.allocation or not record.allocation.order:
            return '—'
        materials = record.allocation.order.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials if m.raw_material]
            if len(names) > 2:
                return format_html('{}, ...', ', '.join(names[:2]))
            return ', '.join(names) if names else '—'
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
        """نمایش پلاک با فرمت جدید: 11|345ب12"""
        if not value:
            return '—'
        try:
            # فرمت جدید: 11|345ب12
            if '|' in str(value):
                parts = str(value).split('|')
                if len(parts) == 2:
                    iran = parts[0]
                    rest = parts[1]
                    # استخراج 3 رقم، 1 حرف، 2 رقم از rest
                    import re
                    match = re.match(r'(\d{3})([آ-یA-Za-z])(\d{2})', rest)
                    if match:
                        middle, letter, last = match.groups()
                        display = f"{iran}|{middle}{letter}{last}"
                    else:
                        display = value
                else:
                    display = value
            # فرمت قدیمی: 11-345-ب-12
            elif '-' in str(value):
                parts = str(value).split('-')
                if len(parts) == 4:
                    iran, middle, letter, last = parts
                    display = f"{iran}|{middle}{letter}{last}"
                elif len(parts) == 3:
                    first, letter, last = parts
                    display = f"{last} | {letter} | {first}"
                else:
                    display = value
            else:
                display = value
            return format_html('<span class="plate-badge"><span class="ir-flag"></span><span class="seg">{}</span></span>', display)
        except Exception:
            return value or '—'
    
    def render_driver(self, value):
        """نمایش راننده"""
        return value or '—'
    
    def render_net_weight(self, value):
        """نمایش مقدار تحویلی (خالص) با فرمت عددی"""
        if value:
            # Convert to float and format it as Persian number
            formatted_value = format_number_persian(value, decimal_places=2)
            return format_html('{} کیلوگرم', formatted_value)
        return '—'
    
    def render_delivery_date(self, value):
        """نمایش تاریخ خروج خودرو"""
        if value:
            return value.strftime('%Y/%m/%d')
        return '—'
    
    def render_status(self, value, record):
        """نمایش وضعیت حمل به صورت badge"""
        status_class = f'status-{record.status}'
        return format_html(
            '<span class="status-badge {}">{}</span>',
            status_class,
            record.get_status_display()
        )
    
    def render_actions(self, record):
        """نمایش دکمه جزئیات"""
        # استفاده از transport_number یا pk در صورت None بودن
        transport_id = record.transport_number
        if not transport_id or transport_id == 'None' or str(transport_id).strip() == '':
            transport_id = str(record.pk)
        detail_url = reverse('supply:logistic_confirmation_detail', kwargs={'transport_number': str(transport_id)})
        return format_html(
            '<a href="{}" class="btn btn-sm btn-primary">جزئیات</a>',
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
        from core.TransportFolder.TransportModel import Transport
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


class AwaitingPurchaseOrderTable(tables.Table):
    """جدول سفارش‌های در انتظار تعریف حمل"""
    
    order_number = tables.Column(
        verbose_name='شماره سفارش',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    supplier = tables.Column(
        verbose_name='تأمین‌کننده',
        accessor='customer.name',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_at = tables.DateTimeColumn(
        verbose_name='تاریخ ایجاد',
        format='Y-m-d',
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
        model = Order
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('order_number', 'supplier', 'created_at', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.88rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('order_number', 'supplier', 'created_at', 'actions')
    
    def render_order_number(self, value):
        """نمایش شماره سفارش به صورت bold"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_supplier(self, value):
        """نمایش نام تأمین‌کننده"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه تعریف حمل"""
        create_url = reverse('supply:create_purchase_transport') + f'?order={record.order_number}'
        return format_html(
            '<a href="{}" class="btn-outline-info">تعریف حمل</a>',
            create_url
        )


class PurchaseOrderMaterialTable(tables.Table):
    """جدول مواد اولیه سفارش خرید"""
    
    raw_material_id = tables.Column(
        verbose_name='شناسه ماده اولیه',
        accessor='raw_material.raw_material_id',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    raw_material_name = tables.Column(
        verbose_name='نام ماده اولیه',
        accessor='raw_material.name',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    physical_form = tables.Column(
        verbose_name='شکل فیزیکی',
        accessor='raw_material.get_physical_form_display',
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    technical_description = tables.Column(
        verbose_name='توضیحات فنی',
        accessor='raw_material.technical_description',
        orderable=False,
        attrs={
            'td': {'class': 'text-center', 'style': 'max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'},
            'th': {'class': 'text-center'}
        }
    )
    
    quantity = tables.Column(
        verbose_name='مقدار',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    weight_unit = tables.Column(
        verbose_name='واحد',
        accessor='get_weight_unit_display',
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    unit_price = tables.Column(
        verbose_name='قیمت واحد',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    vat_percent = tables.Column(
        verbose_name='مالیات بر ارزش افزوده (%)',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    freight_cost = tables.Column(
        verbose_name='بهای تمام شده کرایه',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    total_purchase_cost = tables.Column(
        verbose_name='بهای تمام شده خرید',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    external_allocation_id = tables.Column(
        verbose_name='شناسه تخصیص',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    notes = tables.Column(
        verbose_name='توضیحات',
        orderable=False,
        attrs={
            'td': {'class': 'text-center', 'style': 'max-width: 150px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'},
            'th': {'class': 'text-center'}
        }
    )
    
    class Meta:
        from core.OrderFolder.OrderItemModel import OrderItem
        model = OrderItem
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('raw_material_id', 'raw_material_name', 'physical_form', 'technical_description', 
                  'quantity', 'weight_unit', 'unit_price', 'vat_percent', 'freight_cost', 
                  'total_purchase_cost', 'external_allocation_id', 'notes')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.88rem;min-width: 1800px;'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('raw_material_id', 'raw_material_name', 'physical_form', 'technical_description', 
                    'quantity', 'weight_unit', 'unit_price', 'vat_percent', 'freight_cost', 
                    'total_purchase_cost', 'external_allocation_id', 'notes')
    
    def render_raw_material_name(self, value):
        """نمایش نام ماده اولیه به صورت bold"""
        if value:
            return format_html('<strong>{}</strong>', value)
        return '—'
    
    def render_technical_description(self, value, record):
        """نمایش توضیحات فنی با truncate"""
        if value:
            return format_html('<span title="{}">{}</span>', value, value[:50] + '...' if len(value) > 50 else value)
        return '—'
    
    def render_notes(self, value):
        """نمایش توضیحات با truncate"""
        if value:
            return format_html('<span title="{}">{}</span>', value, value[:30] + '...' if len(value) > 30 else value)
        return '—'


class PurchaseOrderTransportTable(tables.Table):
    """جدول حمل‌های مرتبط با سفارش خرید"""
    
    vehicle_type = tables.Column(
        verbose_name='نوع ماشین',
        accessor='get_vehicle_type_display',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت حمل',
        accessor='get_status_display',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    created_at = tables.DateTimeColumn(
        verbose_name='تاریخ ثبت',
        format='Y/m/d',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    total_freight = tables.Column(
        verbose_name='کرایه',
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
        from core.TransportFolder.TransportModel import Transport
        model = Transport
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('vehicle_type', 'status', 'created_at', 'total_freight', 'actions')
        attrs = {
            'class': 'table table-hover table-bordered',
            'style': 'border-collapse:collapse;font-size:.88rem'
        }
        row_attrs = {
            'style': 'transition: background-color 0.2s ease;'
        }
        sequence = ('vehicle_type', 'status', 'created_at', 'total_freight', 'actions')
    
    def render_status(self, record):
        """نمایش وضعیت با badge"""
        status_display = record.get_status_display()
        status_class = f'status-{record.status}'
        return format_html(
            '<span class="status-badge {}">{}</span>',
            status_class,
            status_display
        )
    
    def render_total_freight(self, value):
        """نمایش کرایه"""
        if value:
            return format_html('{}', format_number_persian(value, decimal_places=0))
        return '—'
    
    def render_actions(self, record):
        """نمایش دکمه جزئیات"""
        if not record.transport_number:
            return format_html('<span class="text-muted">شماره حمل ناموجود</span>')
        detail_url = reverse('supply:purchase_transport_detail', kwargs={'transport_number': record.transport_number})
        return format_html(
            '<a href="{}" class="btn btn-secondary btn-sm">جزئیات</a>',
            detail_url
        )