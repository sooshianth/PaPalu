from django.contrib import admin
from . import Transport, TruckInfo, ProductInfo, LoadingScheduleInfo, Fare
from .RawMaterialInfoModel import RawMaterialInfo


@admin.register(Transport)
class TransportAdmin(admin.ModelAdmin):
    list_display = ['id', 'waybill_number', 'driver']
    search_fields = ['waybill_number']


@admin.register(TruckInfo)
class TruckInfoAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'transport', 'vehicle_type']
    list_filter = ['vehicle_type']
    search_fields = ['plate_number']


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ['id', 'transport', 'product', 'raw_material']
    search_fields = ['transport__waybill_number']


@admin.register(LoadingScheduleInfo)
class LoadingScheduleInfoAdmin(admin.ModelAdmin):
    list_display = ['id', 'transport']
    search_fields = ['transport__waybill_number']


@admin.register(Fare)
class FareAdmin(admin.ModelAdmin):
    list_display = ['id', 'transport']
    search_fields = ['transport__waybill_number']


@admin.register(RawMaterialInfo)
class RawMaterialInfoAdmin(admin.ModelAdmin):
    list_display = [
        'transport', 'raw_material', 'allocated_quantity', 'net_weight',
        'unloading_weight_before', 'unloading_weight_after',
        'waybill_gross_weight', 'waybill_tare_weight', 'waybill_weight',
        'scale_serial', 'weight_unit', 'created_at'
    ]
    list_filter = ['weight_unit', 'transport__status', 'created_at']
    search_fields = ['transport__transport_number', 'transport__waybill_number', 'raw_material__name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('اطلاعات حمل و ماده اولیه', {
            'fields': ('transport', 'order_item', 'raw_material')
        }),
        ('اطلاعات وزن', {
            'fields': (
                'allocated_quantity', 'net_weight', 'unloading_weight_before',
                'unloading_weight_after', 'scale_serial', 'weight_unit'
            )
        }),
        ('اطلاعات وزن بارنامه', {
            'fields': ('waybill_gross_weight', 'waybill_tare_weight', 'waybill_weight')
        }),
        ('اطلاعات بسته‌بندی', {
            'fields': ('packaging_type', 'number_of_packages'),
            'classes': ('collapse',)
        }),
        ('یادداشت‌ها', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
