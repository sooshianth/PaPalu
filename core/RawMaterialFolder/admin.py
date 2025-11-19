from django.contrib import admin
from . import RawMaterial, RawMaterialPurchaseInfo, RawMaterialQualityControl, QualityParameter


@admin.register(RawMaterial)
class RawMaterialAdmin(admin.ModelAdmin):
    list_display = ['raw_material_id', 'name', 'physical_form', 'primary_unit', 'status']
    list_filter = ['physical_form', 'status']
    search_fields = ['raw_material_id', 'name', 'technical_description']
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('raw_material_id', 'name', 'physical_form', 'status')
        }),
        ('واحدها', {
            'fields': ('primary_unit', 'secondary_unit')
        }),
        ('توضیحات', {
            'fields': ('technical_description',)
        }),
    )


@admin.register(RawMaterialPurchaseInfo)
class RawMaterialPurchaseInfoAdmin(admin.ModelAdmin):
    list_display = ['raw_material', 'id']
    search_fields = ['raw_material__name']


@admin.register(RawMaterialQualityControl)
class RawMaterialQualityControlAdmin(admin.ModelAdmin):
    list_display = ['raw_material', 'id']
    search_fields = ['raw_material__name']


@admin.register(QualityParameter)
class QualityParameterAdmin(admin.ModelAdmin):
    list_display = ['id']


# No Supplier model: suppliers are Persons with type='supplier'
