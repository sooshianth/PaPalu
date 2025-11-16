from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db.models import Sum, Q
from django.db import OperationalError
from production.forms.program_form import ProductionProgramForm
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductionInfoModel import ProductionInfo


def _get_dashboard_context():
    """Helper function to gather dashboard data for all three tables"""
    
    # Table 1: Raw Material Inventory (placeholder - needs warehouse integration)
    raw_material_inventory = BOM.objects.values(
        'raw_material_id', 'raw_material', 'unit_used'
    ).distinct()
    # Add placeholder inventory (TODO: integrate with warehouse system)
    for item in raw_material_inventory:
        item['current_inventory'] = 0  # Placeholder
    
    # Table 2: Product Flow Status
    product_flow_status = []
    production_infos = ProductionInfo.objects.select_related('product').all()
    
    db_issue = False
    for prod_info in production_infos:
        try:
            # Calculate planned inventory (sum of confirmed but not started programs)
            planned_inventory = ProductionProgram.objects.filter(
                production_info=prod_info,
                status=ProductionProgram.Status.CONFIRMED
            ).aggregate(total=Sum('planned_weight_ton'))['total'] or 0
        except OperationalError:
            # Missing table or schema drift – mark issue and fallback to zero
            planned_inventory = 0
            db_issue = True

        # Placeholder for inventory and logistic confirmed orders
        inventory = 0  # TODO: integrate with warehouse
        logistic_confirmed = 0  # TODO: integrate with orders/allocation

        # Calculate net unplanned requirement
        net_unplanned = logistic_confirmed - (inventory + planned_inventory)

        product_flow_status.append({
            'product': prod_info.product.name if prod_info.product else '-',
            'program_id': prod_info.formula_id or '-',
            'inventory': inventory,
            'planned_inventory': planned_inventory,
            'net_unplanned_requirement': net_unplanned,
            'status': 'نیازمند برنامه‌ریزی' if net_unplanned > 0 else 'کافی'
        })
    
    # Sort by net_unplanned_requirement descending (highest need first)
    product_flow_status.sort(key=lambda x: x['net_unplanned_requirement'], reverse=True)
    
    # Table 3: Allocations (placeholder - needs allocation model)
    allocations = []
    # TODO: Query allocation model when available
    # allocations = Allocation.objects.filter(
    #     status='logistic_confirmed'
    # ).prefetch_related('products')
    
    return {
        'raw_material_inventory': raw_material_inventory,
        'product_flow_status': product_flow_status,
        'allocations': allocations,
        'db_integrity_issue': db_issue,
    }


def create_program_view(request):
    """ایجاد / پیش نویس / تایید برنامه تولید"""
    if request.method == 'POST':
        action = request.POST.get('action')  # draft / confirm / start / complete
        form = ProductionProgramForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            # Set status based on action
            if action == 'confirm':
                instance.status = ProductionProgram.Status.CONFIRMED
            elif action == 'start':
                instance.status = ProductionProgram.Status.IN_PROGRESS
            elif action == 'complete':
                instance.status = ProductionProgram.Status.COMPLETED
            else:
                instance.status = ProductionProgram.Status.DRAFT
            instance.save()
            messages.success(request, 'برنامه ذخیره شد.')
            return redirect(reverse('production:program_edit', args=[instance.id]))
    else:
        form = ProductionProgramForm()
    
    context = {
        'form': form,
        'mode': 'create',
    }
    context.update(_get_dashboard_context())
    # Template path corrected: file resides at production/templates/program_form.html
    return render(request, 'program_form.html', context)


def edit_program_view(request, program_id):
    program = get_object_or_404(ProductionProgram, id=program_id)
    if request.method == 'POST':
        action = request.POST.get('action')
        form = ProductionProgramForm(request.POST, instance=program)
        if form.is_valid():
            instance = form.save(commit=False)
            # Status transitions (only allowed forward)
            if action == 'confirm' and instance.status == ProductionProgram.Status.DRAFT:
                instance.status = ProductionProgram.Status.CONFIRMED
            elif action == 'start' and instance.status == ProductionProgram.Status.CONFIRMED:
                instance.status = ProductionProgram.Status.IN_PROGRESS
            elif action == 'complete' and instance.status == ProductionProgram.Status.IN_PROGRESS:
                instance.status = ProductionProgram.Status.COMPLETED
            instance.save()
            messages.success(request, 'برنامه بهروز شد.')
            return redirect(reverse('production:program_edit', args=[instance.id]))
    else:
        form = ProductionProgramForm(instance=program)
    
    context = {
        'form': form,
        'program': program,
        'mode': 'edit',
    }
    context.update(_get_dashboard_context())
    # Template path corrected: file resides at production/templates/program_form.html
    return render(request, 'program_form.html', context)


def program_list_view(request):
    programs = ProductionProgram.objects.all().select_related('product', 'production_info')
    # Adjusted template path if list template follows same structure; fallback to simple list page
    return render(request, 'program_list.html', {'programs': programs})
