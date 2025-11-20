from django.contrib import admin

# Import models explicitly from their modules for clarity
from .StockEntryModel import StockEntry
from .SourceStockModel import SourceStock
from .TargetStockModel import TargetStock


class SourceStockInline(admin.TabularInline):
    model = SourceStock
    extra = 0
    fields = ('get_item_display', 'from_warehouse', 'quantity', 'unit')
    readonly_fields = ('get_item_display', 'from_warehouse', 'quantity', 'unit')
    can_delete = False
    
    def get_item_display(self, obj):
        if obj.from_item:
            return str(obj.from_item)
        return f"{obj.from_content_type} (ID: {obj.from_object_id})"
    get_item_display.short_description = 'آیتم (صبح بخیر)'


class TargetStockInline(admin.TabularInline):
    model = TargetStock
    extra = 0
    fields = ('get_item_display', 'to_warehouse', 'quantity', 'unit')
    readonly_fields = ('get_item_display', 'to_warehouse', 'quantity', 'unit')
    can_delete = False
    
    def get_item_display(self, obj):
        if obj.to_item:
            return str(obj.to_item)
        return f"{obj.to_content_type} (ID: {obj.to_object_id})"
    get_item_display.short_description = 'آیتم (شب بخیر)'


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'transaction_date', 'is_committed', 'notes']
    list_filter = ['is_committed', 'transaction_date']
    search_fields = ['notes']
    inlines = [SourceStockInline, TargetStockInline]


@admin.register(SourceStock)
class SourceStockAdmin(admin.ModelAdmin):
    list_display = ['id', 'stock_entry', 'from_warehouse', 'quantity', 'unit']
    search_fields = ['stock_entry__id']


@admin.register(TargetStock)
class TargetStockAdmin(admin.ModelAdmin):
    list_display = ['id', 'stock_entry', 'to_warehouse', 'quantity', 'unit']
    search_fields = ['stock_entry__id']
