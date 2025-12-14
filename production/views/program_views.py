from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
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
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem

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
        production_infos = ProductionInfo.objects.select_related('product').all()
        db_issue = False
        for prod_info in production_infos:
            try:
                planned_inventory = ProductionProgram.objects.filter(
                    production_info=prod_info,
                    status=ProductionProgram.Status.CONFIRMED
                ).aggregate(total=Sum('planned_weight_ton'))['total'] or 0
            except OperationalError:
                planned_inventory = 0
                db_issue = True
                bug_logger.warning("خطای عملیاتی هنگام محاسبه موجودی برنامه‌ریزی شده")

            inventory = 0
            logistic_confirmed = 0
            net_unplanned = logistic_confirmed - (inventory + planned_inventory)

            product_flow_status.append({
                'product': prod_info.product.name if prod_info.product else '-',
                'program_id': prod_info.formula_id or '-',
                'inventory': inventory,
                'planned_inventory': planned_inventory,
                'net_unplanned_requirement': net_unplanned,
                'status': 'نیازمند برنامه‌ریزی' if net_unplanned > 0 else 'کافی'
            })

        product_flow_status.sort(key=lambda x: x['net_unplanned_requirement'], reverse=True)
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


def create_program_view(request):
    """ایجاد / پیش نویس / تایید برنامه تولید"""
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


def edit_program_view(request, program_id):
    audit_logger.info("دسترسی به ویرایش برنامه تولید")
    program = get_object_or_404(ProductionProgram, id=program_id)
    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            form = ProductionProgramForm(request.POST, instance=program)
            if form.is_valid():
                instance = form.save(commit=False)
                if action == 'confirm' and instance.status == ProductionProgram.Status.DRAFT:
                    instance.status = ProductionProgram.Status.CONFIRMED
                elif action == 'start' and instance.status == ProductionProgram.Status.CONFIRMED:
                    instance.status = ProductionProgram.Status.IN_PROGRESS
                elif action == 'complete' and instance.status == ProductionProgram.Status.IN_PROGRESS:
                    instance.status = ProductionProgram.Status.COMPLETED
                instance.save()
                messages.success(request, 'برنامه به‌روز شد.')
                return redirect(reverse('production:program_edit', args=[instance.id]))
        else:
            form = ProductionProgramForm(instance=program)

        context = {'form': form, 'program': program, 'mode': 'edit'}
        context.update(_get_dashboard_context())
        context.update(_prepare_bom_data(request))
        # Add field access permissions
        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
        return render(request, 'program_form.html', context)
    except Exception as e:
        bug_logger.error(f"Edit program error: {e}")
        messages.error(request, 'خطا در بروزرسانی برنامه.')
        context = {'form': ProductionProgramForm(instance=program), 'program': program, 'mode': 'edit'}
        context.update(_get_dashboard_context())
        context.update(_prepare_bom_data(request))
        # Add field access permissions
        context['accessible_raw_material_fields'] = get_accessible_raw_material_fields(request.user)
        return render(request, 'program_form.html', context)


def program_list_view(request):
    audit_logger.info("نمایش لیست برنامه‌های تولید")
    try:
        programs = ProductionProgram.objects.all().select_related('product', 'production_info')
        bug_logger.debug(f"Programs list count={programs.count()}")
        return render(request, 'program_list.html', {'programs': programs})
    except Exception as e:
        bug_logger.error(f"List programs error: {e}")
        return render(request, 'program_list.html', {'programs': []})


def program_drafts_view(request):
    """Redirect to main program list - drafts are shown there with status"""
    audit_logger.info("ریدایرکت از صفحه پیش‌نویس به لیست اصلی")
    return redirect(reverse('production:program_list'))
