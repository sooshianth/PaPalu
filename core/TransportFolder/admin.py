from django.contrib import admin
from . import Transport, TruckInfo, ProductInfo, LoadingScheduleInfo, Fare


@admin.register(Transport)
class TransportAdmin(admin.ModelAdmin):
    list_display = ['waybill_number', 'driver']
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
