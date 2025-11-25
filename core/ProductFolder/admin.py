from django.contrib import admin
from django import forms
from . import Product, ProductionInfo, BOM, QualityControl, ProductSales, ProductFinancialInfo


class BOMInline(admin.TabularInline):
    model = BOM
    extra = 1
    verbose_name = 'ماده اولیه'
    verbose_name_plural = 'مواد اولیه (BOM)'


class ProductionInfoInline(admin.StackedInline):
    model = ProductionInfo
    verbose_name = 'اطلاعات تولید'
    verbose_name_plural = 'اطلاعات تولید'


class QualityControlInline(admin.StackedInline):
    model = QualityControl
    verbose_name = 'کنترل کیفیت'
    verbose_name_plural = 'کنترل کیفیت'


class ProductSalesInline(admin.StackedInline):
    model = ProductSales
    verbose_name = 'اطلاعات فروش'
    verbose_name_plural = 'اطلاعات فروش'

class ProductFinancialInfoInline(admin.StackedInline):
    model = ProductFinancialInfo
    verbose_name = 'اطلاعات مالی محصول'
    verbose_name_plural = 'اطلاعات مالی محصول'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'physical_shape', 'is_custom', 'created_at']
    list_filter = ['category', 'physical_shape', 'is_custom', 'created_at']
    search_fields = ['code', 'name', 'category']
    inlines = [ProductionInfoInline, QualityControlInline, ProductSalesInline]
    
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('name', 'code', 'category', 'subcategory')
        }),
        ('مشخصات فیزیکی', {
            'fields': ('physical_shape', 'pellet_granule_diameter', 'image')
        }),
        ('توضیحات', {
            'fields': ('invoice_description', 'full_description', 'lab_analysis', 'grade', 'main_application')
        }),
        ('واحدها', {
            'fields': ('main_unit', 'secondary_unit', 'conversion_coefficient')
        }),
        ('سایر', {
            'fields': ('is_custom', 'expiration_date')
        }),
    )


@admin.register(ProductionInfo)
class ProductionInfoAdmin(admin.ModelAdmin):
    list_display = ['product', 'formula_id', 'production_time', 'min_batch_production']
    search_fields = ['product__name', 'product__code', 'formula_id']
    inlines = [BOMInline]


@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    list_display = ['raw_material', 'production_info', 'quantity']
    search_fields = ['raw_material__name', 'production_info__product__name']
    list_filter = ['raw_material']


@admin.register(QualityControl)
class QualityControlAdmin(admin.ModelAdmin):
    list_display = ['product', 'requires_post_production_test', 'density', 'moisture_level', 'protein', 'fat']
    search_fields = ['product__name', 'product__code']
    list_filter = ['requires_post_production_test', 'light_sensitive']


@admin.register(ProductSales)
class ProductSalesAdmin(admin.ModelAdmin):
    list_display = ['product', 'min_sales_amount', 'price_with_tax', 'inventory_existence']
    search_fields = ['product__name', 'product__code']
    list_filter = ['inventory_existence']


@admin.register(ProductFinancialInfo)
class ProductFinancialInfoAdmin(admin.ModelAdmin):
    list_display = ['product', 'price', 'deadline', 'condition', 'loading_date', 'condition_description', 'description']
    search_fields = ['product__name', 'product__code']
    list_filter = ['deadline', 'condition', 'loading_date']
