from django.contrib import admin
from . import Warehouse, InventoryItem, DefaultItem


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['warehouse_id', 'warehouse_type']
    list_filter = ['warehouse_type']
    search_fields = ['warehouse_id']


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'warehouse', 'get_item_type', 'get_item_name', 'quantity', 'unit']
    list_filter = ['warehouse', 'content_type']
    search_fields = ['warehouse__warehouse_id', 'object_id']
    
    def get_item_type(self, obj):
        return obj.item_type or '-'
    get_item_type.short_description = 'نوع آیتم'
    
    def get_item_name(self, obj):
        return str(obj.item) if obj.item else '-'
    get_item_name.short_description = 'نام آیتم'


@admin.register(DefaultItem)
class DefaultItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'item_type', 'content_type']
    list_filter = ['item_type', 'content_type']
