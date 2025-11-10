from django.contrib import admin
from . import Warehouse, Inventory, InventoryProduct, DefaultItem


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['warehouse_id', 'warehouse_type']
    list_filter = ['warehouse_type']
    search_fields = ['warehouse_id']


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'warehouse', 'date']
    list_filter = ['warehouse', 'date']
    search_fields = ['warehouse__warehouse_name']
    date_hierarchy = 'date'


@admin.register(InventoryProduct)
class InventoryProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'inventory']
    search_fields = ['inventory__warehouse__warehouse_name']


@admin.register(DefaultItem)
class DefaultItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'item_type', 'content_type']
    list_filter = ['item_type', 'content_type']
