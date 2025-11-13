"""Admin registration for ProductionProgram.

This file was rewritten to remove hidden/null bytes that previously caused a
SyntaxError ("source code string cannot contain null bytes"). If additional
readonly logic is needed it can be extended safely.
"""

from django.contrib import admin
from .ProductionProgramModel import ProductionProgram


@admin.register(ProductionProgram)
class ProductionProgramAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'formula_id', 'product', 'planned_weight_ton', 'execution_date', 'packaging_type', 'status', 'priority_index', 'fulfillment_percentage'
    )
    list_filter = ('status', 'product')
    search_fields = ('formula_id', 'product__name', 'product__code')
    readonly_fields = (
        'consumption_summary', 'priority_index', 'fulfillment_percentage',
        'started_at', 'completed_at', 'planned_hours'
    )

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if obj and obj.status != ProductionProgram.Status.DRAFT:
            fields.extend([
                'formula_id', 'product', 'planned_weight_ton', 'predicted_start_time',
                'predicted_end_time', 'execution_date', 'packaging_type',
                'inventory_snapshot', 'net_unplanned_requirement'
            ])
        return fields
