# Production Program - Implementation Status

## Rules Compliance Summary

### ✅ Fully Implemented Rules

1. **Rule 1 - Formula-based Planning**: Each production program is tied to a specific `formula_id`. Multiple formulas for a product are treated as separate programs.

2. **Rule 6 - Multiple Drafts**: Users can save multiple draft programs. Drafts are not sent to production and are not included in "planned inventory" calculations.

3. **Rule 8 - Edit/Delete/Priority**: Programs in `Draft` or `Confirmed` status can be edited. Once production starts (`In Progress`), the program is locked.

4. **Rule 9 - Partial Fulfillment**: The model tracks `produced_weight_ton` and `fulfillment_percentage` to handle partial completion.

5. **Rule 10 - Input Form**: Form includes fields for weight (tonnage) and predicted hours for production.

6. **Rule 11 - Live Calculations**: The model's `save()` method automatically calculates raw material consumption and planned hours from start/end times.

7. **Rule 12 - Draft vs Confirm Buttons**: Template includes separate buttons for "Save Draft" and "Confirm and Send to Production".

8. **Rule 13 - Lifecycle States**: Four states are implemented:
   - `Draft`: Planner has saved it
   - `Confirmed`: Sent to production queue
   - `In Progress`: Operator has started production (locked)
   - `Completed`: Production declaration submitted

### ⚠️ Partially Implemented Rules

9. **Rule 2 - Management Dashboard**: Dashboard structure exists but needs data integration:
   - ✅ Template structure created
   - ⚠️ Raw material inventory shows placeholder data (needs warehouse integration)
   - ⚠️ Product flow status calculates planned inventory but needs real warehouse/order data
   - ⚠️ Allocation list is empty (needs allocation model integration)

10. **Rule 3 - Raw Material Inventory Table**: 
    - ✅ Table structure exists
    - ⚠️ Shows BOM data but needs integration with warehouse system for actual inventory

11. **Rule 4 - Product Flow Status Table**:
    - ✅ Table structure with correct columns
    - ✅ Automatic sorting by "Net Unplanned Requirement" (highest first) via DataTables
    - ✅ Calculates "planned inventory" from confirmed programs
    - ⚠️ Needs integration with:
      - Warehouse system for actual inventory
      - Orders/allocation system for logistic-confirmed orders

12. **Rule 5 - Allocation List with Parent-Child Rows**:
    - ✅ Template structure with expandable rows
    - ⚠️ Needs allocation model and data
    - ⚠️ Needs logic to track which products in allocation are "ready to ship" vs "awaiting production"

13. **Rule 7 - Batch Creation**:
    - ✅ Spreadsheet-like UI structure in template
    - ✅ JavaScript for adding/removing rows
    - ⚠️ Backend endpoint for batch save not yet implemented
    - ⚠️ Needs AJAX handler or form processing for multiple programs at once

## Required Integrations for Full Compliance

### 1. Warehouse System Integration
**Files to modify**: `production/views/program_views.py`

```python
# Replace placeholder in _get_dashboard_context():
# Current:
inventory = 0  # Placeholder

# Needed:
from warehousing.models import Inventory
inventory = Inventory.objects.filter(
    product=prod_info.product
).aggregate(total=Sum('quantity'))['total'] or 0

# For raw material inventory:
for item in raw_material_inventory:
    inv = Inventory.objects.filter(
        raw_material_id=item['raw_material_id']
    ).aggregate(total=Sum('quantity'))['total'] or 0
    item['current_inventory'] = inv
```

### 2. Allocation/Order System Integration
**Files to modify**: `production/views/program_views.py`

```python
# In _get_dashboard_context():
from core.AllocationFolder.AllocationModel import Allocation

# For product flow status:
logistic_confirmed = Allocation.objects.filter(
    status='logistic_confirmed',
    products__product=prod_info.product
).aggregate(total=Sum('products__weight'))['total'] or 0

# For allocation table:
allocations = Allocation.objects.filter(
    status='logistic_confirmed'
).prefetch_related('products').all()

# Format allocations for template
formatted_allocations = []
for alloc in allocations:
    products = []
    for prod in alloc.products.all():
        products.append({
            'product': prod.product.name,
            'weight': prod.weight,
            'status': 'آماده ارسال' if prod.ready_to_ship else 'نیاز به تولید'
        })
    formatted_allocations.append({
        'id': alloc.id,
        'status': alloc.get_status_display(),
        'total_weight': sum(p['weight'] for p in products),
        'products': products
    })
```

### 3. Batch Creation Backend
**Files to create/modify**: `production/views/program_views.py`, `production/urls.py`

```python
# Add new view:
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

@require_POST
def batch_create_programs(request):
    """Create multiple production programs at once"""
    products = request.POST.getlist('batch_product[]')
    formulas = request.POST.getlist('batch_formula[]')
    weights = request.POST.getlist('batch_weight[]')
    hours = request.POST.getlist('batch_hours[]')
    statuses = request.POST.getlist('batch_status[]')
    
    created_count = 0
    with transaction.atomic():
        for i in range(len(products)):
            if products[i] and formulas[i]:
                ProductionProgram.objects.create(
                    product_id=products[i],
                    formula_id=formulas[i],
                    planned_weight_ton=weights[i] or 0,
                    planned_hours=hours[i] or 0,
                    status=statuses[i] or 'draft'
                )
                created_count += 1
    
    return JsonResponse({
        'success': True,
        'created_count': created_count,
        'message': f'{created_count} برنامه ایجاد شد.'
    })

# Add to urls.py:
path('programs/batch-create/', views.batch_create_programs, name='program_batch_create'),
```

### 4. Live Calculation Enhancements (Rule 11)
**Current**: Calculations happen on save  
**Enhancement Needed**: Add AJAX endpoint for live preview

```python
# Add view:
from django.http import JsonResponse

def calculate_consumption_preview(request):
    """AJAX endpoint for live material consumption calculation"""
    production_info_id = request.GET.get('production_info_id')
    weight = float(request.GET.get('weight', 0))
    
    if not production_info_id or not weight:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    prod_info = get_object_or_404(ProductionInfo, id=production_info_id)
    min_batch = prod_info.min_batch_production or 1
    
    consumption = {}
    for bom in prod_info.bom_items.all():
        if bom.quantity:
            required = (bom.quantity * weight) / float(min_batch)
            consumption[bom.raw_material or bom.raw_material_id] = round(required, 4)
    
    return JsonResponse({
        'consumption': consumption,
        'total_weight': weight
    })
```

Then add JavaScript in template to call this on input change.

## Testing Checklist

- [ ] Create multiple draft programs for same formula
- [ ] Confirm a program and verify fields lock
- [ ] Start production and verify program becomes non-editable
- [ ] Test partial fulfillment tracking
- [ ] Verify product flow table sorts by net unplanned requirement
- [ ] Test allocation parent-child row expansion
- [ ] Test batch creation UI (add/remove rows)
- [ ] Implement and test batch save endpoint
- [ ] Test integration with warehouse for inventory display
- [ ] Test integration with orders for logistic-confirmed requirement

## Priority Order for Remaining Work

1. **High Priority**: Implement batch creation backend (Rule 7)
2. **High Priority**: Integrate warehouse system for inventory (Rules 3, 4)
3. **Medium Priority**: Integrate allocation/order system (Rules 4, 5)
4. **Medium Priority**: Add AJAX for live calculations (Rule 11)
5. **Low Priority**: Polish UI and add more detailed error handling

## Notes

- The DataTables library automatically handles sorting for Rule 4
- Field locking is implemented via form `__init__` method and model `is_locked` property
- Status transitions are enforced in view logic (forward-only progression)
- All Persian labels are in place per requirements
