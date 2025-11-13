from django.contrib import admin
from . import Warehouse, InventoryProduct, DefaultItem


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['warehouse_id', 'warehouse_type']
    list_filter = ['warehouse_type']
    search_fields = ['warehouse_id']


@admin.register(InventoryProduct)
class InventoryProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'warehouse', 'product', 'quantity', 'unit']
    list_filter = ['warehouse']
    search_fields = ['warehouse__warehouse_id', 'product__name']


@admin.register(DefaultItem)
class DefaultItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'item_type', 'content_type']
    list_filter = ['item_type', 'content_type']
