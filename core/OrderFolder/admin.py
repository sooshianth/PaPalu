from django.contrib import admin
from . import Order, OrderItem, OrderDocument, DocumentRelation, ApprovalInfo


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'order_type', 'status']
    list_filter = ['order_type', 'status']
    search_fields = ['order_number']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product']
    list_filter = ['order']
    search_fields = ['order__order_number']


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
