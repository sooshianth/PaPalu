from django.contrib import admin
from . import StockEntry, SourceStock, TargetStock


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(SourceStock)
class SourceStockAdmin(admin.ModelAdmin):
    list_display = ['id', 'stock_entry']
    search_fields = ['stock_entry__stock_entry_number']


@admin.register(TargetStock)
class TargetStockAdmin(admin.ModelAdmin):
    list_display = ['id', 'stock_entry']
    search_fields = ['stock_entry__stock_entry_number']
