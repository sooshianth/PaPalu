from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.db import OperationalError
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from collections import defaultdict
import logging
import json
from core.logging_levels import *
from core.RBACModel import user_can_access_field
from production.forms.program_form import ProductionProgramForm
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from production.tables import ProductionProgramTable
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.ProductModel import Product
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from django_tables2 import RequestConfig
from core.RBACModel import user_has_task, TaskChoices
from django.http import HttpResponseForbidden

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_production_info_fields(user):
    """بررسی دسترسی کاربر به فیلدهای ProductionInfo - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['formula_id'] = user_can_access_field(user, ProductionInfo, 'formula_id', 'view')
    accessible_fields['min_batch_production'] = user_can_access_field(user, ProductionInfo, 'min_batch_production', 'view')
    accessible_fields['specific_production_instruction'] = user_can_access_field(user, ProductionInfo, 'specific_production_instruction', 'view')
    return accessible_fields


def get_accessible_bom_fields(user):
    """بررسی دسترسی کاربر به فیلدهای BOM - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['raw_material'] = user_can_access_field(user, BOM, 'raw_material', 'view')
    accessible_fields['quantity'] = user_can_access_field(user, BOM, 'quantity', 'view')  # DELETE LATER
    accessible_fields['percentage'] = user_can_access_field(user, BOM, 'percentage', 'view')
    accessible_fields['unit_used'] = user_can_access_field(user, BOM, 'unit_used', 'view')
    return accessible_fields


def get_accessible_raw_material_fields(user):
    """بررسی دسترسی کاربر به فیلدهای RawMaterial - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['raw_material_id'] = user_can_access_field(user, RawMaterial, 'raw_material_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, RawMaterial, 'name', 'view')
    return accessible_fields


def _calculate_product_inventory_and_requirement(product):
    """
    Calculate inventory_snapshot and net_unplanned_requirement for a product.
    Returns: (inventory_snapshot, net_unplanned_requirement)
    """
    if not product:
        return Decimal('0'), Decimal('0')
    
    try:
        # Get content type for Product
        product_ct = ContentType.objects.get_for_model(Product)
        
        # Calculate inventory: sum of all InventoryItem quantities for this product across all warehouses
        inventory_result = InventoryItem.objects.filter(
            content_type=product_ct,
            object_id=str(product.id)
        ).aggregate(total=Sum('quantity'))['total']
        inventory = Decimal(str(inventory_result)) if inventory_result else Decimal('0')
        
        # Calculate planned_inventory: sum of planned_weight_ton for CONFIRMED and IN_PROGRESS statuses
        # Exclude COMPLETED status
        planned_result = ProductionProgram.objects.filter(
            product=product,
            status__in=[ProductionProgram.Status.CONFIRMED, ProductionProgram.Status.IN_PROGRESS]
        ).aggregate(total=Sum('planned_weight_ton'))['total']
        planned_inventory = Decimal(str(planned_result)) if planned_result else Decimal('0')
        
        # Calculate logistic_confirmed: sum of quantities from order items of orders with pending_factory status
        # Convert all quantities to kg for consistency
        logistic_confirmed = Decimal('0')
        try:
            orders_pending_factory = Order.objects.filter(
                status='pending_factory',
                order_type='sale'
            )
            for order in orders_pending_factory:
                order_items = OrderItem.objects.filter(
                    order=order,
                    product=product
                )
                for item in order_items:
                    if item.quantity and item.weight_unit:
                        quantity = Decimal(str(item.quantity))
                        # Convert to kg
                        if item.weight_unit == 'kg':
                            logistic_confirmed += quantity
                        elif item.weight_unit == 'ton':
                            logistic_confirmed += quantity * Decimal('1000')
                        elif item.weight_unit == 'bag' and item.bag_weight:
                            # Convert bags to kg using bag_weight
                            logistic_confirmed += quantity * Decimal(str(item.bag_weight))
                        # For 'piece' unit, we skip it as it's not a weight unit
        except Exception as e:
            bug_logger.warning(f"Error calculating logistic_confirmed for product {product.id}: {str(e)}")
        
        # Calculate net_unplanned_requirement: logistic_confirmed - (inventory + planned_inventory)
        net_unplanned = logistic_confirmed - (inventory + planned_inventory)
        
        return inventory, net_unplanned
    except Exception as e:
        bug_logger.warning(f"Error calculating inventory for product {product.id}: {str(e)}")
        return Decimal('0'), Decimal('0')


def _get_dashboard_context():
    """Helper: gathers dashboard data for inventory, flow status, and allocations."""
    audit_logger.debug("جمع‌آوری داده‌های داشبورد برنامه تولید")
    try:
        # Get raw material inventory from primary warehouses only
        raw_materials_inventory = []
        try:
            # Find primary warehouses only
            primary_warehouses = Warehouse.objects.filter(warehouse_type='primary')
            bug_logger.debug(f"Number of primary warehouses: {primary_warehouses.count()}")
            
            if primary_warehouses.exists():
                # Get content type for RawMaterial
                try:
                    raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
                    
                    # Get inventory items that are raw materials from primary warehouses only
                    inventory_items = InventoryItem.objects.filter(
                        warehouse__in=primary_warehouses,
                        content_type=raw_material_ct
                    ).select_related('warehouse', 'content_type')
                    
                    bug_logger.debug(f"Number of raw material inventory items: {inventory_items.count()}")
                    
                    # Group raw materials by raw_material_id and sum inventory from warehouses
                    raw_materials_grouped = defaultdict(lambda: {
                        'raw_material_id': '',
                        'name': '',
                        'total_quantity': Decimal('0'),
                        'unit': '',
                        'warehouses': []
                    })
                    
                    for item in inventory_items:
                        try:
                            raw_material = item.item  # Generic relation
                            if raw_material is None:
                                bug_logger.warning(f"Raw material with id {item.object_id} not found")
                                continue
                            
                            if raw_material:
                                rm_id = getattr(raw_material, 'raw_material_id', '-')
                                quantity = item.quantity if item.quantity else Decimal('0')
                                
                                # Sum total inventory
                                raw_materials_grouped[rm_id]['raw_material_id'] = rm_id
                                raw_materials_grouped[rm_id]['name'] = getattr(raw_material, 'name', '-')
                                raw_materials_grouped[rm_id]['total_quantity'] += quantity
                                raw_materials_grouped[rm_id]['unit'] = item.unit or 'ton'
                                
                                # Store warehouse details
                                raw_materials_grouped[rm_id]['warehouses'].append({
                                    'id': item.warehouse.id,
                                    'warehouse_id': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'warehouse_name': item.warehouse.name if (item.warehouse and item.warehouse.name) else (str(item.warehouse) if item.warehouse else '-'),
                                    'quantity': str(quantity),
                                })
                        except Exception as e:
                            bug_logger.warning(f"Error loading raw material: {str(e)}")
                            continue
                    
                    # Convert to list format for backward compatibility
                    raw_material_inventory = []
                    for rm_id, data in raw_materials_grouped.items():
                        raw_material_inventory.append({
                            'raw_material_id': data['raw_material_id'],
                            'raw_material': data['name'],
                            'unit_used': data['unit'],
                            'current_inventory': str(data['total_quantity']),
                        })
                    
                    # Also create the expanded format for the floating card
                    raw_materials_inventory = []
                    for rm_id, data in raw_materials_grouped.items():
                        raw_materials_inventory.append({
                            'raw_material_id': data['raw_material_id'],
                            'name': data['name'],
                            'total_quantity': str(data['total_quantity']),
                            'unit': data['unit'],
                            'warehouses': data['warehouses']
                        })
                    
                    bug_logger.debug(f"Number of processed raw materials: {len(raw_material_inventory)}")
                    
                except ContentType.DoesNotExist:
                    bug_logger.warning("ContentType for RawMaterial not found")
                    raw_material_inventory = []
                    raw_materials_inventory = []
                except Exception as e:
                    bug_logger.warning(f"Error getting raw material inventory: {str(e)}")
                    raw_material_inventory = []
                    raw_materials_inventory = []
            else:
                bug_logger.warning("No warehouses found")
                raw_material_inventory = []
                raw_materials_inventory = []
        
        except Exception as e:
            bug_logger.error(f"General error in getting raw material inventory: {str(e)}")
            raw_material_inventory = []
            raw_materials_inventory = []

        product_flow_status = []
        db_issue = False
        
        # Get content type for Product to query InventoryItem
        try:
            product_ct = ContentType.objects.get_for_model(Product)
        except ContentType.DoesNotExist:
            bug_logger.warning("ContentType for Product not found")
            product_ct = None
        
        # Pre-compute inventory totals for products across ALL warehouses
        inventory_totals = {}
        if product_ct:
            try:
                inventory_qs = InventoryItem.objects.filter(content_type=product_ct) \
                    .values('object_id').annotate(total=Sum('quantity'))
                for row in inventory_qs:
                    # Ensure Decimal precision
                    total = row['total'] if row['total'] is not None else Decimal('0')
                    inventory_totals[str(row['object_id'])] = Decimal(str(total))
            except Exception as e:
                bug_logger.warning(f"Error aggregating product inventory: {str(e)}")
                inventory_totals = {}
        
        # Pre-compute planned inventory for products (confirmed + in progress only)
        try:
            planned_qs = ProductionProgram.objects.filter(
                status__in=[ProductionProgram.Status.CONFIRMED, ProductionProgram.Status.IN_PROGRESS]
            ).values('product').annotate(total=Sum('planned_weight_ton'))
            planned_totals = {}
            for row in planned_qs:
                if row['product']:
                    # Ensure Decimal precision
                    total = row['total'] if row['total'] is not None else Decimal('0')
                    planned_totals[str(row['product'])] = Decimal(str(total))
        except OperationalError:
            planned_totals = {}
            db_issue = True
            bug_logger.warning("خطای عملیاتی هنگام محاسبه موجودی برنامه‌ریزی شده")
        except Exception as e:
            planned_totals = {}
            bug_logger.warning(f"Error aggregating planned inventory: {str(e)}")
        
        # Pre-compute logistic_confirmed from orders with pending_factory status
        logistic_confirmed_totals = {}
        try:
            orders_pending_factory = Order.objects.filter(
                status='pending_factory',
                order_type='sale'
            ).prefetch_related('order_items')
            for order in orders_pending_factory:
                for item in order.order_items.all():
                    if item.product and item.quantity and item.weight_unit:
                        product_id = str(item.product.id)
                        quantity = Decimal(str(item.quantity))
                        # Convert to kg
                        if item.weight_unit == 'kg':
                            quantity_kg = quantity
                        elif item.weight_unit == 'ton':
                            quantity_kg = quantity * Decimal('1000')
                        elif item.weight_unit == 'bag' and item.bag_weight:
                            quantity_kg = quantity * Decimal(str(item.bag_weight))
                        else:
                            quantity_kg = Decimal('0')  # Skip 'piece' or invalid units
                        
                        if product_id not in logistic_confirmed_totals:
                            logistic_confirmed_totals[product_id] = Decimal('0')
                        logistic_confirmed_totals[product_id] += quantity_kg
        except Exception as e:
            bug_logger.warning(f"Error calculating logistic_confirmed totals: {str(e)}")
            logistic_confirmed_totals = {}
        
        # Build flow status per product (unique), ignoring formula differences
        products = Product.objects.filter(production_infos__isnull=False).distinct()
        for product in products:
            product_id = str(product.id)
            planned_inventory = Decimal(str(planned_totals.get(product_id, 0)))
            inventory = Decimal(str(inventory_totals.get(product_id, 0)))
            logistic_confirmed = Decimal(str(logistic_confirmed_totals.get(product_id, 0)))
            net_unplanned = logistic_confirmed - (inventory + planned_inventory)
            
            product_flow_status.append({
                'product_id': product.id,
                'product': product.name if product else '-',
                'program_id': '-',  # formula ignored in dashboard view
                'inventory': str(inventory),  # Keep as string for JSON to preserve Decimal precision
                'planned_inventory': str(planned_inventory),  # Keep as string for JSON to preserve Decimal precision
                'net_unplanned_requirement': str(net_unplanned),  # Keep as string for JSON to preserve Decimal precision
                'status': 'نیازمند برنامه‌ریزی' if net_unplanned > 0 else 'کافی'
            })

        # Sort by numeric value (convert string back to Decimal for comparison)
        product_flow_status.sort(key=lambda x: Decimal(x['net_unplanned_requirement']), reverse=True)
        
        # Get allocations from orders with pending_factory status
        allocations = []
        try:
            orders_pending_factory = Order.objects.filter(
                status='pending_factory',
                order_type='sale'
            ).prefetch_related('allocations__product_infos__product')
            
            for order in orders_pending_factory:
                order_allocations = order.allocations.all()
                for allocation in order_allocations:
                    # Calculate total weight for this allocation
                    total_weight_kg = Decimal('0')
                    products_list = []
                    
                    for product_info in allocation.product_infos.all():
                        if product_info.quantity and product_info.unit:
                            quantity = Decimal(str(product_info.quantity))
                            # Convert to kg
                            if product_info.unit == 'kg':
                                quantity_kg = quantity
                            elif product_info.unit == 'ton':
                                quantity_kg = quantity * Decimal('1000')
                            elif product_info.unit == 'gr':
                                quantity_kg = quantity / Decimal('1000')
                            else:
                                quantity_kg = Decimal('0')  # Skip other units
                            
                            total_weight_kg += quantity_kg
                            products_list.append({
                                'product': product_info.product.name if product_info.product else '-',
                                'weight': str(quantity_kg),
                                'status': product_info.get_unit_display() if product_info.unit else '-'
                            })
                    
                    allocations.append({
                        'id': allocation.allocation_number or str(allocation.pk),
                        'order_number': order.order_number,
                        'allocation_number': allocation.allocation_number or str(allocation.pk),
                        'status': allocation.get_allocation_status_display() if allocation.allocation_status else '-',
                        'total_weight': str(total_weight_kg),
                        'products': products_list
                    })
        except Exception as e:
            bug_logger.warning(f"Error loading allocations: {str(e)}")
            allocations = []
        return {
            'raw_material_inventory': raw_material_inventory,
            'raw_materials_inventory': raw_materials_inventory,  # Expanded format for floating card
            'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
            'product_flow_status': product_flow_status,
            'allocations': allocations,
            'db_integrity_issue': db_issue,
        }
    except Exception as e:
        bug_logger.error(f"Dashboard context error: {e}")
        return {
            'raw_material_inventory': [],
            'raw_materials_inventory': [],
            'raw_materials_inventory_json': json.dumps([]),
            'product_flow_status': [],
            'allocations': [],
            'db_integrity_issue': False
        }


def _prepare_bom_data(request):
    """Helper: prepares BOM data and production info data for JavaScript."""
    try:
        accessible_production_info_fields = get_accessible_production_info_fields(request.user)
        accessible_bom_fields = get_accessible_bom_fields(request.user)
        accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
        
        production_infos_data = {}
        bom_data = {}
        
        all_production_infos = ProductionInfo.objects.all().select_related('product').prefetch_related('bom_items')
        for prod_info in all_production_infos:
            product_id = prod_info.product.id if prod_info.product else None
            if product_id:
                if product_id not in production_infos_data:
                    production_infos_data[product_id] = []
                
                prod_info_payload = {'id': prod_info.id}
                if accessible_production_info_fields.get('formula_id'):
                    prod_info_payload['program_id'] = prod_info.formula_id or ''
                if accessible_production_info_fields.get('min_batch_production'):
                    prod_info_payload['min_batch_production'] = str(prod_info.min_batch_production) if prod_info.min_batch_production else ''
                if accessible_production_info_fields.get('specific_production_instruction'):
                    prod_info_payload['specific_production_instruction'] = prod_info.specific_production_instruction or ''
                production_infos_data[product_id].append(prod_info_payload)
                
                # Prepare BOM data
                bom_items = []
                for bom in prod_info.bom_items.all():
                    bom_item_payload = {'id': bom.id}
                    # Include raw material related fields only if both relationship and target fields are viewable
                    if accessible_bom_fields.get('raw_material') and accessible_raw_material_fields.get('raw_material_id'):
                        bom_item_payload['raw_material_id'] = bom.raw_material.raw_material_id if bom.raw_material else '-'
                    if accessible_bom_fields.get('raw_material') and accessible_raw_material_fields.get('name'):
                        bom_item_payload['raw_material_name'] = bom.raw_material.name if bom.raw_material else '-'
                        if accessible_bom_fields.get('percentage'):
                            bom_item_payload['percentage'] = str(bom.percentage) if bom.percentage else '0'
                    if accessible_bom_fields.get('unit_used'):
                        bom_item_payload['unit_used'] = bom.raw_material.primary_unit if (bom.raw_material and bom.raw_material.primary_unit) else '-'
                    bom_items.append(bom_item_payload)
                
                bom_data[prod_info.id] = {
                    'program_id': prod_info.formula_id or '',
                    'min_batch_production': str(prod_info.min_batch_production) if prod_info.min_batch_production else '',
                    'specific_production_instruction': prod_info.specific_production_instruction or '',
                    'bom_items': bom_items
                }
        
        return {
            'production_infos_json': json.dumps(production_infos_data),
            'bom_data_json': json.dumps(bom_data),
            'accessible_production_info_fields': accessible_production_info_fields,
            'accessible_bom_fields': accessible_bom_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_production_info_fields_json': json.dumps(accessible_production_info_fields),
            'accessible_bom_fields_json': json.dumps(accessible_bom_fields),
            'accessible_raw_material_fields_json': json.dumps(accessible_raw_material_fields),
        }
    except Exception as e:
        bug_logger.error(f"Error preparing BOM data: {str(e)}")
        return {
            'production_infos_json': json.dumps({}),
            'bom_data_json': json.dumps({}),
            'accessible_production_info_fields': {},
            'accessible_bom_fields': {},
            'accessible_raw_material_fields': {},
            'accessible_production_info_fields_json': json.dumps({}),
            'accessible_bom_fields_json': json.dumps({}),
            'accessible_raw_material_fields_json': json.dumps({}),
        }


@login_required
def create_program_view(request):
    """ایجاد / پیش نویس / تایید برنامه تولید"""
    if not user_has_task(request.user, TaskChoices.PRODUCTION_REGISTER_NEW_SCHEDULE.value):
        audit_logger.activity("تلاش برای ایجاد برنامه تولید بدون دسترسی")
        messages.error(request, 'شما دسترسی به ثبت برنامه تولید جدید ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    audit_logger.info("دسترسی به ایجاد برنامه تولید")
    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            bug_logger.debug(f"POST action={action}")
            bug_logger.debug(f"Date fields received - start_date: {request.POST.get('predicted_start_date')}, start_time: {request.POST.get('predicted_start_time')}, end_date: {request.POST.get('predicted_end_date')}, end_time: {request.POST.get('predicted_end_time')}")
            # Create mutable copy and set status based on action BEFORE validation
            post_data = request.POST.copy()
            if action == 'confirm':
                post_data['status'] = ProductionProgram.Status.CONFIRMED
            elif action == 'start':
                post_data['status'] = ProductionProgram.Status.IN_PROGRESS
            elif action == 'complete':
                post_data['status'] = ProductionProgram.Status.COMPLETED
            else:
                post_data['status'] = ProductionProgram.Status.DRAFT
            
            form = ProductionProgramForm(post_data)
            if form.is_valid():
                instance = form.save(commit=False)
                
                # Validate planned weight against min_batch_production (for all actions that create/modify program)
                if action in ['draft', 'confirm', 'start'] and instance.production_info and instance.production_info.min_batch_production:
                    min_batch = instance.production_info.min_batch_production
                    if instance.planned_weight_ton and instance.planned_weight_ton < min_batch:
                        error_msg = f'تناژ برنامه ({instance.planned_weight_ton} کیلوگرم) کمتر از حداقل وزن تولید ({min_batch} کیلوگرم) است. لطفاً تناژ برنامه را افزایش دهید.'
                        bug_logger.warning(f"Validation failed: {error_msg}")
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                            return JsonResponse({'ok': False, 'errors': {'planned_weight_ton': [error_msg]}}, status=400)
                        messages.error(request, error_msg)
                        context = {'form': form, 'mode': 'create'}
                        context.update(_get_dashboard_context())
                        context.update(_prepare_bom_data(request))
                        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
                        return render(request, 'program_form.html', context)
                
                # Calculate and set inventory_snapshot and net_unplanned_requirement
                if instance.product:
                    inventory_snapshot, net_unplanned = _calculate_product_inventory_and_requirement(instance.product)
                    instance.inventory_snapshot = inventory_snapshot
                    instance.net_unplanned_requirement = net_unplanned
                
                # Status already set from form data
                instance.save()
                bug_logger.info(f"برنامه با موفقیت ذخیره شد. ID={instance.id}, Status={instance.status}")
                messages.success(request, 'برنامه ذخیره شد.')
                # AJAX-friendly JSON
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                    return JsonResponse({
                        'ok': True,
                        'id': instance.id,
                        'status': instance.status,
                        'detail_url': reverse('production:program_edit', args=[instance.id])
                    })
                return redirect(reverse('production:program_edit', args=[instance.id]))
            else:
                bug_logger.warning(f"فرم نامعتبر است. Errors: {form.errors.as_json()}")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                    return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        else:
            form = ProductionProgramForm()

        context = {'form': form, 'mode': 'create'}
        context.update(_get_dashboard_context())
        context.update(_prepare_bom_data(request))
        # Add field access permissions
        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
        # Add product inventory data for JavaScript auto-fill
        safe_flow = context.get('product_flow_status', [])
        context['product_flow_status_json'] = json.dumps(safe_flow, default=str)
        return render(request, 'program_form.html', context)
    except Exception as e:
        bug_logger.error(f"Create program error: {e}")
        messages.error(request, 'خطا در ثبت برنامه.')
        context = {'form': ProductionProgramForm(), 'mode': 'create'}
        context.update(_get_dashboard_context())
        context.update(_prepare_bom_data(request))
        # Add field access permissions
        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
        return render(request, 'program_form.html', context)


@login_required
def edit_program_view(request, program_id):
    audit_logger.info("دسترسی به ویرایش برنامه تولید")
    program = get_object_or_404(ProductionProgram, id=program_id)

    # بررسی دسترسی: برنامه ارجاع‌شده به مدیر را غیرمدیر هم می‌بیند (فقط مشاهده بدون امکان تغییر وضعیت)
    if getattr(program, 'declaration_referred_to_manager', False):
        if not request.user.is_superuser:
            pass  # اجازه مشاهده صفحه داده می‌شود؛ دکمه‌های تغییر وضعیت در قالب غیرفعال هستند
    elif not user_has_task(request.user, TaskChoices.PRODUCTION_REGISTER_NEW_SCHEDULE.value):
        audit_logger.activity("تلاش برای ویرایش برنامه تولید بدون دسترسی")
        messages.error(request, 'شما دسترسی به ویرایش برنامه تولید ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    try:
        # حل توسط مدیر: ذخیره تغییرات + برداشتن ارجاع (فقط سوپرادمین)
        if request.method == 'POST' and request.POST.get('action') == 'save_and_resolve_referral':
            if not (request.user.is_superuser and getattr(program, 'declaration_referred_to_manager', False)):
                messages.error(request, 'فقط مدیر می‌تواند ارجاع را حل کند.')
                return redirect(reverse('production:program_edit', args=[program.id]))
            form = ProductionProgramForm(request.POST, instance=program)
            if form.is_valid():
                instance = form.save(commit=False)
                if instance.product:
                    inventory_snapshot, net_unplanned = _calculate_product_inventory_and_requirement(instance.product)
                    instance.inventory_snapshot = inventory_snapshot
                    instance.net_unplanned_requirement = net_unplanned
                instance.save()
                instance.declaration_referred_to_manager = False
                instance.declaration_referred_at = None
                instance.declaration_referral_reason = ''
                instance.save(update_fields=['declaration_referred_to_manager', 'declaration_referred_at', 'declaration_referral_reason'])
                bug_logger.info(f"Production program {program_id} resolved by manager (save + clear referral)")
                audit_logger.activity(f"برنامه تولید {program_id} توسط مدیر حل شد (ذخیره و برداشتن ارجاع)")
                messages.success(request, 'تغییرات ذخیره شد و برنامه از ارجاع خارج شد. برنامه در لیست برنامه‌ها و اعلام تولید نمایش داده می‌شود.')
                return redirect(reverse('referrals_list'))
            # فرم نامعتبر: نمایش خطاها
            declaration_referred_to_manager = getattr(program, 'declaration_referred_to_manager', False)
            can_resolve_referral = request.user.is_superuser and declaration_referred_to_manager
            context = {'form': form, 'program': program, 'mode': 'edit', 'declaration_referred_to_manager': declaration_referred_to_manager, 'can_resolve_referral': can_resolve_referral}
            context.update(_get_dashboard_context())
            context.update(_prepare_bom_data(request))
            context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
            safe_flow = context.get('product_flow_status', [])
            context['product_flow_status_json'] = json.dumps(safe_flow, default=str)
            messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید و دوباره «حل توسط مدیر» را بزنید.')
            return render(request, 'program_form.html', context)

        # وقتی برنامه ارجاع شده و کاربر مدیر نیست، اکشن‌های تغییر وضعیت مسدود است
        declaration_referred_to_manager = getattr(program, 'declaration_referred_to_manager', False)
        can_resolve_referral = request.user.is_superuser and declaration_referred_to_manager
        if request.method == 'POST' and declaration_referred_to_manager and not can_resolve_referral:
            msg = 'مدیر داره ادیت میکنه و نمیشه به مرحله بعد یا قبل بردش.'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                return JsonResponse({'ok': False, 'errors': {'__all__': [msg]}}, status=403)
            messages.error(request, msg)
            return redirect(reverse('production:program_edit', args=[program.id]))

        # Hard guard: no edits allowed when in progress or completed
        if request.method == 'POST' and program.status in [ProductionProgram.Status.IN_PROGRESS, ProductionProgram.Status.COMPLETED]:
            msg = 'ویرایش در این وضعیت مجاز نیست.'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                return JsonResponse({'ok': False, 'errors': {'__all__': [msg]}}, status=400)
            messages.error(request, msg)
            return redirect(reverse('production:program_edit', args=[program.id]))

        if request.method == 'POST':
            action = request.POST.get('action')

            # Delete draft action (only allowed for draft)
            if action == 'delete_draft':
                if program.status != ProductionProgram.Status.DRAFT:
                    msg = 'حذف پیش‌نویس فقط در وضعیت پیش‌نویس مجاز است.'
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                        return JsonResponse({'ok': False, 'errors': {'__all__': [msg]}}, status=400)
                    messages.error(request, msg)
                    return redirect(reverse('production:program_edit', args=[program.id]))
                program.delete()
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                    return JsonResponse({'ok': True, 'deleted': True})
                messages.success(request, 'پیش‌نویس حذف شد.')
                return redirect(reverse('production:program_list'))

            form = ProductionProgramForm(request.POST, instance=program)
            if form.is_valid():
                instance = form.save(commit=False)
                
                # Validate planned weight against min_batch_production (for all actions that create/modify program)
                if action in ['draft', 'confirm', 'start'] and instance.production_info and instance.production_info.min_batch_production:
                    min_batch = instance.production_info.min_batch_production
                    if instance.planned_weight_ton and instance.planned_weight_ton < min_batch:
                        error_msg = f'تناژ برنامه ({instance.planned_weight_ton} کیلوگرم) کمتر از حداقل وزن تولید ({min_batch} کیلوگرم) است. لطفاً تناژ برنامه را افزایش دهید.'
                        bug_logger.warning(f"Validation failed: {error_msg}")
                        messages.error(request, error_msg)
                        declaration_referred = getattr(program, 'declaration_referred_to_manager', False)
                        context = {'form': form, 'program': program, 'mode': 'edit', 'declaration_referred_to_manager': declaration_referred, 'can_resolve_referral': request.user.is_superuser and declaration_referred}
                        context.update(_get_dashboard_context())
                        context.update(_prepare_bom_data(request))
                        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
                        return render(request, 'program_form.html', context)
                
                # Calculate and set inventory_snapshot and net_unplanned_requirement
                if instance.product:
                    inventory_snapshot, net_unplanned = _calculate_product_inventory_and_requirement(instance.product)
                    instance.inventory_snapshot = inventory_snapshot
                    instance.net_unplanned_requirement = net_unplanned
                
                # State transitions: allow draft/confirm edits; block start/complete unless existing rules
                if action == 'confirm' and instance.status in [ProductionProgram.Status.DRAFT, ProductionProgram.Status.CONFIRMED]:
                    instance.status = ProductionProgram.Status.CONFIRMED
                elif action == 'draft' and instance.status == ProductionProgram.Status.DRAFT:
                    instance.status = ProductionProgram.Status.DRAFT  # no change, just save
                elif action == 'draft' and instance.status == ProductionProgram.Status.CONFIRMED:
                    instance.status = ProductionProgram.Status.DRAFT  # change from confirmed to draft
                elif action == 'start' and instance.status == ProductionProgram.Status.CONFIRMED:
                    instance.status = ProductionProgram.Status.IN_PROGRESS
                elif action == 'complete' and instance.status == ProductionProgram.Status.IN_PROGRESS:
                    instance.status = ProductionProgram.Status.COMPLETED
                elif action == 'confirm' and instance.status == ProductionProgram.Status.CONFIRMED:
                    # permit saving confirmed without changing status
                    pass
                else:
                    msg = 'این اقدام برای وضعیت فعلی مجاز نیست.'
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                        return JsonResponse({'ok': False, 'errors': {'__all__': [msg]}}, status=400)
                    messages.error(request, msg)
                    return redirect(reverse('production:program_edit', args=[instance.id]))
                instance.save()
                messages.success(request, 'برنامه به‌روز شد.')
                return redirect(reverse('production:program_edit', args=[instance.id]))
        else:
            form = ProductionProgramForm(instance=program)

        declaration_referred_to_manager = getattr(program, 'declaration_referred_to_manager', False)
        can_resolve_referral = request.user.is_superuser and declaration_referred_to_manager
        context = {'form': form, 'program': program, 'mode': 'edit', 'declaration_referred_to_manager': declaration_referred_to_manager, 'can_resolve_referral': can_resolve_referral}
        context.update(_get_dashboard_context())
        context.update(_prepare_bom_data(request))
        # Add field access permissions
        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
        # Add product inventory data for JavaScript auto-fill
        safe_flow = context.get('product_flow_status', [])
        context['product_flow_status_json'] = json.dumps(safe_flow, default=str)
        return render(request, 'program_form.html', context)
    except Exception as e:
        bug_logger.error(f"Edit program error: {e}")
        messages.error(request, 'خطا در بروزرسانی برنامه.')
        declaration_referred_to_manager = getattr(program, 'declaration_referred_to_manager', False)
        can_resolve_referral = request.user.is_superuser and declaration_referred_to_manager
        context = {'form': ProductionProgramForm(instance=program), 'program': program, 'mode': 'edit', 'declaration_referred_to_manager': declaration_referred_to_manager, 'can_resolve_referral': can_resolve_referral}
        context.update(_get_dashboard_context())
        context.update(_prepare_bom_data(request))
        # Add field access permissions
        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
        return render(request, 'program_form.html', context)


@login_required
def program_list_view(request):
    if not user_has_task(request.user, TaskChoices.PRODUCTION_PROGRAM_LIST.value):
        audit_logger.activity("تلاش برای مشاهده لیست برنامه‌های تولید بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست برنامه‌های تولید ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    audit_logger.info("نمایش لیست برنامه‌های تولید")
    try:
        programs = ProductionProgram.objects.select_related('product', 'production_info')

        search_query = request.GET.get('q', '').strip()
        if search_query:
            programs = programs.filter(
                Q(product__name__icontains=search_query) |
                Q(program_id__icontains=search_query) |
                Q(production_info__formula_id__icontains=search_query)
            )

        table = ProductionProgramTable(programs)
        RequestConfig(request, paginate={'per_page': 20}).configure(table)

        bug_logger.debug(f"Programs list count={programs.count()}")
        return render(request, 'program_list.html', {'table': table, 'search_query': search_query})
    except Exception as e:
        bug_logger.error(f"List programs error: {e}")
        return render(request, 'program_list.html', {'table': None, 'search_query': ''})


@login_required
def program_drafts_view(request):
    """Redirect to main program list - drafts are shown there with status"""
    if not user_has_task(request.user, TaskChoices.PRODUCTION_PROGRAM_LIST.value):
        audit_logger.activity("تلاش برای مشاهده پیش‌نویس‌های برنامه تولید بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست برنامه‌های تولید ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    audit_logger.info("ریدایرکت از صفحه پیش‌نویس به لیست اصلی")
    return redirect(reverse('production:program_list'))
