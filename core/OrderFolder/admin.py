from django.contrib import admin
from . import Order, OrderItem, OrderDocument, DocumentRelation, ApprovalInfo, Proforma, Invoice


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'order_type', 'status', 'freight_payment_type']
    list_filter = ['order_type', 'status', 'registered_by']
    search_fields = ['order_number', 'customer__name', 'customer__national_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('order_number', 'customer', 'order_type', 'registration_source', 'registered_by')
        }),
        ('وزن‌های ارسال و تحویل', {
            'fields': ('total_shipment_weight', 'total_delivery_weight'),
            'description': 'این مقادیر از اقلام سفارش محاسبه می‌شوند'
        }),
        ('وضعیت و تاریخ', {
            'fields': ('status', 'creation_date', 'created_at', 'updated_at')
        }),
        ('اطلاعات دیگر', {
            'fields': ('freight_payment_type', 'accounting_document_number'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'weight_unit', 'quantity', 'unit_price', 'total_purchase_cost']
    list_filter = ['order', 'weight_unit']
    search_fields = ['order__order_number', 'product__name']
    readonly_fields = ['total_purchase_cost', 'vat']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('order', 'product')
        }),
        ('واحد و مقدار', {
            'fields': ('weight_unit', 'bag_weight', 'quantity')
        }),
        ('قیمت و هزینه‌ها', {
            'fields': ('unit_price', 'discount', 'additional_charges', 'vat_percent', 'vat')
        }),
        ('هزینه‌های محاسبه شده', {
            'fields': ('cost_without_freight', 'freight_cost', 'total_purchase_cost'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderDocument)
class OrderDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order']
    search_fields = ['order__order_number']


@admin.register(DocumentRelation)
class DocumentRelationAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(ApprovalInfo)
class ApprovalInfoAdmin(admin.ModelAdmin):
    list_display = ['id', 'order']
    search_fields = ['order__order_number']


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = ['id', 'proforma_number', 'order', 'customer', 'company', 'validity_date', 'is_invalidated', 'created_at']
    list_filter = ['is_invalidated', 'created_at', 'validity_date']
    search_fields = ['proforma_number', 'order__order_number', 'customer__name', 'customer__national_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('proforma_number', 'order', 'customer', 'company', 'validity_date')
        }),
        ('وضعیت', {
            'fields': ('is_invalidated',)
        }),
        ('توضیحات', {
            'fields': ('description',)
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['id', 'tax_invoice_number', 'order', 'customer', 'company', 'issue_date', 'customer_tax_type', 'created_at']
    list_filter = ['customer_tax_type', 'issue_date', 'created_at']
    search_fields = ['tax_invoice_number', 'order__order_number', 'customer__name', 'customer__national_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('order', 'tax_invoice_number', 'customer', 'company', 'customer_tax_type', 'issue_date')
        }),
        ('فایل و توضیحات', {
            'fields': ('invoice_file', 'description')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
