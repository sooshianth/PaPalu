from django.contrib import admin
from django import forms
from .ProductFolder import Product, ProductionInfo, BOM, QualityControl, ProductSales
from .RBACModel import TaskPermission, Role, UserTaskPermission, TaskChoices


class TaskPermissionForm(forms.ModelForm):
    tasks = forms.MultipleChoiceField(
        choices=TaskChoices.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select tasks for this permission set"
    )
    
    class Meta:
        model = TaskPermission
        fields = ['name', 'tasks']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.tasks:
            self.initial['tasks'] = self.instance.tasks
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.tasks = self.cleaned_data['tasks']
        if commit:
            instance.save()
        return instance


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
            'fields': ('invoice_description', 'full_description', 'lab_analysis', 'original_selection')
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
    list_display = ['raw_material', 'production_info', 'unit_used']
    search_fields = ['raw_material', 'production_info__product__name']
    list_filter = ['unit_used']


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


@admin.register(TaskPermission)
class TaskPermissionAdmin(admin.ModelAdmin):
    form = TaskPermissionForm
    list_display = ['name', 'get_tasks_display']
    search_fields = ['name']
    
    def get_tasks_display(self, obj):
        return ', '.join([TaskChoices(task).label for task in obj.tasks if task in TaskChoices.values])
    get_tasks_display.short_description = 'Tasks'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_permission']
    list_filter = ['name']
    filter_horizontal = ['users']


@admin.register(UserTaskPermission)
class UserTaskPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'task_permission']
    search_fields = ['user__username']
