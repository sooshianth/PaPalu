from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, date, time
import jdatetime
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template.loader import render_to_string
from django.db import transaction
from decimal import Decimal

import logging
import traceback
from core.logging_levels import *
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field

from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.ProductionFolder.ProductionRevertLogModel import ProductionRevertLog
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductModel import Product
from core.StockEntryFolder.StockEntryModel import StockEntry
from core.StockEntryFolder.SourceStockModel import SourceStock
from core.StockEntryFolder.TargetStockModel import TargetStock
from core.StockEntryFolder.StockEntryParentModel import StockEntryParent
from production.forms.program_form import ProductionProgramForm
from production.forms.production_form import ProductionForm
# Reuse dashboard helper for inventory snapshot auto-fill (used in program create)
from production.views.program_views import _get_dashboard_context
import json

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_production_program_fields(user):
    """بررسی دسترسی کاربر به فیلدهای ProductionProgram - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['id'] = user_can_access_field(user, ProductionProgram, 'id', 'view')
    accessible_fields['program_id'] = user_can_access_field(user, ProductionProgram, 'program_id', 'view')
    accessible_fields['planned_weight_ton'] = user_can_access_field(user, ProductionProgram, 'planned_weight_ton', 'view')
    accessible_fields['produced_weight_ton'] = user_can_access_field(user, ProductionProgram, 'produced_weight_ton', 'view')
    accessible_fields['packaging_type'] = user_can_access_field(user, ProductionProgram, 'packaging_type', 'view')
    accessible_fields['predicted_start_date'] = user_can_access_field(user, ProductionProgram, 'predicted_start_date', 'view')
    accessible_fields['predicted_start_time'] = user_can_access_field(user, ProductionProgram, 'predicted_start_time', 'view')
    accessible_fields['predicted_end_date'] = user_can_access_field(user, ProductionProgram, 'predicted_end_date', 'view')
    accessible_fields['predicted_end_time'] = user_can_access_field(user, ProductionProgram, 'predicted_end_time', 'view')
    accessible_fields['started_at'] = user_can_access_field(user, ProductionProgram, 'started_at', 'view')
    accessible_fields['completed_at'] = user_can_access_field(user, ProductionProgram, 'completed_at', 'view')
    accessible_fields['status'] = user_can_access_field(user, ProductionProgram, 'status', 'view')
    accessible_fields['product'] = user_can_access_field(user, ProductionProgram, 'product', 'view')
    accessible_fields['product_warehouse'] = user_can_access_field(user, ProductionProgram, 'product_warehouse', 'view')
    accessible_fields['production_warehouse'] = user_can_access_field(user, ProductionProgram, 'production_warehouse', 'view')
    accessible_fields['production_info'] = user_can_access_field(user, ProductionProgram, 'production_info', 'view')
    accessible_fields['inventory_snapshot'] = user_can_access_field(user, ProductionProgram, 'inventory_snapshot', 'view')
    accessible_fields['net_unplanned_requirement'] = user_can_access_field(user, ProductionProgram, 'net_unplanned_requirement', 'view')
    accessible_fields['extra_description'] = user_can_access_field(user, ProductionProgram, 'extra_description', 'view')
    accessible_fields['priority_index'] = user_can_access_field(user, ProductionProgram, 'priority_index', 'view')
    accessible_fields['fulfillment_percentage'] = user_can_access_field(user, ProductionProgram, 'fulfillment_percentage', 'view')
    accessible_fields['actual_start_date'] = user_can_access_field(user, ProductionProgram, 'actual_start_date', 'view')
    accessible_fields['actual_end_date'] = user_can_access_field(user, ProductionProgram, 'actual_end_date', 'view')
    
    # Edit permissions for actual_end_date
    accessible_fields['actual_end_date_edit'] = user_can_access_field(user, ProductionProgram, 'actual_end_date', 'edit')
    
    # Edit permissions
    accessible_fields['id_edit'] = user_can_access_field(user, ProductionProgram, 'id', 'edit')
    accessible_fields['program_id_edit'] = user_can_access_field(user, ProductionProgram, 'program_id', 'edit')
    accessible_fields['planned_weight_ton_edit'] = user_can_access_field(user, ProductionProgram, 'planned_weight_ton', 'edit')
    accessible_fields['produced_weight_ton_edit'] = user_can_access_field(user, ProductionProgram, 'produced_weight_ton', 'edit')
    accessible_fields['packaging_type_edit'] = user_can_access_field(user, ProductionProgram, 'packaging_type', 'edit')
    accessible_fields['predicted_start_time_edit'] = user_can_access_field(user, ProductionProgram, 'predicted_start_time', 'edit')
    accessible_fields['predicted_end_time_edit'] = user_can_access_field(user, ProductionProgram, 'predicted_end_time', 'edit')
    accessible_fields['started_at_edit'] = user_can_access_field(user, ProductionProgram, 'started_at', 'edit')
    accessible_fields['completed_at_edit'] = user_can_access_field(user, ProductionProgram, 'completed_at', 'edit')
    accessible_fields['status_edit'] = user_can_access_field(user, ProductionProgram, 'status', 'edit')
    accessible_fields['product_edit'] = user_can_access_field(user, ProductionProgram, 'product', 'edit')
    accessible_fields['product_warehouse_edit'] = user_can_access_field(user, ProductionProgram, 'product_warehouse', 'edit')
    accessible_fields['production_warehouse_edit'] = user_can_access_field(user, ProductionProgram, 'production_warehouse', 'edit')
    accessible_fields['production_info_edit'] = user_can_access_field(user, ProductionProgram, 'production_info', 'edit')
    accessible_fields['inventory_snapshot_edit'] = user_can_access_field(user, ProductionProgram, 'inventory_snapshot', 'edit')
    accessible_fields['net_unplanned_requirement_edit'] = user_can_access_field(user, ProductionProgram, 'net_unplanned_requirement', 'edit')
    accessible_fields['extra_description_edit'] = user_can_access_field(user, ProductionProgram, 'extra_description', 'edit')
    accessible_fields['priority_index_edit'] = user_can_access_field(user, ProductionProgram, 'priority_index', 'edit')
    accessible_fields['fulfillment_percentage_edit'] = user_can_access_field(user, ProductionProgram, 'fulfillment_percentage', 'edit')
    accessible_fields['actual_start_date_edit'] = user_can_access_field(user, ProductionProgram, 'actual_start_date', 'edit')
    # Actual consumption (JSON) on production program
    accessible_fields['actual_consumption'] = user_can_access_field(user, ProductionProgram, 'actual_consumption', 'view')
    accessible_fields['actual_consumption_edit'] = user_can_access_field(user, ProductionProgram, 'actual_consumption', 'edit')
    
    return accessible_fields


def get_accessible_product_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Product - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['name'] = user_can_access_field(user, Product, 'name', 'view')
    accessible_fields['packaging_type'] = user_can_access_field(user, Product, 'packaging_type', 'view')
    return accessible_fields


def get_accessible_raw_material_fields(user):
    """بررسی دسترسی کاربر به فیلدهای RawMaterial - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['raw_material_id'] = user_can_access_field(user, RawMaterial, 'raw_material_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, RawMaterial, 'name', 'view')
    return accessible_fields


def get_accessible_warehouse_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Warehouse - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['warehouse_id'] = user_can_access_field(user, Warehouse, 'warehouse_id', 'view')
    accessible_fields['warehouse_name'] = user_can_access_field(user, Warehouse, 'warehouse_name', 'view')
    accessible_fields['name'] = user_can_access_field(user, Warehouse, 'name', 'view')
    return accessible_fields


def get_accessible_production_info_fields(user):
    """بررسی دسترسی کاربر به فیلدهای ProductionInfo - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['formula_id'] = user_can_access_field(user, ProductionInfo, 'formula_id', 'view')
    accessible_fields['min_batch_production'] = user_can_access_field(user, ProductionInfo, 'min_batch_production', 'view')
    accessible_fields['specific_production_instruction'] = user_can_access_field(user, ProductionInfo, 'specific_production_instruction', 'view')
    accessible_fields['product'] = user_can_access_field(user, ProductionInfo, 'product', 'view')
    return accessible_fields


def get_accessible_bom_fields(user):
    """بررسی دسترسی کاربر به فیلدهای BOM - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['raw_material'] = user_can_access_field(user, BOM, 'raw_material', 'view')
    accessible_fields['quantity'] = user_can_access_field(user, BOM, 'quantity', 'view')  # DELETE LATER
    accessible_fields['percentage'] = user_can_access_field(user, BOM, 'percentage', 'view')
    accessible_fields['unit_used'] = user_can_access_field(user, BOM, 'unit_used', 'view')
    return accessible_fields


def create_completion_stock_entries(production_program, actual_consumption, product_warehouse, request):
    """
    ایجاد ثبت‌های انبار برای تکمیل تولید
    1. تصحیح برداشت واقعی (اگر تفاوت وجود داشته باشد)
    2. انتقال تمام مواد اولیه از انبار تولید به انبار محصول به صورت محصول نهایی
    
    Args:
        production_program: برنامه تولید
        actual_consumption: دیکشنری مصرف واقعی {bom_id: {warehouse: amount}}
        product_warehouse: انبار مقصد محصول نهایی
        request: Django request object
    
    Returns:
        list of StockEntry objects or None if failed
    """
    try:
        stock_entries = []
        
        # Preliminary validation - ensure warehouses exist and are correct
        # Normalize keys 'global'/'none' to production warehouse id for checking
        production_warehouse = production_program.production_warehouse
        if not production_warehouse:
            production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
            if not production_warehouse:
                bug_logger.warning("Production warehouse not found")
                return None

        # Validate product warehouse
        try:
            if isinstance(product_warehouse, int) or (isinstance(product_warehouse, str) and product_warehouse.isdigit()):
                product_warehouse = Warehouse.objects.get(id=int(product_warehouse))
        except (Warehouse.DoesNotExist, ValueError):
            bug_logger.warning(f"Product warehouse {product_warehouse} not found")
            return None

        # Collect all warehouse ids referenced in actual_consumption
        warehouse_ids_to_check = set()
        for bom_map in actual_consumption.values():
            for wh_key in bom_map.keys():
                if wh_key in ['global', 'none']:
                    warehouse_ids_to_check.add(str(production_warehouse.id))
                else:
                    warehouse_ids_to_check.add(str(wh_key))

        # Check if all warehouses exist
        # Filter out non-numeric values that are not 'global'/'none'
        numeric_ids = set()
        for wid in warehouse_ids_to_check:
            try:
                numeric_ids.add(int(wid))
            except (ValueError, TypeError):
                bug_logger.warning(f"Invalid warehouse id in actual_consumption: {wid}")
                return None

        existing_count = Warehouse.objects.filter(id__in=numeric_ids).count() if numeric_ids else 0
        if numeric_ids and existing_count != len(numeric_ids):
            bug_logger.warning("One or more warehouses referenced in actual consumption not found")
            return None

        with transaction.atomic():
            # Get content types
            raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
            product_ct = ContentType.objects.get_for_model(Product)
            
            if not production_program.production_info:
                bug_logger.warning("Production program lacks formula information")
                return None
            
            # Find production warehouse
            production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
            if not production_warehouse:
                bug_logger.warning("Production warehouse not found")
                return None
            
            # Step 1: Correct actual consumption
            # Compare warehouse_distribution (planned) with actual_consumption (actual)
            warehouse_distribution = production_program.warehouse_distribution or {}
            
            for bom in production_program.production_info.bom_items.all():
                bom_id_str = str(bom.id)
                
                if bom_id_str not in warehouse_distribution:
                    continue
                
                planned_dist = warehouse_distribution[bom_id_str]
                actual_dist = actual_consumption.get(bom_id_str, {})
                # Normalize 'global' or 'none' keys to production_warehouse id so downstream logic works
                if actual_dist and production_warehouse:
                    normalized_actual_dist = {}
                    for wh_key, wh_amount in actual_dist.items():
                        if wh_key in ['global', 'none']:
                            normalized_actual_dist[str(production_warehouse.id)] = wh_amount
                        else:
                            normalized_actual_dist[wh_key] = wh_amount
                    actual_dist = normalized_actual_dist
                
                # Calculate difference for each warehouse
                for planned_item in planned_dist:
                    warehouse_id = planned_item['warehouse']
                    planned_amount = Decimal(str(planned_item.get('amount', 0)))
                    actual_amount = Decimal(str(actual_dist.get(warehouse_id, 0)))
                    
                    difference = actual_amount - planned_amount
                    
                    if difference != 0:
                        # Create correction stock entry
                        correction_entry = StockEntry.objects.create(
                            transaction_date=timezone.now(),
                            notes=f'تصحیح برداشت واقعی برنامه {production_program.program_id or production_program.id} - {bom.raw_material.name if bom.raw_material else "ماده اولیه"} - انبار {warehouse_id}',
                            is_committed=False
                        )
                        
                        try:
                            source_warehouse = Warehouse.objects.get(id=int(warehouse_id))
                        except (Warehouse.DoesNotExist, ValueError):
                            bug_logger.warning(f"Warehouse {warehouse_id} not found")
                            # If warehouse doesn't exist, abort whole operation
                            raise
                        
                        if difference > 0:
                            # More consumed than planned - decrease from source, increase to production
                            bug_logger.debug(f"Correction: {difference} more consumed from {warehouse_id} for {bom.raw_material.name if bom.raw_material else 'raw material'}")
                            
                            SourceStock.objects.create(
                                stock_entry=correction_entry,
                                from_content_type=raw_material_ct,
                                from_object_id=bom.raw_material.id,
                                from_warehouse=source_warehouse,
                                quantity=difference,
                            )
                            
                            TargetStock.objects.create(
                                stock_entry=correction_entry,
                                to_content_type=raw_material_ct,
                                to_object_id=bom.raw_material.id,
                                to_warehouse=production_warehouse,
                                quantity=difference,
                            )
                        else:
                            # Less consumed than planned - return to source warehouse
                            return_amount = abs(difference)
                            bug_logger.debug(f"Correction: {return_amount} less consumed, returned to {warehouse_id} for {bom.raw_material.name if bom.raw_material else 'raw material'}")
                            
                            SourceStock.objects.create(
                                stock_entry=correction_entry,
                                from_content_type=raw_material_ct,
                                from_object_id=bom.raw_material.id,
                                from_warehouse=production_warehouse,
                                quantity=return_amount,
                            )
                            
                            TargetStock.objects.create(
                                stock_entry=correction_entry,
                                to_content_type=raw_material_ct,
                                to_object_id=bom.raw_material.id,
                                to_warehouse=source_warehouse,
                                quantity=return_amount,
                            )
                        
                        correction_entry.commit()
                        stock_entries.append(correction_entry)
                        bug_logger.info(f"Correction stock entry {correction_entry.id} confirmed")
            
            # Step 2: Convert all raw materials in production warehouse to final product
            # and transfer to product warehouse
            produced_weight = production_program.produced_weight_ton or Decimal('0')
            
            if produced_weight > 0 and production_program.product:
                # Find the "Start Production" (Consumption) entry to link as parent
                # We look for the entry associated with this program that moved materials to production
                consumption_entry = StockEntry.objects.filter(
                    notes__contains=f'شروع تولید برنامه {production_program.program_id or production_program.id}',
                    is_committed=True
                ).order_by('-created_at').first()

                completion_entry = StockEntry.objects.create(
                    transaction_date=timezone.now(),
                    entry_type=StockEntry.StockEntryType.PRODUCTION,
                    notes=f'تکمیل تولید برنامه {production_program.program_id or production_program.id} - تبدیل مواد اولیه به محصول نهایی',
                    is_committed=False
                )

                if consumption_entry:
                    # Link Consumption as Parent of Production (Consumption -> Production)
                    # For simplificty, we assume specific linking helps tracing.
                    # Quantity linked? Ideally the total weight of raw materials, or just 0 as a symbolic link?
                    # Let's link it with produced_weight to indicate "This production output came from that consumption event"
                    # But wait, StockEntryParent.quantity represents "How much of PARENT was used".
                    # The parent (Consumption) consumed Raw Materials. It doesn't "have" quantity in the same way Purchase does.
                    # However, strictly for tracing, we can just link them.
                    StockEntryParent.objects.create(
                        parent=consumption_entry,
                        child=completion_entry,
                        quantity=produced_weight # Symbolic: effectively 1-to-1 event link
                    )
                
                # Decrease all raw materials from production warehouse (based on total actual consumption)
                for bom in production_program.production_info.bom_items.all():
                    bom_id_str = str(bom.id)
                    actual_dist = actual_consumption.get(bom_id_str, {})
                    
                    # Sum total actual consumption from all warehouses
                    total_actual = sum(Decimal(str(amount)) for amount in actual_dist.values())
                    
                    if total_actual > 0:
                        SourceStock.objects.create(
                            stock_entry=completion_entry,
                            from_content_type=raw_material_ct,
                            from_object_id=bom.raw_material.id,
                            from_warehouse=production_warehouse,
                            quantity=total_actual,
                        )
                        bug_logger.debug(f"Decrease {total_actual} tons {bom.raw_material.name if bom.raw_material else 'raw material'} from production warehouse")
                
                # Increase final product to product warehouse
                TargetStock.objects.create(
                    stock_entry=completion_entry,
                    to_content_type=product_ct,
                    to_object_id=production_program.product.id,
                    to_warehouse=product_warehouse,
                    quantity=produced_weight,
                )
                bug_logger.debug(f"Increase {produced_weight} tons of product {production_program.product.name} to warehouse {product_warehouse.name}")
                
                completion_entry.commit()
                stock_entries.append(completion_entry)
                bug_logger.info(f"Completion stock entry {completion_entry.id} confirmed")
            
            bug_logger.info(f"Successful completion: {len(stock_entries)} stock entries created")
            return stock_entries
            
    except Exception as e:
        bug_logger.error(f"Error creating completion stock entries: {str(e)}")
        bug_logger.error(traceback.format_exc())
        return None


def create_production_stock_entry(production_program, warehouse_distribution, request):
    """
    ایجاد ثبت انبار برای شروع تولید
    انتقال مواد اولیه از انبارهای اولیه به انبار تولید
    
    Args:
        production_program: برنامه تولید
        warehouse_distribution: دیکشنری توزیع انبارها {bom_id: [{warehouse: str, amount: Decimal}, ...]}
        request: Django request object
    
    Returns:
        StockEntry object or None if failed
    """
    try:
        # Preliminary validation: ensure production warehouse and all source warehouses exist
        production_warehouse = production_program.production_warehouse
        if not production_warehouse:
            production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
            if not production_warehouse:
                bug_logger.warning("Production warehouse not found")
                return None

        # Collect needed source warehouse IDs from warehouse_distribution
        warehouse_ids = set()
        for bom_id, dist_list in (warehouse_distribution or {}).items():
            for dist in dist_list:
                wh = dist.get('warehouse')
                if wh in ['global', 'none', None]:
                    # will use production warehouse in that case
                    continue
                try:
                    warehouse_ids.add(int(wh))
                except (ValueError, TypeError):
                    bug_logger.warning(f"Invalid warehouse id in distribution: {wh}")
                    return None

        if warehouse_ids:
            existing_count = Warehouse.objects.filter(id__in=warehouse_ids).count()
            if existing_count != len(warehouse_ids):
                bug_logger.warning("One or more warehouses referenced in distribution not found")
                return None

        with transaction.atomic():
            # ایجاد ثبت انبار (create after validation)
            stock_entry = StockEntry.objects.create(
                transaction_date=timezone.now(),
                entry_type=StockEntry.StockEntryType.CONSUMPTION,
                notes=f'شروع تولید برنامه {production_program.program_id or production_program.id} - انتقال مواد اولیه به انبار تولید',
                is_committed=False
            )
            
            bug_logger.info(f"Stock entry {stock_entry.id} created for production start")
            
            # Get content type for raw material
            raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
            
            # Calculate total consumption amount for each raw material
            if not production_program.production_info:
                bug_logger.warning("Production program lacks formula information")
                return None
            
            # Use production warehouse from program if selected
            production_warehouse = production_program.production_warehouse
            if not production_warehouse:
                # If not, use the first production warehouse
                production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
                if not production_warehouse:
                    bug_logger.warning("Production warehouse not found")
                    return None
            
            # Process each BOM item
            for bom in production_program.production_info.bom_items.all():
                bom_id_str = str(bom.id)
                
                # Check if distribution for this BOM exists
                if bom_id_str not in warehouse_distribution:
                    bug_logger.warning(f"Warehouse distribution for BOM {bom.id} not found")
                    continue
                
                bug_logger.debug(f"Processing BOM {bom.id}: {bom.raw_material.name if bom.raw_material else 'unknown'}")
                
                # Create SourceStock and TargetStock for each warehouse (one by one transfer)
                for dist in warehouse_distribution[bom_id_str]:
                    warehouse_id = dist['warehouse']
                    # Normalize 'global'/'none' to production warehouse id
                    if warehouse_id in ['global', 'none']:
                        warehouse_id = production_warehouse.id
                    # Normalize 'global' or 'none' to production_warehouse id
                    if warehouse_id in ['global', 'none']:
                        warehouse_id = production_warehouse.id
                    amount = Decimal(str(dist['amount']))
                    
                    bug_logger.debug(f"Transfer {amount} from warehouse {warehouse_id} to production warehouse")
                    
                    # Find source warehouse using Django primary key (id)
                    source_warehouse = None
                    try:
                        # Ensure we use an int id
                        source_warehouse = Warehouse.objects.get(id=int(warehouse_id))
                        bug_logger.debug(f"Warehouse found by id: {warehouse_id}")
                    except (Warehouse.DoesNotExist, ValueError):
                        bug_logger.warning(f"Warehouse {warehouse_id} not found")
                        # abort whole operation (will be caught by outer except and trigger rollback)
                        raise
                    
                    if not source_warehouse:
                        bug_logger.warning(f"Warehouse {warehouse_id} not found")
                        # abort whole operation if missing
                        raise
                    
                    if amount > 0:
                        # Create SourceStock (decrease from source warehouse)
                        source_stock = SourceStock.objects.create(
                            stock_entry=stock_entry,
                            from_content_type=raw_material_ct,
                            from_object_id=bom.raw_material.id,
                            from_warehouse=source_warehouse,
                            quantity=amount,
                        )
                        bug_logger.debug(f"SourceStock created: {source_stock}")
                        
                        # Create TargetStock (increase to production warehouse - as raw material)
                        target_stock = TargetStock.objects.create(
                            stock_entry=stock_entry,
                            to_content_type=raw_material_ct,
                            to_object_id=bom.raw_material.id,
                            to_warehouse=production_warehouse,
                            quantity=amount,
                        )
                        bug_logger.debug(f"TargetStock created to production warehouse: {target_stock}")

                        # -------------------------------------------------------------------------
                        # FIFO Tracing: Link to Parent (Purchase/Opening) Entries
                        # -------------------------------------------------------------------------
                        try:
                            remaining_needed = amount
                            
                            # Find valid parent candidates:
                            # 1. Purchase or Opening or Production (if reusing material?) - usually Purchase/Opening
                            # 2. Must contain the specific Raw Material (TargetStock matches matches to_object_id)
                            # 3. Must be in the SOURCE warehouse
                            # 4. Must be committed
                            candidates = StockEntry.objects.filter(
                                entry_type__in=[
                                    StockEntry.StockEntryType.PURCHASE,
                                    StockEntry.StockEntryType.OPENING,
                                    StockEntry.StockEntryType.RETURN_IN
                                ],
                                target_stocks__to_content_type=raw_material_ct,
                                target_stocks__to_object_id=bom.raw_material.id,
                                target_stocks__to_warehouse=source_warehouse,
                                is_committed=True
                            ).distinct().order_by('transaction_date')

                            for candidate in candidates:
                                if remaining_needed <= 0:
                                    break
                                    
                                available = candidate.get_remaining_quantity()
                                if available <= 0:
                                    continue
                                    
                                take = min(remaining_needed, available)
                                
                                # Create or Update Link
                                link, created_link = StockEntryParent.objects.get_or_create(
                                    parent=candidate,
                                    child=stock_entry,
                                    defaults={'quantity': 0}
                                )
                                link.quantity = models.F('quantity') + take
                                link.save()
                                
                                remaining_needed -= take
                                bug_logger.debug(f"FIFO: Took {take} from Parent {candidate.id} for {bom.raw_material.name}")

                        except Exception as e:
                            bug_logger.warning(f"FIFO Tracing failed for {bom.raw_material.name}: {e}")
                            # Continue without failing the main transaction, as tracing is secondary
                        # -------------------------------------------------------------------------
            
            # Commit transaction
            stock_entry.commit()
            bug_logger.info(f"Stock entry {stock_entry.id} confirmed - raw materials transferred to production warehouse")
            
            return stock_entry
            
    except Exception as e:
        bug_logger.error(f"Error creating stock entry for production start: {str(e)}")
        bug_logger.error(traceback.format_exc())
        return None


def revert_production_stock_entry(production_program, request):
    """
    برگشت ثبت انبار برنامه تولید (از in_progress به confirmed)
    ایجاد ثبت انبار معکوس برای برگرداندن مواد اولیه از انبار تولید به انبارهای اولیه
    
    Args:
        production_program: برنامه تولید که باید برگردانده شود
        request: Django request object
    
    Returns:
        StockEntry object (reversal entry) or None if failed
    """
    try:
        # Preliminary validation: ensure distribution exists and warehouses exist
        warehouse_distribution = production_program.warehouse_distribution or {}

        if not warehouse_distribution:
            bug_logger.warning(f"Warehouse distribution for program {production_program.id} is empty")
            return None

        # Get production warehouse
        production_warehouse = production_program.production_warehouse
        if not production_warehouse:
            production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
            if not production_warehouse:
                bug_logger.warning("Production warehouse not found")
                return None

        # Collect all source warehouses referenced in distribution
        warehouse_ids = set()
        for bom_id, dist_list in warehouse_distribution.items():
            for dist in dist_list:
                wh = dist.get('warehouse')
                if wh in ['global', 'none', None]:
                    # these are normalized to production warehouse - ensure production warehouse exists, which we did above
                    continue
                try:
                    warehouse_ids.add(int(wh))
                except (ValueError, TypeError):
                    bug_logger.warning(f"Invalid warehouse id in distribution: {wh}")
                    return None

        if warehouse_ids:
            existing_count = Warehouse.objects.filter(id__in=warehouse_ids).count()
            if existing_count != len(warehouse_ids):
                bug_logger.warning("One or more warehouses referenced in distribution not found")
                return None

        with transaction.atomic():
            # Create reversal stock entry AFTER successful validation
            reversal_entry = StockEntry.objects.create(
                transaction_date=timezone.now(),
                notes=f'برگشت تولید برنامه {production_program.program_id or production_program.id} - برگشت مواد اولیه از انبار تولید به انبارهای اولیه',
                is_committed=False
            )
            
            bug_logger.info(f"Reversal stock entry {reversal_entry.id} created for production revert")
            
            # Get content type for raw material
            raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
            
            # Get production warehouse
            production_warehouse = production_program.production_warehouse
            if not production_warehouse:
                production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
                if not production_warehouse:
                    bug_logger.warning("Production warehouse not found")
                    return None
            
            # Process each BOM item - reverse operations
            for bom in production_program.production_info.bom_items.all():
                bom_id_str = str(bom.id)
                
                if bom_id_str not in warehouse_distribution:
                    continue
                
                # For each warehouse, create reverse operation
                for dist in warehouse_distribution[bom_id_str]:
                    warehouse_id = dist['warehouse']
                    amount = Decimal(str(dist['amount']))
                    
                    # Find source warehouse using Django primary key (id)
                    source_warehouse = None
                    try:
                        source_warehouse = Warehouse.objects.get(id=int(warehouse_id))
                    except (Warehouse.DoesNotExist, ValueError):
                        bug_logger.warning(f"Warehouse {warehouse_id} not found")
                        # abort whole operation if referenced warehouse missing
                        raise
                    
                    if not source_warehouse:
                        # abort if missing
                        raise
                    
                    if amount > 0:
                        # Reverse: decrease from production warehouse (SourceStock)
                        SourceStock.objects.create(
                            stock_entry=reversal_entry,
                            from_content_type=raw_material_ct,
                            from_object_id=bom.raw_material.id,
                            from_warehouse=production_warehouse,
                            quantity=amount
                        )
                        
                        # Reverse: increase to source warehouse (TargetStock)
                        TargetStock.objects.create(
                            stock_entry=reversal_entry,
                            to_content_type=raw_material_ct,
                            to_object_id=bom.raw_material.id,
                            to_warehouse=source_warehouse,
                            quantity=amount
                        )
                        
                        bug_logger.debug(f"Returned {amount} from production warehouse to {warehouse_id} for {bom.raw_material.name if bom.raw_material else 'raw material'}")
            
            # Commit transaction
            reversal_entry.commit()
            bug_logger.info(f"Reversal stock entry {reversal_entry.id} confirmed - raw materials returned to source warehouses")
            
            return reversal_entry
            
    except Exception as e:
        bug_logger.error(f"Error creating reversal stock entry: {str(e)}")
        bug_logger.error(traceback.format_exc())
        return None



@login_required
def production_declaration_view(request):
    """
    Production declaration page
    Display production programs by status and raw material inventory
    """
    # Check permission for submitting production reports
    if not user_has_task(request.user, TaskChoices.PRODUCTION_DECLARATION.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه اظهار تولید بدون دسترسی")
        messages.error(request, 'شما دسترسی به صفحه اظهار تولید ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    audit_logger.info("Access to production declaration page")
    
    try:
        # Get consolidated search parameters for each table
        search_confirmed = request.GET.get('search_confirmed', '').strip()
        search_progress = request.GET.get('search_progress', '').strip()
        search_completed = request.GET.get('search_completed', '').strip()
        
        # Get sort parameters for each table
        sort_by_confirmed = request.GET.get('sort_confirmed', 'predicted_start_date')
        sort_dir_confirmed = request.GET.get('dir_confirmed', 'asc')
        
        sort_by_progress = request.GET.get('sort_progress', 'predicted_start_date')
        sort_dir_progress = request.GET.get('dir_progress', 'asc')
        
        sort_by_completed = request.GET.get('sort_completed', 'predicted_start_date')
        sort_dir_completed = request.GET.get('dir_completed', 'desc')
        
        # Validate sort columns
        allowed_sorts = ['id', 'program_id', 'predicted_start_date', 'predicted_start_time', 'predicted_end_date', 'predicted_end_time', 'planned_weight_ton', 'status', 'started_at', 'completed_at', 'actual_start_date', 'actual_end_date']
        
        if sort_by_confirmed not in allowed_sorts:
            sort_by_confirmed = 'predicted_start_date'
        if sort_by_progress not in allowed_sorts:
            sort_by_progress = 'predicted_start_date'
        if sort_by_completed not in allowed_sorts:
            sort_by_completed = 'predicted_start_date'
        
        # Build order_by strings with datetime support (date + time)
        def build_order_by(sort_by, sort_dir):
            """Build order_by list for datetime fields (date + time)"""
            prefix = '-' if sort_dir == 'desc' else ''
            
            # For datetime fields, sort by date first, then time
            if sort_by == 'predicted_start_date':
                return [f'{prefix}predicted_start_date', f'{prefix}predicted_start_time']
            elif sort_by == 'predicted_end_date':
                return [f'{prefix}predicted_end_date', f'{prefix}predicted_end_time']
            elif sort_by == 'actual_start_date':
                return [f'{prefix}actual_start_date', f'{prefix}started_at']
            elif sort_by == 'actual_end_date':
                return [f'{prefix}actual_end_date', f'{prefix}completed_at']
            else:
                return [f'{prefix}{sort_by}']
        
        order_by_confirmed = build_order_by(sort_by_confirmed, sort_dir_confirmed) + ['id']
        order_by_progress = build_order_by(sort_by_progress, sort_dir_progress) + ['id']
        order_by_completed = build_order_by(sort_by_completed, sort_dir_completed) + ['id']
        
        # دریافت برنامه‌های تولید بر اساس وضعیت
        try:
            confirmed_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.CONFIRMED,
                is_denied=False,
                is_archived=False
            ).exclude(declaration_referred_to_manager=True).select_related('product', 'production_info')
            
            # Apply consolidated search filter for confirmed table
            if search_confirmed:
                confirmed_programs = confirmed_programs.filter(
                    Q(id__icontains=search_confirmed) | 
                    Q(product__name__icontains=search_confirmed)
                )
            
            # Apply sorting for confirmed table
            confirmed_programs = confirmed_programs.order_by(*order_by_confirmed)
            bug_logger.debug(f"Number of confirmed programs: {confirmed_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"Error loading confirmed programs: {str(e)}")
            confirmed_programs = ProductionProgram.objects.none()
        
        try:
            in_progress_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.IN_PROGRESS,
                is_denied=False,
                is_archived=False
            ).select_related('product', 'production_info')
            
            # Apply consolidated search filter for in-progress table
            if search_progress:
                in_progress_programs = in_progress_programs.filter(
                    Q(id__icontains=search_progress) | 
                    Q(product__name__icontains=search_progress)
                )
            
            # Apply sorting for in-progress table
            in_progress_programs = in_progress_programs.order_by(*order_by_progress)
            bug_logger.debug(f"Number of in-progress programs: {in_progress_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"Error loading in-progress programs: {str(e)}")
            in_progress_programs = ProductionProgram.objects.none()
        
        # Pagination for completed programs
        try:
            completed_programs_qs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.COMPLETED,
                is_denied=False,
                is_archived=False
            ).select_related('product', 'production_info')
            
            # Apply consolidated search filter for completed table
            if search_completed:
                completed_programs_qs = completed_programs_qs.filter(
                    Q(id__icontains=search_completed) | 
                    Q(product__name__icontains=search_completed)
                )
            
            # Apply sorting for completed table
            completed_programs_qs = completed_programs_qs.order_by(*order_by_completed)
            
            bug_logger.debug(f"Total number of completed programs: {completed_programs_qs.count()}")
            
            # Pagination
            page_number = request.GET.get('page', 1)
            paginator = Paginator(completed_programs_qs, 10)  # 10 items per page
            
            try:
                completed_page = paginator.page(page_number)
            except PageNotAnInteger:
                completed_page = paginator.page(1)
            except EmptyPage:
                completed_page = paginator.page(paginator.num_pages)
                
        except Exception as e:
            bug_logger.warning(f"Error loading completed programs: {str(e)}")
            completed_page = Paginator(ProductionProgram.objects.none(), 10).page(1)
        
        # Get raw material inventory from primary warehouses
        raw_materials_inventory = []
        try:
            # Find primary warehouses
            primary_warehouses = Warehouse.objects.filter(warehouse_type='primary')
            bug_logger.debug(f"Number of primary warehouses: {primary_warehouses.count()}")
            
            if primary_warehouses.exists():
                # Get content type for RawMaterial
                try:
                    raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
                    
                    # Get inventory items that are raw materials
                    inventory_items = InventoryItem.objects.filter(
                        warehouse__in=primary_warehouses,
                        content_type=raw_material_ct
                    ).select_related('warehouse', 'content_type')
                    
                    bug_logger.debug(f"Number of raw material inventory items: {inventory_items.count()}")
                    
                    # Group raw materials by ID and sum inventory from warehouses
                    from collections import defaultdict
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
                                
                                # Store warehouse details (include Django ID for proper lookups)
                                raw_materials_grouped[rm_id]['warehouses'].append({
                                    'id': item.warehouse.id,  # Django primary key
                                    'warehouse_id': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'warehouse_name': item.warehouse.name if (item.warehouse and item.warehouse.name) else (str(item.warehouse) if item.warehouse else '-'),
                                    'quantity': str(quantity),
                                })
                        except Exception as e:
                            bug_logger.warning(f"Error loading raw material: {str(e)}")
                            continue
                    
                    # Convert to list
                    for rm_id, data in raw_materials_grouped.items():
                        raw_materials_inventory.append({
                            'raw_material_id': data['raw_material_id'],
                            'name': data['name'],
                            'total_quantity': str(data['total_quantity']),
                            'unit': data['unit'],
                            'warehouses': data['warehouses']
                        })
                    
                    bug_logger.debug(f"Number of processed raw materials: {len(raw_materials_inventory)}")
                    
                except ContentType.DoesNotExist:
                    bug_logger.warning("ContentType for RawMaterial not found")
                except Exception as e:
                    bug_logger.warning(f"Error getting raw material inventory: {str(e)}")
            else:
                bug_logger.warning("No primary warehouses found")
        
        except Exception as e:
            bug_logger.error(f"General error in getting raw material inventory: {str(e)}")
        
        # بررسی دسترسی فیلدها
        accessible_production_program_fields = get_accessible_production_program_fields(request.user)
        accessible_product_fields = get_accessible_product_fields(request.user)
        accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
        accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
        
        # Check permissions for deny, revert, and archive actions
        can_deny = user_has_task(request.user, TaskChoices.PRODUCTION_REJECT_SCHEDULE.value)
        can_revert = user_has_task(request.user, TaskChoices.PRODUCTION_REVERT_SCHEDULE.value)
        can_archive = user_has_task(request.user, TaskChoices.PRODUCTION_ARCHIVE.value)
        
        # Product inventory/requirement data (shared with program create view)
        dashboard_context = _get_dashboard_context()
        safe_flow = dashboard_context.get('product_flow_status', [])
        
        # آماده‌سازی context
        context = {
            'confirmed_programs': confirmed_programs,
            'in_progress_programs': in_progress_programs,
            'completed_page': completed_page,
            'raw_materials_inventory': raw_materials_inventory,
            'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
            # Consolidated search parameters for each table
            'search_confirmed': search_confirmed,
            'search_progress': search_progress,
            'search_completed': search_completed,
            # Sort parameters for each table
            'sort_by_confirmed': sort_by_confirmed,
            'sort_dir_confirmed': sort_dir_confirmed,
            'sort_by_progress': sort_by_progress,
            'sort_dir_progress': sort_dir_progress,
            'sort_by_completed': sort_by_completed,
            'sort_dir_completed': sort_dir_completed,
            # Field access permissions
            'accessible_production_program_fields': accessible_production_program_fields,
            'accessible_product_fields': accessible_product_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_warehouse_fields': accessible_warehouse_fields,
            # Action permissions
            'can_refer': can_refer,
            'can_revert': can_revert,
            'can_archive': can_archive,
            # Product inventory snapshot + net unplanned requirement (for auto-fill)
            'product_flow_status': safe_flow,
            'product_flow_status_json': json.dumps(safe_flow, default=str),
        }
        
        bug_logger.info("Production declaration page loaded successfully")
        
        # Handle AJAX requests for pagination/filtering
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            table_type = request.GET.get('table', 'completed')
            
            if table_type == 'confirmed':
                programs_html = render_to_string(
                    'production/_confirmed_programs_tbody.html',
                    {
                        'confirmed_programs': confirmed_programs,
                        'accessible_production_program_fields': accessible_production_program_fields,
                        'accessible_product_fields': accessible_product_fields,
                        'can_refer': can_refer,
                    },
                    request=request
                )
                return JsonResponse({
                    'programs_html': programs_html,
                    'total_count': confirmed_programs.count()
                })
            elif table_type == 'progress':
                programs_html = render_to_string(
                    'production/_progress_programs_tbody.html',
                    {
                        'in_progress_programs': in_progress_programs,
                        'accessible_production_program_fields': accessible_production_program_fields,
                        'accessible_product_fields': accessible_product_fields,
                        'can_revert': can_revert,
                    },
                    request=request
                )
                return JsonResponse({
                    'programs_html': programs_html,
                    'total_count': in_progress_programs.count()
                })
            else:  # completed
                programs_html = render_to_string(
                    'production/_completed_programs_tbody.html',
                    {
                        'completed_page': completed_page,
                        'accessible_production_program_fields': accessible_production_program_fields,
                        'accessible_product_fields': accessible_product_fields,
                        'accessible_warehouse_fields': accessible_warehouse_fields,
                        'can_refer': can_refer,
                        'can_revert': can_revert,
                        'can_archive': can_archive,
                    },
                    request=request
                )
                pagination_html = render_to_string(
                    'production/_completed_pagination.html',
                    {'completed_page': completed_page},
                    request=request
                )
                return JsonResponse({
                    'programs_html': programs_html,
                    'pagination_html': pagination_html,
                    'total_count': completed_page.paginator.count
                })
        
        return render(request, 'production_declaration.html', context)
    
    except Exception as e:
        bug_logger.error(f"General error in production declaration page load: {str(e)}")
        
        # Return empty page on error
        context = {
            'confirmed_programs': ProductionProgram.objects.none(),
            'in_progress_programs': ProductionProgram.objects.none(),
            'completed_page': Paginator(ProductionProgram.objects.none(), 10).page(1),
            'raw_materials_inventory': [],
            'raw_materials_inventory_json': json.dumps([]),
        }
        return render(request, 'production_declaration.html', context)



@login_required
def production_program_crud_view(request, program_id=None):
    """
    Production program create/edit page
    Display and edit all details of a production program with raw material inventory
    If program_id is None, it's in create mode
    """
    is_create = program_id is None
    
    # Check permission for creating new production program
    if is_create:
        if not user_has_task(request.user, TaskChoices.PRODUCTION_DECLARATION_CRUD.value):
            audit_logger.activity("تلاش برای ایجاد برنامه تولید جدید بدون دسترسی")
            messages.error(request, 'شما دسترسی به ایجاد برنامه تولید جدید ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    if is_create:
        audit_logger.info("Access to new production program creation page")
        program = None
    else:
        audit_logger.info(f"Access to production program {program_id} details")
    
    try:
        # Get production program (if editing)
        if not is_create:
            try:
                program_qs = ProductionProgram.objects.select_related('product', 'production_info')
                if not program_qs.filter(id=program_id).exists():
                    audit_logger.activity(f"Attempt to access missing production program {program_id}")
                program = get_object_or_404(program_qs, id=program_id)
                
                # Block access to denied programs
                if program.is_denied:
                    audit_logger.activity(f"Attempt to access denied production program {program_id}")
                    messages.error(request, 'این برنامه تولید رد شده و قابل دسترسی نیست')
                    return redirect(reverse('production:production_declaration'))

                # برنامه ارجاع‌شده به مدیر را فقط سوپرادمین می‌تواند باز کند
                if getattr(program, 'declaration_referred_to_manager', False) and not request.user.is_superuser:
                    audit_logger.activity(f"تلاش برای دسترسی به برنامه تولید ارجاع‌شده به مدیر {program_id}")
                    messages.error(request, 'این برنامه به مدیر ارجاع شده و فقط مدیر می‌تواند آن را باز کند.')
                    return HttpResponseForbidden('شما دسترسی به این برنامه را ندارید.')
                
                bug_logger.debug(f"Production program {program_id} loaded successfully")
            except Exception as e:
                bug_logger.error(f"Error loading production program {program_id}: {str(e)}")
                raise
        
        # Process form
        if request.method == 'POST':
            action = request.POST.get('action', 'save')

            # اکشن‌های ارجاع/حل ارجاع بدون نیاز به اعتبار فرم (از لیست یا مودال ارسال می‌شوند)
            if not is_create and action == 'refer_to_manager':
                if program.status != ProductionProgram.Status.CONFIRMED:
                    messages.error(request, 'فقط برنامه‌های تایید شده قابل ارجاع به مدیر هستند')
                    return redirect(reverse('production:program_crud', args=[program_id]))
                reason = request.POST.get('referral_reason', '').strip() or request.POST.get('deny_reason', '').strip()
                if not reason:
                    messages.error(request, 'لطفاً دلیل ارجاع به مدیر را وارد کنید')
                    return redirect(reverse('production:program_crud', args=[program_id]))
                program.declaration_referred_to_manager = True
                program.declaration_referred_at = timezone.now()
                program.declaration_referral_reason = reason
                program.save(update_fields=['declaration_referred_to_manager', 'declaration_referred_at', 'declaration_referral_reason'])
                bug_logger.info(f"Production program {program_id} referred to manager")
                audit_logger.activity(f"برنامه تولید {program_id} به مدیر ارجاع داده شد. دلیل: {reason[:100]}")
                messages.success(request, 'برنامه تولید به مدیر ارجاع داده شد. مدیر از صفحه ارجاعات آن را حل می‌کند.')
                return redirect(reverse('production:production_declaration'))
            if not is_create and action == 'resolve_referral_deny':
                if not request.user.is_superuser or not getattr(program, 'declaration_referred_to_manager', False):
                    messages.error(request, 'فقط مدیر می‌تواند ارجاع را با رد برنامه حل کند.')
                    return redirect(reverse('production:program_crud', args=[program_id]))
                reason = request.POST.get('deny_reason', '').strip()
                if not reason:
                    messages.error(request, 'لطفاً دلیل رد برنامه را وارد کنید')
                    return redirect(reverse('production:program_crud', args=[program_id]))
                program.is_denied = True
                program.declaration_referred_to_manager = False
                program.declaration_referred_at = None
                program.declaration_referral_reason = ''
                program.save(update_fields=['is_denied', 'declaration_referred_to_manager', 'declaration_referred_at', 'declaration_referral_reason'])
                ProductionRevertLog.objects.create(
                    production_program=program,
                    action_type='denied',
                    reason=reason,
                    created_by=request.user.username if request.user.is_authenticated else 'anonymous'
                )
                bug_logger.info(f"Production program {program_id} denied by manager (resolved referral)")
                audit_logger.activity(f"برنامه تولید {program_id} توسط مدیر رد شد. دلیل: {reason[:100]}")
                messages.success(request, 'برنامه تولید رد شد و از لیست ارجاعات خارج شد.')
                return redirect(reverse('referrals_list'))
            if not is_create and action == 'resolve_referral_clear':
                if not request.user.is_superuser or not getattr(program, 'declaration_referred_to_manager', False):
                    messages.error(request, 'فقط مدیر می‌تواند ارجاع را بردارد.')
                    return redirect(reverse('production:program_crud', args=[program_id]))
                program.declaration_referred_to_manager = False
                program.declaration_referred_at = None
                program.declaration_referral_reason = ''
                program.save(update_fields=['declaration_referred_to_manager', 'declaration_referred_at', 'declaration_referral_reason'])
                bug_logger.info(f"Production program {program_id} referral cleared by manager")
                audit_logger.activity(f"ارجاع برنامه تولید {program_id} توسط مدیر برطرف شد (بدون رد)")
                messages.success(request, 'برنامه از ارجاع خارج شد و به لیست اعلام تولید برمی‌گردد.')
                return redirect(reverse('referrals_list'))
            
            if is_create:
                form = ProductionForm(request.POST)
                audit_logger.info("Submitting form to create new production program")
            else:
                form = ProductionForm(request.POST, instance=program)
                audit_logger.info(f"Submitting form to edit production program {program_id}")
            
            if form.is_valid():
                try:
                    instance = form.save(commit=False)
                    
                    # Validate planned weight against min_batch_production (for all actions that create/modify program)
                    if action in ['save_draft', 'confirm', 'start'] and instance.production_info and instance.production_info.min_batch_production:
                        min_batch = instance.production_info.min_batch_production
                        if instance.planned_weight_ton and instance.planned_weight_ton < min_batch:
                            error_msg = f'تناژ برنامه ({instance.planned_weight_ton} کیلوگرم) کمتر از حداقل وزن تولید ({min_batch} کیلوگرم) است. لطفاً تناژ برنامه را افزایش دهید.'
                            messages.error(request, error_msg)
                            # Return to form with errors
                            warehouse_dist_data = program.warehouse_distribution if program and program.warehouse_distribution else {}
                            available_warehouses = Warehouse.objects.filter(
                                warehouse_type='secondary'
                            ).order_by('name')
                            production_warehouses = Warehouse.objects.filter(
                                warehouse_type='production'
                            ).order_by('name')
                            context = {
                                'form': form,
                                'program': program,
                                'is_create': is_create,
                                'raw_materials_inventory': raw_materials_inventory,
                                'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
                                'production_infos_json': json.dumps(production_infos_data),
                                'bom_data_json': json.dumps(bom_data),
                                'warehouse_distribution_json': json.dumps(warehouse_dist_data),
                                'warehouses': available_warehouses,
                                'production_warehouses': production_warehouses,
                            }
                            return render(request, 'production_declaration_crud.html', context)
                    
                    # تنظیم وضعیت بر اساس اکشن
                    if action == 'save_draft':
                        instance.status = ProductionProgram.Status.DRAFT
                    elif action == 'confirm':
                        instance.status = ProductionProgram.Status.CONFIRMED
                    elif action == 'start':
                        instance.status = ProductionProgram.Status.IN_PROGRESS
                        # Handle popup data for start action (separate date and time)
                        actual_start_date_str = request.POST.get('actual_start_date')
                        started_at_str = request.POST.get('started_at')
                        production_warehouse_id = request.POST.get('production_warehouse')
                        
                        # Set actual_start_date (Jalali date from form will be converted automatically)
                        if actual_start_date_str:
                            instance.actual_start_date = actual_start_date_str
                            bug_logger.debug(f"Actual start date received from popup: {instance.actual_start_date}")
                        
                        # Set started_at (time only)
                        if started_at_str:
                            instance.started_at = started_at_str
                            bug_logger.debug(f"Actual start time received from popup: {instance.started_at}")
                        else:
                            from datetime import datetime
                            instance.started_at = timezone.now().time()
                            bug_logger.debug(f"Actual start time set to current time")

                        # Set production warehouse
                        if production_warehouse_id:
                            try:
                                instance.production_warehouse = Warehouse.objects.get(id=production_warehouse_id)
                                bug_logger.info(f"Production warehouse: {instance.production_warehouse.name}")
                            except Warehouse.DoesNotExist:
                                bug_logger.warning(f"Production warehouse with id {production_warehouse_id} not found")
                                messages.error(request, 'انبار تولید نامعتبر است')
                                return redirect(reverse('production:program_crud', args=[program_id]))
                        
                        # Parse warehouse distribution data
                        warehouse_distribution = {}
                        for key in request.POST.keys():
                            if key.startswith('warehouse_dist_'):
                                parts = key.split('_')
                                # Format: warehouse_dist_{bom_id}_{index}_warehouse or warehouse_dist_{bom_id}_{index}_amount
                                if len(parts) >= 5:
                                    bom_id = parts[2]
                                    index = parts[3]
                                    field_type = parts[4]
                                    
                                    if bom_id not in warehouse_distribution:
                                        warehouse_distribution[bom_id] = {}
                                    if index not in warehouse_distribution[bom_id]:
                                        warehouse_distribution[bom_id][index] = {}
                                    
                                    warehouse_distribution[bom_id][index][field_type] = request.POST.get(key)
                        
                        # Convert to clean format
                        clean_distribution = {}
                        for bom_id, indices in warehouse_distribution.items():
                            clean_distribution[bom_id] = []
                            for index, data in indices.items():
                                if 'warehouse' in data and 'amount' in data:
                                    try:
                                        # Parse amount
                                        amount_val = Decimal(str(data['amount']))
                                        
                                        if amount_val > 0:  # Only include if amount > 0
                                            clean_distribution[bom_id].append({
                                                'warehouse': data['warehouse'],
                                                'amount': amount_val
                                            })
                                    except (ValueError, TypeError) as e:
                                        bug_logger.warning(f"Error converting amount for BOM {bom_id}: {str(e)}")
                        
                        bug_logger.debug(f"Warehouse distribution received: {len(clean_distribution)} BOM items")
                        
                        # Validate warehouse distribution: sum must equal total needed for each BOM
                        if clean_distribution and instance.production_info and instance.planned_weight_ton:
                            validation_errors = []
                            tolerance = Decimal('0.0001')  # Small tolerance for decimal comparison
                            
                            for bom in instance.production_info.bom_items.all():
                                bom_id_str = str(bom.id)
                                if bom_id_str in clean_distribution:
                                    # Calculate total needed: (percentage / 100) * planned_weight_ton
                                    if bom.percentage is not None:
                                        total_needed = (Decimal(str(bom.percentage)) / Decimal('100')) * instance.planned_weight_ton
                                        
                                        # Sum all warehouse amounts for this BOM
                                        total_withdrawal = Decimal('0')
                                        for dist in clean_distribution[bom_id_str]:
                                            total_withdrawal += Decimal(str(dist['amount']))
                                        
                                        # Check if sum equals total needed (with tolerance)
                                        difference = abs(total_withdrawal - total_needed)
                                        if difference > tolerance:
                                            material_name = bom.raw_material.name if bom.raw_material else f"BOM #{bom.id}"
                                            if total_withdrawal > total_needed:
                                                validation_errors.append(
                                                    f'{material_name}: مجموع برداشت ({total_withdrawal.quantize(Decimal("0.001"))}) '
                                                    f'بیشتر از مقدار مورد نیاز ({total_needed.quantize(Decimal("0.001"))}) است. '
                                                    f'تفاوت: +{(total_withdrawal - total_needed).quantize(Decimal("0.001"))}'
                                                )
                                            else:
                                                validation_errors.append(
                                                    f'{material_name}: مجموع برداشت ({total_withdrawal.quantize(Decimal("0.001"))}) '
                                                    f'کمتر از مقدار مورد نیاز ({total_needed.quantize(Decimal("0.001"))}) است. '
                                                    f'تفاوت: {(total_withdrawal - total_needed).quantize(Decimal("0.001"))}'
                                                )
                            
                            if validation_errors:
                                bug_logger.warning(f"Warehouse distribution validation failed: {validation_errors}")
                                messages.error(request, 'خطا در توزیع انبارها:\n\n' + '\n'.join(validation_errors))
                                # Return to form with errors
                                warehouse_dist_data = program.warehouse_distribution if program and program.warehouse_distribution else {}
                                available_warehouses = Warehouse.objects.filter(
                                    warehouse_type='secondary'
                                ).order_by('name')
                                production_warehouses = Warehouse.objects.filter(
                                    warehouse_type='production'
                                ).order_by('name')
                                context = {
                                    'form': form,
                                    'program': program,
                                    'is_create': is_create,
                                    'raw_materials_inventory': raw_materials_inventory,
                                    'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
                                    'production_infos_json': json.dumps(production_infos_data),
                                    'bom_data_json': json.dumps(bom_data),
                                    'warehouse_distribution_json': json.dumps(warehouse_dist_data),
                                    'warehouses': available_warehouses,
                                    'production_warehouses': production_warehouses,
                                }
                                return render(request, 'production_declaration_crud.html', context)
                        
                        # Store warehouse distribution with amounts (amounts directly from user input)
                        if clean_distribution and instance.production_info:
                            warehouse_dist_with_amounts = {}
                            
                            for bom in instance.production_info.bom_items.all():
                                bom_id_str = str(bom.id)
                                if bom_id_str in clean_distribution:
                                    warehouse_dist_with_amounts[bom_id_str] = []
                                    for dist in clean_distribution[bom_id_str]:
                                        amount = Decimal(str(dist['amount']))
                                        warehouse_dist_with_amounts[bom_id_str].append({
                                            'warehouse': dist['warehouse'],
                                            'amount': str(amount)
                                        })
                            
                            instance.warehouse_distribution = warehouse_dist_with_amounts
                            bug_logger.debug(f"Warehouse distribution with amounts stored: {warehouse_dist_with_amounts}")
                        
                        # Create stock entry if we have distribution data
                        if clean_distribution:
                            stock_entry = create_production_stock_entry(instance, clean_distribution, request)
                            if stock_entry:
                                bug_logger.info(f"Stock entry {stock_entry.id} created and confirmed for program {instance.id}")
                                messages.success(request, f'ثبت انبار با موفقیت ایجاد شد (شناسه: {stock_entry.id})')
                            else:
                                bug_logger.warning(f"Error creating stock entry for program {instance.id}")
                                messages.warning(request, 'خطا در ایجاد ثبت انبار')
                        else:
                            bug_logger.warning("Warehouse distribution data not received")
                    elif action == 'complete':
                        instance.status = ProductionProgram.Status.COMPLETED
                        # Handle popup data for complete action
                        produced_weight_str = request.POST.get('produced_weight_ton')
                        actual_end_date_str = request.POST.get('actual_end_date')
                        completed_at_str = request.POST.get('completed_at')
                        product_warehouse_id = request.POST.get('product_warehouse')
                        # Also read posted start values (hidden fields) to validate chronological order
                        posted_start_date_str = request.POST.get('actual_start_date') or None
                        posted_start_time_str = request.POST.get('started_at') or None
                        
                        if produced_weight_str:
                            try:
                                instance.produced_weight_ton = Decimal(produced_weight_str)
                                bug_logger.debug(f"Produced weight received from popup: {instance.produced_weight_ton}")
                            except (ValueError, TypeError) as e:
                                bug_logger.warning(f"Error converting produced weight: {str(e)}")
                        
                        # Set actual_end_date (Jalali date from form will be converted automatically)
                        if actual_end_date_str:
                            instance.actual_end_date = actual_end_date_str
                            bug_logger.debug(f"Actual end date received from popup: {instance.actual_end_date}")
                        
                        # Set completed_at (time only)
                        if completed_at_str:
                            instance.completed_at = completed_at_str
                            bug_logger.debug(f"Completion time received from popup: {instance.completed_at}")
                        else:
                            from datetime import datetime
                            instance.completed_at = timezone.now().time()
                            bug_logger.debug(f"Completion time set to current time")
                        
                        # Set product warehouse
                        if product_warehouse_id:
                            try:
                                instance.product_warehouse = Warehouse.objects.get(id=product_warehouse_id)
                                bug_logger.debug(f"Final product warehouse: {instance.product_warehouse.name}")
                            except Warehouse.DoesNotExist:
                                bug_logger.warning(f"Warehouse with id {product_warehouse_id} not found")
                                messages.error(request, 'انبار محصول نهایی نامعتبر است')
                                return redirect(reverse('production:program_crud', args=[program_id]))

                        # Validate actual start/end chronology
                        start_date_val = instance.actual_start_date if instance and instance.actual_start_date else posted_start_date_str
                        start_time_val = instance.started_at if instance and instance.started_at else posted_start_time_str

                        def _normalize_digits(s):
                            if s is None:
                                return None
                            persian = "۰۱۲۳۴۵۶۷۸۹"
                            normalized = []
                            for ch in str(s):
                                if ch in persian:
                                    normalized.append(str(persian.index(ch)))
                                else:
                                    normalized.append(ch)
                            return ''.join(normalized)

                        def _parse_date(val):
                            if not val:
                                return None
                            raw = _normalize_digits(val)
                            try:
                                if hasattr(raw, 'togregorian'):
                                    return raw.togregorian()
                            except Exception:
                                pass
                            try:
                                return jdatetime.date.fromisoformat(str(raw)).togregorian()
                            except Exception:
                                try:
                                    return datetime.strptime(str(raw), "%Y-%m-%d").date()
                                except Exception:
                                    return None

                        def _parse_time(val):
                            if not val:
                                return None
                            raw = _normalize_digits(val)
                            raw_str = str(raw).strip().upper()
                            if isinstance(raw, time):
                                return raw
                            for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
                                try:
                                    return datetime.strptime(raw_str, fmt).time()
                                except Exception:
                                    continue
                            return None

                        # Fall back to persisted start values if they were not posted again
                        if (not start_date_val or not start_time_val) and instance and instance.pk:
                            try:
                                original_program = ProductionProgram.objects.only('actual_start_date', 'started_at').get(pk=instance.pk)
                                start_date_val = start_date_val or original_program.actual_start_date
                                start_time_val = start_time_val or original_program.started_at
                            except ProductionProgram.DoesNotExist:
                                pass

                        start_date = _parse_date(start_date_val)
                        start_time = _parse_time(start_time_val)
                        end_date = _parse_date(actual_end_date_str)
                        end_time = _parse_time(completed_at_str)

                        # Only enforce ordering when both datetimes are available
                        if start_date and start_time and end_date and end_time:
                            start_dt = datetime.combine(start_date, start_time)
                            end_dt = datetime.combine(end_date, end_time)
                            if end_dt <= start_dt:
                                messages.error(request, 'زمان پایان واقعی باید بعد از شروع واقعی ثبت شود.')
                                return redirect(reverse('production:program_crud', args=[program_id]))
                    
                    # Handle actual consumption data (for COMPLETED status, warehouse-specific)
                    if action == 'complete' and instance.status == ProductionProgram.Status.COMPLETED:
                        actual_consumption = {}
                        # Collect warehouse-specific actual consumption data from POST
                        # Format: actual_consumption_{bom_id}_{warehouse}
                        for key, value in request.POST.items():
                            if key.startswith('actual_consumption_'):
                                parts = key.replace('actual_consumption_', '').split('_', 1)
                                if len(parts) == 2:
                                    bom_id = parts[0]
                                    warehouse = parts[1]
                                    if value and value.strip():
                                        try:
                                            amount = str(Decimal(value))
                                            if bom_id not in actual_consumption:
                                                actual_consumption[bom_id] = {}
                                            actual_consumption[bom_id][warehouse] = amount
                                            bug_logger.debug(f"Actual consumption BOM {bom_id} from warehouse {warehouse}: {amount}")
                                        except (ValueError, TypeError) as e:
                                            bug_logger.warning(f"Error converting actual consumption BOM {bom_id}, warehouse {warehouse}: {str(e)}")
                        
                        # Normalize 'global' or 'none' actual consumption keys to production_warehouse id
                        # So subsequent validation and stock entry creation can find warehouses
                        if instance.production_warehouse and actual_consumption:
                            normalized_consumption = {}
                            for bom_key, wh_map in actual_consumption.items():
                                normalized_wh_map = {}
                                for wh_key, amt in wh_map.items():
                                    if wh_key in ['global', 'none']:
                                        normalized_wh_map[str(instance.production_warehouse.id)] = amt
                                    else:
                                        normalized_wh_map[wh_key] = amt
                                normalized_consumption[bom_key] = normalized_wh_map
                            actual_consumption = normalized_consumption

                        # Validate that all BOM items with warehouse distribution have actual consumption
                        if instance.production_info and instance.warehouse_distribution:
                            bom_items = instance.production_info.bom_items.all()
                            missing_consumption = []
                            
                            for bom in bom_items:
                                bom_id_str = str(bom.id)
                                # Check if this BOM has warehouse distribution
                                if bom_id_str in instance.warehouse_distribution:
                                    # Check if it has actual consumption from at least one warehouse
                                    if bom_id_str not in actual_consumption or not actual_consumption[bom_id_str]:
                                        missing_consumption.append(bom.raw_material.name if bom.raw_material else f"BOM #{bom.id}")
                            
                            if missing_consumption:
                                bug_logger.warning(f"Completion rejected: actual consumption not entered for {len(missing_consumption)} raw materials")
                                messages.error(request, f'لطفاً مقدار مصرف واقعی را برای تمام مواد اولیه وارد کنید. موارد ناقص: {", ".join(missing_consumption)}')
                                # Don't save and return to form
                                warehouse_dist_data = program.warehouse_distribution if program and program.warehouse_distribution else {}
                                available_warehouses = Warehouse.objects.filter(
                                    warehouse_type='secondary'
                                ).order_by('name')
                                production_warehouses = Warehouse.objects.filter(
                                    warehouse_type='production'
                                ).order_by('name')
                                context = {
                                    'form': form,
                                    'program': program,
                                    'is_create': is_create,
                                    'raw_materials_inventory': raw_materials_inventory,
                                    'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
                                    'production_infos_json': json.dumps(production_infos_data),
                                    'bom_data_json': json.dumps(bom_data),
                                    'warehouse_distribution_json': json.dumps(warehouse_dist_data),
                                    'warehouses': available_warehouses,
                                    'production_warehouses': production_warehouses,
                                    'max_bom_error': Decimal(str(program.max_bom_error)) if program and program.max_bom_error else Decimal('5'),
                                }
                                return render(request, 'production_declaration_crud.html', context)
                            
                            # Validate BOM error percentage
                            if instance.produced_weight_ton and instance.produced_weight_ton > 0:
                                max_error = instance.max_bom_error if instance.max_bom_error else Decimal('5.00')
                                bom_errors = []
                                
                                for bom in bom_items:
                                    bom_id_str = str(bom.id)
                                    if bom_id_str in instance.warehouse_distribution:
                                        # Calculate total actual consumption for this BOM
                                        bom_actuals = actual_consumption.get(bom_id_str, {})
                                        total_actual = sum(Decimal(str(amount)) for amount in bom_actuals.values())
                                        
                                        if total_actual > 0 and bom.percentage:
                                            # Calculate actual percentage
                                            actual_percentage = (total_actual / instance.produced_weight_ton) * Decimal('100')
                                            
                                            # Calculate allowed range: bom.percentage ± (max_error% of bom.percentage)
                                            error_amount = (bom.percentage * max_error) / Decimal('100')
                                            min_allowed = bom.percentage - error_amount
                                            max_allowed = bom.percentage + error_amount
                                            
                                            # Check if actual percentage is outside allowed range
                                            if actual_percentage < min_allowed or actual_percentage > max_allowed:
                                                material_name = bom.raw_material.name if bom.raw_material else f"BOM #{bom.id}"
                                                diff = actual_percentage - bom.percentage
                                                bom_errors.append(
                                                    f"{material_name}: درصد واقعی {actual_percentage:.2f}% خارج از محدوده مجاز "
                                                    f"({min_allowed:.2f}% - {max_allowed:.2f}%) است. انحراف: {diff:+.2f}%"
                                                )
                                
                                if bom_errors:
                                    bug_logger.warning(f"Completion rejected: BOM error validation failed for {len(bom_errors)} materials")
                                    messages.error(request, f'خطا در درصد مواد اولیه:\n\n' + '\n'.join(bom_errors) + f'\n\nحداکثر انحراف مجاز: {max_error}%')
                                    # Don't save and return to form
                                    warehouse_dist_data = program.warehouse_distribution if program and program.warehouse_distribution else {}
                                    available_warehouses = Warehouse.objects.filter(
                                        warehouse_type='secondary'
                                    ).order_by('name')
                                    production_warehouses = Warehouse.objects.filter(
                                        warehouse_type='production'
                                    ).order_by('name')
                                    context = {
                                        'form': form,
                                        'program': program,
                                        'is_create': is_create,
                                        'raw_materials_inventory': raw_materials_inventory,
                                        'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
                                        'production_infos_json': json.dumps(production_infos_data),
                                        'bom_data_json': json.dumps(bom_data),
                                        'warehouse_distribution_json': json.dumps(warehouse_dist_data),
                                        'warehouses': available_warehouses,
                                        'production_warehouses': production_warehouses,
                                        'max_bom_error': Decimal(str(program.max_bom_error)) if program and program.max_bom_error else Decimal('5'),
                                    }
                                    return render(request, 'production_declaration_crud.html', context)
                        
                        instance.actual_consumption = actual_consumption
                        bug_logger.debug(f"Actual consumption data (warehouse-wise) stored: {len(actual_consumption)} BOM items")
                        
                        # Create completion stock entries (corrections + final product transfer)
                        if instance.product_warehouse and actual_consumption:
                            stock_entries = create_completion_stock_entries(
                                instance, 
                                actual_consumption, 
                                instance.product_warehouse, 
                                request
                            )
                            if stock_entries:
                                bug_logger.info(f"{len(stock_entries)} stock entries created for production completion")
                                messages.success(request, f'تکمیل تولید با موفقیت انجام شد. {len(stock_entries)} ثبت انبار ایجاد شد.')
                            else:
                                bug_logger.error("Error creating completion stock entries")
                                messages.warning(request, 'برنامه تکمیل شد اما خطا در ایجاد ثبت‌های انبار رخ داد')
                        else:
                            bug_logger.warning("Product warehouse or actual consumption not present - stock entry not created")
                    elif action == 'save':
                        # Save action - allow updating actual consumption for in_progress programs
                        if instance.status == ProductionProgram.Status.IN_PROGRESS:
                            # Parse actual consumption data from form
                            actual_consumption = {}
                            for key in request.POST.keys():
                                if key.startswith('actual_consumption_'):
                                    # Format: actual_consumption_{bom_id}_{warehouse}
                                    parts = key.replace('actual_consumption_', '').split('_', 1)
                                    if len(parts) == 2:
                                        bom_id = parts[0]
                                        warehouse = parts[1]
                                        amount_str = request.POST.get(key, '').strip()
                                        if amount_str:
                                            try:
                                                amount = Decimal(str(amount_str))
                                                if amount >= 0:  # Only accept non-negative values
                                                    if bom_id not in actual_consumption:
                                                        actual_consumption[bom_id] = {}
                                                    actual_consumption[bom_id][warehouse] = str(amount)
                                            except (ValueError, TypeError) as e:
                                                bug_logger.warning(f"Error parsing actual consumption amount for {key}: {str(e)}")
                            
                            # Update actual consumption if provided
                            if actual_consumption:
                                instance.actual_consumption = actual_consumption
                                bug_logger.debug(f"Actual consumption updated for program {program_id}: {len(actual_consumption)} BOM items")
                        
                        instance.save()
                        bug_logger.info(f"Production program {program_id} saved")
                        messages.success(request, 'برنامه تولید با موفقیت ذخیره شد.')
                        return redirect(reverse('production:program_crud', args=[program_id]))
                    elif action == 'revert':
                        # Revert an in-progress program back to confirmed
                        if not user_has_task(request.user, TaskChoices.PRODUCTION_REVERT_SCHEDULE.value):
                            audit_logger.activity("تلاش برای دسترسی به صفحه برگشت برنامه تولید بدون دسترسی")
                            messages.error(request, 'شما دسترسی به صفحه برگشت برنامه تولید ندارید.')
                            return redirect(reverse('production:program_crud', args=[program_id]))

                        if instance.status != ProductionProgram.Status.IN_PROGRESS:
                            messages.error(request, 'فقط برنامه‌های در حال اجرا قابل برگشت هستند')
                            # If request came from list view, stay on declaration page
                            if request.POST.get('origin') == 'list':
                                return redirect(reverse('production:production_declaration'))
                            return redirect(reverse('production:program_crud', args=[program_id]))


                        reason = request.POST.get('revert_reason', '').strip()
                        if not reason:
                            messages.error(request, 'لطفاً دلیل برگشت برنامه را وارد کنید')
                            return redirect(reverse('production:program_crud', args=[program_id]))
                        
                        # Create reversal stock entry
                        reversal_entry = revert_production_stock_entry(instance, request)
                        
                        if reversal_entry:
                            # Change status back to confirmed
                            instance.status = ProductionProgram.Status.CONFIRMED
                            instance.started_at = None
                            instance.actual_start_date = None
                            instance.save()
                            
                            # Create log
                            ProductionRevertLog.objects.create(
                                production_program=instance,
                                action_type='reverted',
                                reason=reason,
                                created_by=request.user.username if request.user.is_authenticated else 'anonymous',
                                reversal_stock_entry_id=reversal_entry.id
                            )
                            
                            bug_logger.info(f"Production program {program_id} reverted to confirmed status.")
                            audit_logger.activity(f"Production program {program_id} reverted by user. Reason: {reason}")
                            messages.success(request, f'برنامه تولید با موفقیت برگردانده شد. ثبت انبار معکوس: {reversal_entry.id}')
                            # If request came from list view, redirect back to declaration list
                            if request.POST.get('origin') == 'list':
                                return redirect(reverse('production:production_declaration'))
                            return redirect(reverse('production:program_crud', args=[program_id]))
                        else:
                            bug_logger.error(f"Error creating reversal stock entry for program {program_id}")
                            messages.error(request, 'خطا در برگشت برنامه. ثبت انبار معکوس ایجاد نشد')
                            if request.POST.get('origin') == 'list':
                                return redirect(reverse('production:production_declaration'))
                            return redirect(reverse('production:program_crud', args=[program_id]))
                    elif action == 'archive':
                        # Archive a completed program
                        if not user_has_task(request.user, TaskChoices.PRODUCTION_ARCHIVE.value):
                            audit_logger.activity("تلاش برای دسترسی به صفحه آرشیو برنامه تولید بدون دسترسی")
                            messages.error(request, 'شما دسترسی به صفحه آرشیو برنامه تولید ندارید.')
                            return redirect(reverse('production:program_crud', args=[program_id]))
                        
                        if instance.status != ProductionProgram.Status.COMPLETED:
                            messages.error(request, 'فقط برنامه‌های تکمیل شده قابل آرشیو هستند')
                            return redirect(reverse('production:program_crud', args=[program_id]))


                        reason = request.POST.get('archive_reason', '').strip()
                        
                        instance.is_archived = True
                        instance.save()
                        
                        # Create log
                        ProductionRevertLog.objects.create(
                            production_program=instance,
                            action_type='archived',
                            reason=reason if reason else None,
                            created_by=request.user.username if request.user.is_authenticated else 'anonymous'
                        )
                        
                        bug_logger.info(f"Production program {program_id} archived")
                        if reason:
                            audit_logger.info(f"Production program {program_id} archived. Reason: {reason}")
                        else:
                            audit_logger.info(f"Production program {program_id} archived")
                        messages.success(request, 'برنامه تولید با موفقیت آرشیو شد')
                        return redirect(reverse('production:production_declaration'))
                    elif action == 'unarchive':
                        # Unarchive a program
                        if not instance.is_archived:
                            messages.error(request, 'این برنامه در آرشیو نیست')
                            return redirect(reverse('production:program_crud', args=[program_id]))
                        
                        instance.is_archived = False
                        instance.save()
                        
                        # Create log
                        ProductionRevertLog.objects.create(
                            production_program=instance,
                            action_type='unarchived',
                            reason='Removed from archive',
                            created_by=request.user.username if request.user.is_authenticated else 'anonymous'
                        )
                        
                        bug_logger.info(f"Production program {program_id} removed from archive")
                        audit_logger.info(f"Production program {program_id} removed from archive")
                        messages.success(request, 'برنامه تولید با موفقیت از آرشیو خارج شد')
                        return redirect(reverse('production:production_declaration'))
                    
                    instance.save()
                    
                    if is_create:
                        bug_logger.info(f"New production program created with id {instance.id}")
                        audit_logger.info(f"New production program created with id {instance.id}")
                        messages.success(request, f'برنامه تولید با موفقیت ایجاد شد.')
                    else:
                        bug_logger.info(f"Production program {program_id} successfully edited")
                        audit_logger.info(f"Production program {program_id} edited")
                        messages.success(request, f'برنامه تولید با موفقیت ذخیره شد.')
                    
                    return redirect(reverse('production:program_crud', args=[instance.id]))
                    
                except Exception as e:
                    bug_logger.error(f"Error saving production program: {str(e)}")
                    messages.error(request, f'خطا در ذخیره برنامه تولید: {str(e)}')
            else:
                bug_logger.warning(f"Production program form is invalid: {form.errors}")
                messages.error(request, 'لطفاً خطاهای فرم را بررسی کنید.')
        else:
            # GET request
            if is_create:
                form = ProductionForm()
            else:
                form = ProductionForm(instance=program)
        
        # Get raw material inventory from primary warehouses
        raw_materials_inventory = []
        try:
            primary_warehouses = Warehouse.objects.filter(warehouse_type='primary')
            bug_logger.debug(f"Number of primary warehouses: {primary_warehouses.count()}")
            
            if primary_warehouses.exists():
                try:
                    raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
                    
                    inventory_items = InventoryItem.objects.filter(
                        warehouse__in=primary_warehouses,
                        content_type=raw_material_ct
                    ).select_related('warehouse', 'content_type')
                    
                    bug_logger.debug(f"Number of inventory items: {inventory_items.count()}")
                    
                    # Group raw materials by ID and sum inventory from warehouses
                    from collections import defaultdict
                    raw_materials_grouped = defaultdict(lambda: {
                        'raw_material_id': '',
                        'name': '',
                        'total_quantity': Decimal('0'),
                        'unit': '',
                        'warehouses': []
                    })
                    
                    for item in inventory_items:
                        try:
                            raw_material = item.item
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
                                
                                # Store warehouse details (include Django ID for proper lookups)
                                raw_materials_grouped[rm_id]['warehouses'].append({
                                    'id': item.warehouse.id,  # Django primary key
                                    'warehouse_id': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'warehouse_name': item.warehouse.name if (item.warehouse and item.warehouse.name) else (str(item.warehouse) if item.warehouse else '-'),
                                    'quantity': str(quantity),
                                })
                        except Exception as e:
                            bug_logger.warning(f"Error loading raw material: {str(e)}")
                            continue
                    
                    # Convert to list
                    for rm_id, data in raw_materials_grouped.items():
                        raw_materials_inventory.append({
                            'raw_material_id': data['raw_material_id'],
                            'name': data['name'],
                            'total_quantity': str(data['total_quantity']),
                            'unit': data['unit'],
                            'warehouses': data['warehouses']
                        })
                    
                except ContentType.DoesNotExist:
                    bug_logger.warning("ContentType for RawMaterial not found")
                except Exception as e:
                    bug_logger.warning(f"Error getting raw material inventory: {str(e)}")
            else:
                bug_logger.info("No primary warehouses found")
        
        except Exception as e:
            bug_logger.error(f"General error in getting raw material inventory: {str(e)}")
        
    # Prepare production info and BOM data for JavaScript
        production_infos_data = {}
        bom_data = {}
        
        # Get actual consumption data if editing existing program
        actual_consumption_data = {}
        if not is_create and program:
            actual_consumption_data = program.actual_consumption or {}
        
        try:
            # Ensure accessible flags are calculated before serialization to avoid leaking fields in JSON
            accessible_production_program_fields = get_accessible_production_program_fields(request.user)
            accessible_product_fields = get_accessible_product_fields(request.user)
            accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
            accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
            accessible_production_info_fields = get_accessible_production_info_fields(request.user)
            accessible_bom_fields = get_accessible_bom_fields(request.user)
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
                        # Get actual consumption for this BOM item if exists
                        bom_id_str = str(bom.id)
                        actual_consumption = actual_consumption_data.get(bom_id_str, '')
                        
                        # Convert Decimal to string if needed
                        if actual_consumption and hasattr(actual_consumption, '__float__'):
                            actual_consumption = str(actual_consumption)
                        
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
                        if actual_consumption and (accessible_bom_fields.get('percentage') or accessible_bom_fields.get('raw_material')):
                            bom_item_payload['actual_consumption'] = str(actual_consumption) if actual_consumption else ''
                        bom_items.append(bom_item_payload)
                    
                    bom_data[prod_info.id] = {
                        'program_id': prod_info.formula_id or '',
                        'min_batch_production': str(prod_info.min_batch_production) if prod_info.min_batch_production else '',
                        'specific_production_instruction': prod_info.specific_production_instruction or '',
                        'bom_items': bom_items
                    }
        except Exception as e:
            bug_logger.error(f"Error preparing BOM data: {str(e)}")
        
        # Get warehouse distribution if exists
        warehouse_distribution_data = {}
        if program and program.warehouse_distribution:
            warehouse_distribution_data = program.warehouse_distribution
        
        # Prepare actual consumption JSON
        actual_consumption_data = {}
        if program and program.actual_consumption:
            actual_consumption_data = program.actual_consumption
        
        # Get available warehouses for product warehouse selection
        # Filter to only secondary warehouses (ثانویه)
        available_warehouses = Warehouse.objects.filter(
            warehouse_type='secondary'
        ).order_by('name')
        
        # Get production warehouses
        production_warehouses = Warehouse.objects.filter(
            warehouse_type='production'
        ).order_by('name')
        
        # Check permissions for revert and archive; ارجاع به مدیر بدون task است؛ حل ارجاع فقط سوپرادمین
        can_revert = user_has_task(request.user, TaskChoices.PRODUCTION_REVERT_SCHEDULE.value)
        can_archive = user_has_task(request.user, TaskChoices.PRODUCTION_ARCHIVE.value)
        declaration_referred_to_manager = getattr(program, 'declaration_referred_to_manager', False) if program else False
        can_resolve_referral = request.user.is_superuser and declaration_referred_to_manager
        
        # Product inventory/requirement data (shared with program create view)
        dashboard_context = _get_dashboard_context()
        safe_flow = dashboard_context.get('product_flow_status', [])
        
        # بررسی دسترسی فیلدها
        accessible_production_program_fields = get_accessible_production_program_fields(request.user)
        accessible_product_fields = get_accessible_product_fields(request.user)
        accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
        accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
        accessible_production_info_fields = get_accessible_production_info_fields(request.user)
        accessible_bom_fields = get_accessible_bom_fields(request.user)
        
        context = {
            'form': form,
            'program': program,
            'is_create': is_create,
            'raw_materials_inventory': raw_materials_inventory,
            'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
            'production_infos_json': json.dumps(production_infos_data),
            'bom_data_json': json.dumps(bom_data),
            'warehouse_distribution_json': json.dumps(warehouse_distribution_data),
            'actual_consumption_json': json.dumps(actual_consumption_data),
            'program_status': program.status if program else 'draft',
            'warehouses': available_warehouses,
            'production_warehouses': production_warehouses,
            'max_bom_error': Decimal(str(program.max_bom_error)) if program and program.max_bom_error else Decimal('5'),
            'declaration_referred_to_manager': declaration_referred_to_manager,
            'can_resolve_referral': can_resolve_referral,
            'can_revert': can_revert,
            'can_archive': can_archive,
            'accessible_production_program_fields': accessible_production_program_fields,
            'accessible_product_fields': accessible_product_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_warehouse_fields': accessible_warehouse_fields,
            'accessible_production_info_fields': accessible_production_info_fields,
            'accessible_bom_fields': accessible_bom_fields,
            'accessible_production_info_fields_json': json.dumps(accessible_production_info_fields),
            'accessible_bom_fields_json': json.dumps(accessible_bom_fields),
            'accessible_production_program_fields_json': json.dumps(accessible_production_program_fields),
            'accessible_product_fields_json': json.dumps(accessible_product_fields),
            'accessible_raw_material_fields_json': json.dumps(accessible_raw_material_fields),
            'accessible_warehouse_fields_json': json.dumps(accessible_warehouse_fields),
            # Product inventory snapshot + net unplanned requirement (for auto-fill)
            'product_flow_status': safe_flow,
            'product_flow_status_json': json.dumps(safe_flow, default=str),
        }
        
        if is_create:
            bug_logger.info("Production program creation page loaded successfully")
            audit_logger.activity("Accessed production program creation page")
        else:
            bug_logger.info(f"Production program {program_id} details page loaded successfully")
            audit_logger.activity(f"Accessed production program {program_id} details page")

        return render(request, 'production_declaration_crud.html', context)
    
    except Exception as e:
        bug_logger.error(f"General error in page load: {str(e)}")        
        available_warehouses = Warehouse.objects.filter(
            warehouse_type='secondary'
        ).order_by('name')
        production_warehouses = Warehouse.objects.filter(
            warehouse_type='production'
        ).order_by('name')
        
        # Check permissions for revert and archive
        can_revert = user_has_task(request.user, TaskChoices.PRODUCTION_REVERT_SCHEDULE.value)
        can_archive = user_has_task(request.user, TaskChoices.PRODUCTION_ARCHIVE.value)
        
        # Product inventory/requirement data (shared with program create view)
        try:
            dashboard_context = _get_dashboard_context()
            safe_flow = dashboard_context.get('product_flow_status', [])
        except Exception:
            safe_flow = []
        
        context = {
            'form': ProductionForm(),
            'program': None,
            'is_create': is_create,
            'raw_materials_inventory': [],
            'raw_materials_inventory_json': json.dumps([]),
            'production_infos_json': json.dumps({}),
            'bom_data_json': json.dumps({}),
            'warehouse_distribution_json': json.dumps({}),
            'program_status': 'draft',
            'warehouses': available_warehouses,
            'production_warehouses': production_warehouses,
            'declaration_referred_to_manager': False,
            'can_resolve_referral': False,
            'can_revert': can_revert,
            'can_archive': can_archive,
            'accessible_production_program_fields': {},
            'accessible_product_fields': {},
            'accessible_raw_material_fields': {},
            'accessible_warehouse_fields': {},
            'accessible_production_info_fields': {},
            'accessible_bom_fields': {},
            'accessible_production_program_fields_json': json.dumps({}),
            'accessible_product_fields_json': json.dumps({}),
            'accessible_raw_material_fields_json': json.dumps({}),
            'accessible_warehouse_fields_json': json.dumps({}),
            'accessible_production_info_fields_json': json.dumps({}),
            'accessible_bom_fields_json': json.dumps({}),
            # Product inventory snapshot + net unplanned requirement (for auto-fill)
            'product_flow_status': safe_flow,
            'product_flow_status_json': json.dumps(safe_flow, default=str),
        }
        return render(request, 'production_declaration_crud.html', context)



@login_required
def archived_programs_view(request):
    """
    Display archived production programs
    """
    # Check permission for submitting production reports
    if not user_has_task(request.user, TaskChoices.PRODUCTION_DECLARATION_ARCHIVED.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه برنامه‌های بایگانی‌شده بدون دسترسی")
        messages.error(request, 'شما دسترسی به صفحه برنامه‌های بایگانی‌شده ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    audit_logger.info("Access to archived production programs page")    
    try:
        # Get archived programs
        programs = ProductionProgram.objects.filter(
            is_archived=True,
            status='completed'
        ).select_related('product', 'production_info').order_by('-created_at', '-id')
        
        bug_logger.debug(f"Number of archived programs: {programs.count()}")
        
        context = {
            'programs': programs,
        }
        
        bug_logger.info("Archived production programs page loaded successfully")
        return render(request, 'production_archived.html', context)
    
    except Exception as e:
        bug_logger.error(f"Error loading archived programs: {str(e)}")
        bug_logger.error(traceback.format_exc())
        messages.error(request, 'Error loading archived programs')
        return redirect(reverse('production:production_declaration'))