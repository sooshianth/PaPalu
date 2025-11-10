from django.contrib import admin
from . import Allocation, AllocationProductInfo, AllocationSchedulingInfo


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ['allocation_number', 'order']
    search_fields = ['allocation_number', 'order__order_number']


@admin.register(AllocationProductInfo)
class AllocationProductInfoAdmin(admin.ModelAdmin):
    list_display = ['id', 'allocation']
    search_fields = ['allocation__allocation_number']


@admin.register(AllocationSchedulingInfo)
class AllocationSchedulingInfoAdmin(admin.ModelAdmin):
    list_display = ['id', 'allocation']
    search_fields = ['allocation__allocation_number']
