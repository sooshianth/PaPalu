import django_tables2 as tables
from django.utils.html import format_html
from django.urls import reverse
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from production.templatetags.number_filters import persian_number


class ProductionProgramTable(tables.Table):
    id = tables.Column(verbose_name='شناسه', orderable=True)
    product = tables.Column(verbose_name='محصول', orderable=True)
    production_info = tables.Column(verbose_name='فرمول', orderable=True)
    planned_weight_ton = tables.Column(verbose_name='تناژ برنامه (کیلوگرم)', orderable=True)
    status = tables.Column(verbose_name='وضعیت', orderable=True)
    actions = tables.Column(empty_values=(), verbose_name='عملیات', orderable=False)

    class Meta:
        model = ProductionProgram
        template_name = "django_tables2/bootstrap.html"
        fields = ("id", "product", "production_info", "planned_weight_ton", "status")
        attrs = {
            "class": "data-table",
        }
        row_attrs = {
            "class": lambda record: "referred-to-manager-row" if getattr(record, "declaration_referred_to_manager", False) else ""
        }

    def render_id(self, value):
        """نمایش شناسه با اعداد فارسی"""
        return format_html('<span class="persian-number">{}</span>', persian_number(value, 0))

    def render_product(self, value, record):
        """نمایش نام محصول با badge سبز"""
        if value:
            return format_html('<span class="badge badge-green">{}</span>', value.name if hasattr(value, 'name') else str(value))
        return '-'

    def render_production_info(self, value, record):
        """نمایش فرمول با badge سبز"""
        if value and hasattr(value, 'formula_id') and value.formula_id:
            return format_html('<span class="badge badge-green">{}</span>', value.formula_id)
        return format_html('<span class="badge badge-green-empty">-</span>')

    def render_planned_weight_ton(self, value):
        """نمایش تناژ برنامه با اعداد فارسی"""
        if value is not None:
            return format_html('<span class="persian-number">{}</span>', persian_number(value, 3))
        return '-'

    def render_status(self, value, record):
        if value == ProductionProgram.Status.CONFIRMED:
            return format_html('<span class="badge badge-green">تأیید شده</span>')
        if value == ProductionProgram.Status.IN_PROGRESS:
            return format_html('<span class="badge badge-warning">در حال اجرا</span>')
        if value == ProductionProgram.Status.COMPLETED:
            return format_html('<span class="badge badge-gray">تکمیل شده</span>')
        return record.get_status_display()

    def render_actions(self, record):
        edit_url = reverse('production:program_edit', args=[record.id])
        return format_html('<a href="{}" class="btn-outline-warning">ویرایش</a>', edit_url)

