import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrder


class SupplierTable(tables.Table):
    """جدول لیست تأمین‌کنندگان با استفاده از django-tables2"""
    
    national_id = tables.Column(
        verbose_name='کد ملی',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    name = tables.Column(
        verbose_name='نام تأمین‌کننده',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    nature = tables.Column(
        verbose_name='نوع',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    registration_number = tables.Column(
        verbose_name='شماره ثبت',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    phone_number = tables.Column(
        verbose_name='شماره تلفن',
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
        model = Person
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('national_id', 'name', 'nature', 'registration_number', 'phone_number', 'actions')
        attrs = {
            'class': 'table table-striped table-bordered dataTable',
            'id': 'suppliersTable'
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
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    status = tables.Column(
        verbose_name='وضعیت فعلی',
        orderable=True,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    materials_list = tables.Column(
        verbose_name='مواد اولیه',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    supplier = tables.Column(
        verbose_name='تأمین‌کننده',
        accessor='supplier.name',
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
        model = ProcurementPurchaseOrder
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('order_number', 'status', 'materials_list', 'supplier', 'created_at', 'actions')
        attrs = {
            'class': 'table table-striped table-bordered dataTable',
        }
        sequence = ('order_number', 'status', 'materials_list', 'supplier', 'created_at', 'actions')
    
    def render_status(self, value, record):
        """نمایش وضعیت به صورت badge"""
        status_class = f'status-{record.status}'
        return format_html(
            '<span class="status-badge {}">{}</span>',
            status_class,
            record.get_status_display()
        )
    
    def render_materials_list(self, record):
        """نمایش لیست مواد اولیه"""
        materials = record.materials.all()
        if materials:
            html_parts = []
            for m in materials:
                html_parts.append(format_html(
                    '<span style="display:inline-block;padding:2px 6px;background:#f1f3f4;border-radius:4px;margin:1px">{}</span>',
                    m.raw_material.name
                ))
            return format_html(''.join(str(part) for part in html_parts))
        return '—'
    
    def render_supplier(self, value):
        """نمایش نام تأمین‌کننده"""
        return value or '—'
    
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
        attrs = {'class': 'table table-bordered'}
    
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
        attrs = {'class': 'table table-bordered'}
    
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
    credit_limit = tables.Column(verbose_name='سقف اعتبار', orderable=False)
    notes = tables.Column(verbose_name='توضیحات', orderable=False)
    
    class Meta:
        model = PaymentPreference
        template_name = 'django_tables2/bootstrap4.html'
        fields = ('payment_method', 'payment_term_days', 'credit_limit', 'notes')
        attrs = {'class': 'table table-bordered'}
    
    def render_payment_method(self, record):
        return record.get_payment_method_display() or '—'
    
    def render_payment_term_days(self, value):
        return value or '—'
    
    def render_credit_limit(self, value):
        return value or '—'
    
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
        attrs = {'class': 'table table-bordered'}
    
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
        attrs = {'class': 'table table-bordered'}
    
    def render_doc_type(self, record):
        return record.get_doc_type_display() or '—'
    
    def render_file(self, record):
        if record.file:
            return format_html('<a href="{}" target="_blank">دانلود</a>', record.file.url)
        return '—'
    
    def render_description(self, value):
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
        attrs = {'class': 'table table-bordered log-table'}
    
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
