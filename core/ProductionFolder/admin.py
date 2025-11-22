"""Admin registration for ProductionProgram.

This file was rewritten to remove hidden/null bytes that previously caused a
SyntaxError ("source code string cannot contain null bytes"). If additional
readonly logic is needed it can be extended safely.
"""

from django.contrib import admin
from .ProductionProgramModel import ProductionProgram
from .ProductionRevertLogModel import ProductionRevertLog


@admin.register(ProductionProgram)
class ProductionProgramAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'program_id', 'product', 'planned_weight_ton', 'execution_date', 'packaging_type', 'status', 'is_denied', 'is_archived', 'priority_index', 'fulfillment_percentage'
    )
    list_filter = ('status', 'product')
    search_fields = ('program_id', 'product__name', 'product__code')
    readonly_fields = (
        'consumption_summary', 'priority_index', 'fulfillment_percentage',
        'started_at', 'completed_at', 'planned_hours'
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj and obj.status != ProductionProgram.Status.DRAFT:
            fields.extend([
                'program_id', 'product', 'planned_weight_ton', 'predicted_start_time',
                'predicted_end_time', 'execution_date', 'packaging_type',
                'inventory_snapshot', 'net_unplanned_requirement'
            ])
        return fields


@admin.register(ProductionRevertLog)
class ProductionRevertLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'production_program', 'action_type', 'created_by', 'created_at', 'reversal_stock_entry_id'
    )
    list_filter = ('action_type', 'created_at')
    search_fields = ('production_program__program_id', 'production_program__product__name', 'reason', 'created_by')
    readonly_fields = ('production_program', 'action_type', 'reason', 'created_by', 'created_at', 'reversal_stock_entry_id')
    
    def has_add_permission(self, request):
        # Prevent manual creation
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Allow deletion
        return True
