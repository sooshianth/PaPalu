from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from decimal import Decimal
from django.utils import timezone
import json

import logging
import traceback
from core.logging_levels import *
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field

from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductModel import Product
from core.StockEntryFolder.StockEntryModel import StockEntry
from core.StockEntryFolder.SourceStockModel import SourceStock
from core.StockEntryFolder.TargetStockModel import TargetStock

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_production_program_fields(user):
    """بررسی دسترسی کاربر به فیلدهای ProductionProgram - برای ویرایش"""
    accessible_fields = {}
    accessible_fields['id'] = user_can_access_field(user, ProductionProgram, 'id', 'edit')
    accessible_fields['program_id'] = user_can_access_field(user, ProductionProgram, 'program_id', 'edit')
    accessible_fields['execution_date'] = user_can_access_field(user, ProductionProgram, 'execution_date', 'edit')
    accessible_fields['planned_weight_ton'] = user_can_access_field(user, ProductionProgram, 'planned_weight_ton', 'edit')
    accessible_fields['produced_weight_ton'] = user_can_access_field(user, ProductionProgram, 'produced_weight_ton', 'edit')
    accessible_fields['packaging_type'] = user_can_access_field(user, ProductionProgram, 'packaging_type', 'edit')
    accessible_fields['predicted_start_time'] = user_can_access_field(user, ProductionProgram, 'predicted_start_time', 'edit')
    accessible_fields['predicted_end_time'] = user_can_access_field(user, ProductionProgram, 'predicted_end_time', 'edit')
    accessible_fields['started_at'] = user_can_access_field(user, ProductionProgram, 'started_at', 'edit')
    accessible_fields['completed_at'] = user_can_access_field(user, ProductionProgram, 'completed_at', 'edit')
    accessible_fields['status'] = user_can_access_field(user, ProductionProgram, 'status', 'edit')
    accessible_fields['product'] = user_can_access_field(user, ProductionProgram, 'product', 'edit')
    accessible_fields['product_warehouse'] = user_can_access_field(user, ProductionProgram, 'product_warehouse', 'edit')
    accessible_fields['production_warehouse'] = user_can_access_field(user, ProductionProgram, 'production_warehouse', 'edit')
    accessible_fields['production_info'] = user_can_access_field(user, ProductionProgram, 'production_info', 'edit')
    accessible_fields['actual_consumption'] = user_can_access_field(user, ProductionProgram, 'actual_consumption', 'edit')
    accessible_fields['extra_description'] = user_can_access_field(user, ProductionProgram, 'extra_description', 'edit')
    accessible_fields['planned_hours'] = user_can_access_field(user, ProductionProgram, 'planned_hours', 'edit')
    accessible_fields['actual_start_date'] = user_can_access_field(user, ProductionProgram, 'actual_start_date', 'edit')
    accessible_fields['fulfillment_percentage'] = user_can_access_field(user, ProductionProgram, 'fulfillment_percentage', 'edit')
    accessible_fields['confirmed_by_warehouseman'] = user_can_access_field(user, ProductionProgram, 'confirmed_by_warehouseman', 'edit')
    accessible_fields['sent_to_manager_for_revalidation'] = user_can_access_field(user, ProductionProgram, 'sent_to_manager_for_revalidation', 'edit')
    accessible_fields['reason_for_warehouse_disapprove'] = user_can_access_field(user, ProductionProgram, 'reason_for_warehouse_disapprove', 'edit')
    
    return accessible_fields


def get_accessible_product_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Product"""
    accessible_fields = {}
    accessible_fields['name'] = user_can_access_field(user, Product, 'name', 'view')
    accessible_fields['packaging_type'] = user_can_access_field(user, Product, 'packaging_type', 'view')
    return accessible_fields


def get_accessible_warehouse_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Warehouse"""
    accessible_fields = {}
    accessible_fields['warehouse_id'] = user_can_access_field(user, Warehouse, 'warehouse_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, Warehouse, 'name', 'view')
    accessible_fields['warehouse_type'] = user_can_access_field(user, Warehouse, 'warehouse_type', 'view')
    return accessible_fields


def get_accessible_stock_entry_fields(user):
    """بررسی دسترسی کاربر به فیلدهای StockEntry"""
    accessible_fields = {}
    accessible_fields['id'] = user_can_access_field(user, StockEntry, 'id', 'view')
    accessible_fields['transaction_date'] = user_can_access_field(user, StockEntry, 'transaction_date', 'view')
    accessible_fields['notes'] = user_can_access_field(user, StockEntry, 'notes', 'view')
    accessible_fields['is_committed'] = user_can_access_field(user, StockEntry, 'is_committed', 'view')
    return accessible_fields


def get_accessible_inventory_item_fields(user):
    """بررسی دسترسی کاربر به فیلدهای InventoryItem"""
    accessible_fields = {}
    accessible_fields['warehouse'] = user_can_access_field(user, InventoryItem, 'warehouse', 'view')
    accessible_fields['quantity'] = user_can_access_field(user, InventoryItem, 'quantity', 'view')
    accessible_fields['item'] = user_can_access_field(user, InventoryItem, 'item', 'view')
    return accessible_fields


def get_accessible_raw_material_fields(user):
    """بررسی دسترسی کاربر به فیلدهای RawMaterial"""
    accessible_fields = {}
    accessible_fields['raw_material_id'] = user_can_access_field(user, RawMaterial, 'raw_material_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, RawMaterial, 'name', 'view')
    return accessible_fields


def get_accessible_bom_fields(user):
    """بررسی دسترسی کاربر به فیلدهای BOM"""
    accessible_fields = {}
    accessible_fields['raw_material'] = user_can_access_field(user, BOM, 'raw_material', 'view')
    accessible_fields['quantity'] = user_can_access_field(user, BOM, 'quantity', 'view')  # DELETE LATER
    accessible_fields['percentage'] = user_can_access_field(user, BOM, 'percentage', 'view')
    return accessible_fields


def calculate_actual_consumption_from_stock_entries(program, stock_entries):
    """
    محاسبه actual_consumption از stock entries مربوط به برنامه
    فقط stock entries که committed هستند را در نظر می‌گیرد
    """
    actual_consumption = {}
    
    if not program.production_info:
        return actual_consumption
    
    # ایجاد mapping از raw_material_id به bom_id
    bom_mapping = {}
    for bom in program.production_info.bom_items.all():
        if bom.raw_material:
            bom_mapping[bom.raw_material.id] = str(bom.id)
    
    raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
    
    # فقط committed stock entries را بررسی کن
    committed_entries = [e for e in stock_entries if e.is_committed]
    
    for entry in committed_entries:
        # بررسی source stocks (برداشت از انبار)
        for source in entry.source_stocks.all():
            if source.from_content_type == raw_material_ct and source.from_item:
                raw_material_id = source.from_object_id
                bom_id = bom_mapping.get(raw_material_id)
                
                if bom_id:
                    warehouse_id = str(source.from_warehouse.id) if source.from_warehouse else 'global'
                    quantity = Decimal(str(source.quantity)) if source.quantity else Decimal('0')
                    if bom_id not in actual_consumption:
                        actual_consumption[bom_id] = {}
                    if warehouse_id not in actual_consumption[bom_id]:
                        actual_consumption[bom_id][warehouse_id] = Decimal('0')
                    actual_consumption[bom_id][warehouse_id] += quantity
    
    # تبدیل به string برای JSON
    for bom_id in actual_consumption:
        for warehouse_id in actual_consumption[bom_id]:
            actual_consumption[bom_id][warehouse_id] = str(Decimal(str(actual_consumption[bom_id][warehouse_id])).quantize(Decimal('0.001')))
    
    return actual_consumption


def calculate_warehouse_before_after(program, stock_entries):
    """
    محاسبه وضعیت قبل و بعد انبارها بر اساس ثبت‌های انبار
    این فقط برای نمایش است و هیچ تغییری در دیتابیس ایجاد نمی‌کند
    """
    try:
        warehouses = Warehouse.objects.filter(
            warehouse_type__in=['primary', 'production', 'secondary']
        )
        
        before_after = {}
        
        for warehouse in warehouses:
            before_after[warehouse.id] = {
                'warehouse': warehouse,
                'before': {},
                'after': {},
                'changes': []
            }
            
            # محاسبه وضعیت بعد (موجودی فعلی)
            current_inventory = InventoryItem.objects.filter(warehouse=warehouse)
            for item in current_inventory:
                item_key = f"{item.content_type.model}_{item.object_id}"
                before_after[warehouse.id]['after'][item_key] = {
                    'item': item.item,
                    'quantity': item.quantity or Decimal('0'),
                    'unit': item.unit,
                    'item_type': item.item_type
                }
            
            # برای محاسبه before، باید تمام تراکنش‌های committed را به ترتیب زمانی معکوس اعمال کنیم
            before_state = {}
            for item_key, item_data in before_after[warehouse.id]['after'].items():
                before_state[item_key] = item_data['quantity']
            
            # مرتب‌سازی stock entries بر اساس transaction_date (جدیدترین اول)
            committed_entries = [e for e in stock_entries if e.is_committed]
            sorted_entries = sorted(
                committed_entries,
                key=lambda x: x.transaction_date if x.transaction_date else x.created_at,
                reverse=False  # قدیمی‌ترین اول
            )
            
            # اعمال معکوس تراکنش‌ها
            for entry in sorted_entries:
                for source in entry.source_stocks.filter(from_warehouse=warehouse):
                    item_key = f"{source.from_content_type.model}_{source.from_object_id}"
                    change_amount = source.quantity or Decimal('0')
                    
                    if item_key not in before_state:
                        before_state[item_key] = Decimal('0')
                    
                    before_state[item_key] = before_state[item_key] + change_amount
                
                for target in entry.target_stocks.filter(to_warehouse=warehouse):
                    item_key = f"{target.to_content_type.model}_{target.to_object_id}"
                    change_amount = target.quantity or Decimal('0')
                    
                    if item_key not in before_state:
                        before_state[item_key] = Decimal('0')
                    
                    before_state[item_key] = before_state[item_key] - change_amount
            
            # ذخیره وضعیت before
            for item_key, before_qty in before_state.items():
                if item_key in before_after[warehouse.id]['after']:
                    before_after[warehouse.id]['before'][item_key] = {
                        'item': before_after[warehouse.id]['after'][item_key]['item'],
                        'quantity': before_qty,
                        'unit': before_after[warehouse.id]['after'][item_key]['unit'],
                        'item_type': before_after[warehouse.id]['after'][item_key]['item_type']
                    }
        
        return before_after
        
    except Exception as e:
        bug_logger.error(f"خطا در محاسبه قبل و بعد انبار: {str(e)}\n{traceback.format_exc()}")
        return {}


@login_required
def manager_warehouse_resolve(request, program_id):
    """
    صفحه حل مشکلات تولید توسط مدیر - شبیه warehouse_production_detail اما با قابلیت ویرایش
    """
    # بررسی دسترسی task
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        audit_logger.alert(f"دسترسی غیرمجاز به حل مشکلات تولید - برنامه {program_id}")
        return HttpResponseForbidden("شما اجازه دسترسی به این صفحه را ندارید.")
    
    audit_logger.info(f"دسترسی مدیر به حل مشکلات برنامه {program_id}")
    
    try:
        program = get_object_or_404(
            ProductionProgram.objects.select_related(
                'product',
                'product_warehouse',
                'production_warehouse',
                'production_info'
            ),
            id=program_id,
            sent_to_manager_for_revalidation=True
        )
        
        # دریافت ثبت‌های انبار مرتبط با این برنامه
        # جستجو بر اساس شناسه برنامه یا ID برنامه در notes
        stock_entries = StockEntry.objects.filter(
            Q(notes__icontains=f'برنامه {program.program_id}') |
            Q(notes__icontains=f'برنامه {program.id}') |
            Q(notes__icontains=f'program {program.program_id}') |
            Q(notes__icontains=f'program {program.id}')
        ).order_by('-transaction_date')
        
        # دریافت موجودی فعلی انبارهای مرتبط
        warehouses = Warehouse.objects.filter(
            warehouse_type__in=['primary', 'production', 'secondary']
        ).prefetch_related('inventory_items')
        
        warehouse_inventories = {}
        for warehouse in warehouses:
            warehouse_inventories[warehouse.id] = {
                'warehouse': warehouse,
                'items': []
            }
            
            for item in warehouse.inventory_items.all():
                warehouse_inventories[warehouse.id]['items'].append({
                    'item': item.item,
                    'quantity': item.quantity,
                    'unit': item.unit,
                    'item_type': item.item_type
                })
        
        # محاسبه قبل و بعد
        before_after_calculation = calculate_warehouse_before_after(program, stock_entries)
        
        # دریافت BOM items و actual consumption
        # دریافت BOM items و actual consumption
        # استفاده از مقدار ذخیره شده در دیتابیس (مانند warehouse view)
        # دیتابیس فقط زمانی به‌روزرسانی می‌شود که stock entry جدید commit شود
        bom_items_data = []
        if program.production_info:
            bom_items = program.production_info.bom_items.all().select_related('raw_material')
            actual_consumption = program.actual_consumption or {}
            warehouse_distribution = program.warehouse_distribution or {}
            
            # دریافت اطلاعات انبارها برای نمایش
            warehouses_list = list(warehouses)
            warehouses_dict = {str(w.id): w for w in warehouses_list}
            
            for bom in bom_items:
                # Calculate total consumption needed based on planned weight using percentage
                planned_weight = Decimal(str(program.planned_weight_ton)) if program.planned_weight_ton else Decimal('0')
                percentage = Decimal(str(bom.percentage)) if bom.percentage else Decimal('0')
                total_consumption = (percentage / Decimal('100')) * planned_weight if planned_weight > 0 else Decimal('0')
                
                # Get actual consumption for this BOM
                bom_id_str = str(bom.id)
                actual_used = actual_consumption.get(bom_id_str, {})
                
                # Get warehouse distribution for this BOM
                warehouse_dist = warehouse_distribution.get(bom_id_str, [])
                
                # Create rows for each warehouse
                warehouse_rows = []
                
                if warehouse_dist and isinstance(warehouse_dist, list) and len(warehouse_dist) > 0:
                    for dist_item in warehouse_dist:
                        if isinstance(dist_item, dict):
                            warehouse_id = str(dist_item.get('warehouse', ''))
                            planned_amount = Decimal(str(dist_item.get('amount', 0) or 0))
                            actual_amount = Decimal('0')
                            if isinstance(actual_used, dict):
                                warehouse_id_str = str(warehouse_id)
                                actual_amount = Decimal(str(actual_used.get(warehouse_id_str, 0) or 0))
                            
                            variance = actual_amount - planned_amount
                            variance_percent = (variance / planned_amount * 100) if planned_amount > 0 else Decimal('0')
                            warehouse_obj = warehouses_dict.get(warehouse_id)
                            if warehouse_obj:
                                warehouse_rows.append({
                                    'warehouse_id': warehouse_id,
                                    'warehouse_name': warehouse_obj.name,
                                    'planned_amount': planned_amount.quantize(Decimal('0.001')),
                                    'actual_amount': actual_amount.quantize(Decimal('0.001')),
                                    'variance': variance.quantize(Decimal('0.001')),
                                    'variance_percent': variance_percent.quantize(Decimal('0.01'))
                                })
                elif isinstance(actual_used, dict) and len(actual_used) > 0:
                    for warehouse_id, actual_amount in actual_used.items():
                        if warehouse_id in ['global', 'none', None]:
                            continue
                        try:
                            actual_amount_dec = Decimal(str(actual_amount)) if actual_amount else Decimal('0')
                            warehouse_obj = warehouses_dict.get(str(warehouse_id))
                            if warehouse_obj:
                                warehouse_rows.append({
                                    'warehouse_id': str(warehouse_id),
                                    'warehouse_name': warehouse_obj.name,
                                    'planned_amount': None,
                                    'actual_amount': actual_amount_dec.quantize(Decimal('0.001')),
                                    'variance': None,
                                    'variance_percent': None
                                })
                        except (ValueError, TypeError):
                            pass
                
                if warehouse_rows:
                    total_actual_consumption = sum(Decimal(str(row.get('actual_amount', 0) or 0)) for row in warehouse_rows)
                elif isinstance(actual_used, dict):
                    total_actual_consumption = sum(Decimal(str(v)) for v in actual_used.values() if v is not None and str(v).strip())
                elif isinstance(actual_used, str):
                    try:
                        total_actual_consumption = Decimal(str(actual_used))
                    except Exception:
                        total_actual_consumption = Decimal('0')
                else:
                    total_actual_consumption = Decimal('0')
                total_variance = total_actual_consumption - total_consumption if total_consumption > 0 else Decimal('0')
                total_variance_percent = (total_variance / total_consumption * 100) if total_consumption > 0 else Decimal('0')
                
                bom_items_data.append({
                    'id': bom.id,
                    'raw_material': bom.raw_material,
                    'planned_percentage': percentage,
                    'total_consumption': total_consumption.quantize(Decimal('0.001')),
                    'total_actual_consumption': total_actual_consumption.quantize(Decimal('0.001')),
                    'total_variance': total_variance.quantize(Decimal('0.001')),
                    'total_variance_percent': total_variance_percent.quantize(Decimal('0.01')),
                    'unit': bom.raw_material.primary_unit if bom.raw_material else '-',
                    'warehouse_rows': warehouse_rows,
                    'has_warehouse_details': len(warehouse_rows) > 0
                })
        
        # بررسی دسترسی فیلدها
        accessible_production_program_fields = get_accessible_production_program_fields(request.user)
        accessible_product_fields = get_accessible_product_fields(request.user)
        accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
        accessible_stock_entry_fields = get_accessible_stock_entry_fields(request.user)
        accessible_inventory_item_fields = get_accessible_inventory_item_fields(request.user)
        accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
        accessible_bom_fields = get_accessible_bom_fields(request.user)
        
        # دریافت لیست همه مواد اولیه و محصولات و انبارها برای فرم‌ها
        all_raw_materials = RawMaterial.objects.all()
        all_products = Product.objects.all()
        all_warehouses = Warehouse.objects.all()
        
        context = {
            'program': program,
            'stock_entries': stock_entries,
            'warehouse_inventories': warehouse_inventories,
            'before_after_calculation': before_after_calculation,
            'bom_items_data': bom_items_data,
            'accessible_production_program_fields': accessible_production_program_fields,
            'accessible_product_fields': accessible_product_fields,
            'accessible_warehouse_fields': accessible_warehouse_fields,
            'accessible_stock_entry_fields': accessible_stock_entry_fields,
            'accessible_inventory_item_fields': accessible_inventory_item_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_bom_fields': accessible_bom_fields,
            'all_raw_materials': all_raw_materials,
            'all_products': all_products,
            'all_warehouses': all_warehouses,
        }
        
        bug_logger.info(f"صفحه حل مشکلات برنامه {program_id} با موفقیت بارگذاری شد")
        return render(request, 'manager_warehouse_resolve.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در بارگذاری صفحه حل مشکلات برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, "خطا در بارگذاری صفحه")
        return redirect('production:warehouse_production_list')


@login_required
def manager_save_program(request, program_id):
    """ذخیره تغییرات برنامه"""
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        audit_logger.alert(f"دسترسی غیرمجاز به ذخیره برنامه - برنامه {program_id}")
        return JsonResponse({'success': False, 'message': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'متد نامعتبر'}, status=400)
    
    try:
        program = get_object_or_404(ProductionProgram, id=program_id)
        
        with transaction.atomic():
            # بروزرسانی فیلدهای قابل ویرایش
            if 'program_id' in request.POST:
                program.program_id = request.POST.get('program_id', '')
            if 'execution_date' in request.POST and request.POST.get('execution_date'):
                try:
                    exec_date = request.POST.get('execution_date')
                    if exec_date:
                        program.execution_date = exec_date
                except:
                    pass
            if 'planned_weight_ton' in request.POST:
                try:
                    program.planned_weight_ton = Decimal(request.POST.get('planned_weight_ton', 0))
                except:
                    pass
            old_produced_weight = program.produced_weight_ton or Decimal('0')
            if 'produced_weight_ton' in request.POST:
                try:
                    new_produced_weight = Decimal(request.POST.get('produced_weight_ton', 0))
                    
                    # پیدا کردن مقدار اولیه (original first real tonnage) از stock entry "تکمیل تولید"
                    original_produced_weight = None
                    if program.product and program.product_warehouse:
                        product_ct = ContentType.objects.get_for_model(Product)
                        # جستجوی stock entry committed با notes "تکمیل تولید برنامه X - تبدیل مواد اولیه به محصول نهایی"
                        completion_entry = StockEntry.objects.filter(
                            (Q(notes__icontains=f'تکمیل تولید برنامه {program.program_id or program.id}') |
                             Q(notes__icontains=f'تکمیل تولید برنامه {program.id}')) &
                            Q(notes__icontains='تبدیل مواد اولیه به محصول نهایی') &
                            Q(is_committed=True)
                        ).first()
                        
                        if completion_entry:
                            # پیدا کردن target stock که مربوط به محصول و انبار محصول است
                            target_stock = completion_entry.target_stocks.filter(
                                to_content_type=product_ct,
                                to_object_id=program.product.id,
                                to_warehouse=program.product_warehouse
                            ).first()
                            
                            if target_stock and target_stock.quantity:
                                original_produced_weight = target_stock.quantity
                    
                    # اگر مقدار اولیه پیدا نشد، از مقدار فعلی استفاده کن (یا 0)
                    if original_produced_weight is None:
                        original_produced_weight = Decimal('0')
                    
                    # محاسبه تفاوت بر اساس مقدار اولیه (نه مقدار قبلی)
                    difference = new_produced_weight - original_produced_weight
                    
                    # بررسی اینکه آیا مقدار جدید برابر با مقدار اولیه است
                    if new_produced_weight == original_produced_weight:
                        # اگر برابر است، stock entry تصحیحی را حذف کن (اگر وجود داشته باشد)
                        correction_entry = StockEntry.objects.filter(
                            Q(notes__icontains=f'تصحیح تناژ تولید شده برنامه {program.program_id or program.id}') |
                            Q(notes__icontains=f'correction produced_weight program {program.program_id or program.id}')
                        ).exclude(is_committed=True).first()
                        
                        if correction_entry:
                            correction_entry.delete()
                            bug_logger.info(f"Stock entry تصحیحی {correction_entry.id} حذف شد چون مقدار به مقدار اولیه ({original_produced_weight}) برگشت")
                        
                        program.produced_weight_ton = new_produced_weight
                    # فقط اگر تفاوت وجود داشته باشد و محصول و انبار محصول مشخص باشند
                    elif difference != 0 and program.product and program.product_warehouse:
                        program.produced_weight_ton = new_produced_weight
                        
                        product_ct = ContentType.objects.get_for_model(Product)
                        
                        # جستجوی stock entry تصحیحی uncommitted موجود
                        correction_entry = StockEntry.objects.filter(
                            Q(notes__icontains=f'تصحیح تناژ تولید شده برنامه {program.program_id or program.id}') |
                            Q(notes__icontains=f'correction produced_weight program {program.program_id or program.id}')
                        ).exclude(is_committed=True).first()
                        
                        if correction_entry:
                            # ویرایش stock entry تصحیحی موجود
                            # حذف source و target stocks قبلی
                            correction_entry.source_stocks.all().delete()
                            correction_entry.target_stocks.all().delete()
                            
                            # ایجاد stock جدید با مقدار تفاوت
                            if difference > 0:
                                TargetStock.objects.create(
                                    stock_entry=correction_entry,
                                    to_content_type=product_ct,
                                    to_object_id=program.product.id,
                                    to_warehouse=program.product_warehouse,
                                    quantity=difference,
                                )
                            # اگر difference منفی باشد، باید source stock ایجاد کنیم (کاهش)
                            elif difference < 0:
                                SourceStock.objects.create(
                                    stock_entry=correction_entry,
                                    from_content_type=product_ct,
                                    from_object_id=program.product.id,
                                    from_warehouse=program.product_warehouse,
                                    quantity=abs(difference),
                                )
                            
                            bug_logger.info(f"Stock entry تصحیحی {correction_entry.id} برای تناژ تولید شده به‌روزرسانی شد: تفاوت {difference}")
                        else:
                            # ایجاد stock entry تصحیحی جدید
                            correction_entry = StockEntry.objects.create(
                                transaction_date=timezone.now(),
                                notes=f'تصحیح تناژ تولید شده برنامه {program.program_id or program.id}',
                                is_committed=False
                            )
                            
                            # ایجاد target stock (اگر تفاوت مثبت باشد - افزودن)
                            if difference > 0:
                                TargetStock.objects.create(
                                    stock_entry=correction_entry,
                                    to_content_type=product_ct,
                                    to_object_id=program.product.id,
                                    to_warehouse=program.product_warehouse,
                                    quantity=difference,
                                )
                            # ایجاد source stock (اگر تفاوت منفی باشد - کاهش)
                            elif difference < 0:
                                SourceStock.objects.create(
                                    stock_entry=correction_entry,
                                    from_content_type=product_ct,
                                    from_object_id=program.product.id,
                                    from_warehouse=program.product_warehouse,
                                    quantity=abs(difference),
                                )
                            
                            bug_logger.info(f"Stock entry تصحیحی {correction_entry.id} برای تناژ تولید شده ایجاد شد: تفاوت {difference} (از {old_produced_weight} به {new_produced_weight})")
                    elif difference == 0:
                        # اگر تفاوتی نیست، فقط مقدار را ذخیره کن
                        program.produced_weight_ton = new_produced_weight
                except Exception as e:
                    bug_logger.error(f"خطا در ایجاد/ویرایش stock entry تصحیحی برای produced_weight_ton: {str(e)}\n{traceback.format_exc()}")
                    # در صورت خطا، مقدار را ذخیره نکن
                    pass
            if 'packaging_type' in request.POST:
                program.packaging_type = request.POST.get('packaging_type', '')
            if 'predicted_start_time' in request.POST and request.POST.get('predicted_start_time'):
                program.predicted_start_time = request.POST.get('predicted_start_time')
            if 'predicted_end_time' in request.POST and request.POST.get('predicted_end_time'):
                program.predicted_end_time = request.POST.get('predicted_end_time')
            if 'started_at' in request.POST and request.POST.get('started_at'):
                program.started_at = request.POST.get('started_at')
            if 'completed_at' in request.POST and request.POST.get('completed_at'):
                program.completed_at = request.POST.get('completed_at')
            if 'product' in request.POST and request.POST.get('product'):
                try:
                    program.product = Product.objects.get(id=int(request.POST.get('product')))
                except:
                    pass
            if 'product_warehouse' in request.POST and request.POST.get('product_warehouse'):
                try:
                    program.product_warehouse = Warehouse.objects.get(id=int(request.POST.get('product_warehouse')))
                except:
                    pass
            if 'production_warehouse' in request.POST and request.POST.get('production_warehouse'):
                try:
                    program.production_warehouse = Warehouse.objects.get(id=int(request.POST.get('production_warehouse')))
                except:
                    pass
            if 'extra_description' in request.POST:
                program.extra_description = request.POST.get('extra_description', '')
            if 'planned_hours' in request.POST:
                try:
                    program.planned_hours = Decimal(request.POST.get('planned_hours', 0))
                except:
                    pass
            
            program.save()
            
            audit_logger.info(f"ذخیره تغییرات برنامه {program_id} توسط مدیر {request.user.username}")
            bug_logger.info(f"ذخیره تغییرات برنامه {program_id} توسط مدیر")
        
        return JsonResponse({'success': True, 'message': 'تغییرات با موفقیت ذخیره شد'})
        
    except Exception as e:
        bug_logger.error(f"خطا در ذخیره برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': f'خطا در ذخیره: {str(e)}'}, status=500)


@login_required
def manager_create_stock_entry(request, program_id):
    """
    ایجاد stock entry جدید توسط مدیر
    """
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=400)
    
    try:
        program = get_object_or_404(ProductionProgram, id=program_id)
        
        with transaction.atomic():
            # ایجاد stock entry
            notes = request.POST.get('notes', '').strip()
            if not notes:
                notes = f'تصحیح دستی توسط مدیر - برنامه {program.program_id or program.id}'
            else:
                # اطمینان از اینکه notes شامل شناسه برنامه است
                if f'برنامه {program.program_id or program.id}' not in notes:
                    notes = f'{notes} - برنامه {program.program_id or program.id}'
            
            stock_entry = StockEntry.objects.create(
                transaction_date=timezone.now(),
                notes=notes,
                is_committed=False
            )
            
            # پردازش source stocks
            source_stocks_data = json.loads(request.POST.get('source_stocks', '[]'))
            for source_data in source_stocks_data:
                item_type = source_data.get('item_type')
                item_id = source_data.get('item_id')
                warehouse_id = source_data.get('warehouse_id')
                quantity = Decimal(str(source_data.get('quantity', 0)))
                
                if quantity <= 0 or not item_id or not warehouse_id:
                    continue
                
                try:
                    warehouse = Warehouse.objects.get(id=warehouse_id)
                    
                    if item_type == 'raw_material':
                        content_type = ContentType.objects.get_for_model(RawMaterial)
                        item = RawMaterial.objects.get(id=item_id)
                    elif item_type == 'product':
                        content_type = ContentType.objects.get_for_model(Product)
                        item = Product.objects.get(id=item_id)
                    else:
                        continue
                    
                    SourceStock.objects.create(
                        stock_entry=stock_entry,
                        from_content_type=content_type,
                        from_object_id=item.id,
                        from_warehouse=warehouse,
                        quantity=quantity,
                    )
                except Exception as e:
                    bug_logger.warning(f"خطا در ایجاد source stock: {str(e)}")
                    continue
            
            # پردازش target stocks
            target_stocks_data = json.loads(request.POST.get('target_stocks', '[]'))
            for target_data in target_stocks_data:
                item_type = target_data.get('item_type')
                item_id = target_data.get('item_id')
                warehouse_id = target_data.get('warehouse_id')
                quantity = Decimal(str(target_data.get('quantity', 0)))
                
                if quantity <= 0 or not item_id or not warehouse_id:
                    continue
                
                try:
                    warehouse = Warehouse.objects.get(id=warehouse_id)
                    
                    if item_type == 'raw_material':
                        content_type = ContentType.objects.get_for_model(RawMaterial)
                        item = RawMaterial.objects.get(id=item_id)
                    elif item_type == 'product':
                        content_type = ContentType.objects.get_for_model(Product)
                        item = Product.objects.get(id=item_id)
                    else:
                        continue
                    
                    TargetStock.objects.create(
                        stock_entry=stock_entry,
                        to_content_type=content_type,
                        to_object_id=item.id,
                        to_warehouse=warehouse,
                        quantity=quantity,
                    )
                except Exception as e:
                    bug_logger.warning(f"خطا در ایجاد target stock: {str(e)}")
                    continue
            
            # Stock entry همیشه uncommitted ایجاد می‌شود تا زمانی که resolve فشرده شود
            audit_logger.info(f"Stock entry {stock_entry.id} ایجاد شد (uncommitted) توسط مدیر {request.user.username}")
            bug_logger.info(f"Stock entry {stock_entry.id} ایجاد شد برای برنامه {program_id}")
            
            return JsonResponse({
                'success': True,
                'stock_entry_id': stock_entry.id,
                'message': 'ثبت انبار با موفقیت ایجاد شد (در انتظار تایید نهایی)'
            })
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد stock entry: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def manager_commit_stock_entry(request, program_id, entry_id):
    """
    Commit کردن stock entry و به‌روزرسانی actual_consumption
    این تابع دیگر استفاده نمی‌شود - همه commit ها از طریق resolve انجام می‌شود
    """
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=400)
    
    try:
        program = get_object_or_404(ProductionProgram, id=program_id)
        stock_entry = get_object_or_404(StockEntry, id=entry_id)
        
        if stock_entry.is_committed:
            return JsonResponse({'success': False, 'error': 'این ثبت قبلاً تایید شده است'}, status=400)
        
        with transaction.atomic():
            # Commit کردن stock entry
            stock_entry.commit()
            
            # به‌روزرسانی actual_consumption از تمام stock entries مربوط به برنامه
            stock_entries = StockEntry.objects.filter(
                Q(notes__icontains=f'برنامه {program.program_id}') |
                Q(notes__icontains=f'برنامه {program.id}') |
                Q(notes__icontains=f'program {program.program_id}') |
                Q(notes__icontains=f'program {program.id}')
            )
            
            actual_consumption = calculate_actual_consumption_from_stock_entries(program, stock_entries)
            program.actual_consumption = actual_consumption
            program.save(update_fields=['actual_consumption'])
            
            audit_logger.info(f"Stock entry {entry_id} commit شد و actual_consumption به‌روزرسانی شد توسط مدیر {request.user.username}")
            bug_logger.info(f"Stock entry {entry_id} commit شد برای برنامه {program_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'ثبت انبار با موفقیت تایید شد و جزئیات مواد اولیه به‌روزرسانی شد'
        })
        
    except Exception as e:
        bug_logger.error(f"خطا در commit stock entry {entry_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def manager_resolve_all(request, program_id):
    """
    Resolve کردن همه stock entries و به‌روزرسانی وضعیت برنامه
    - همه stock entries uncommitted را commit می‌کند
    - actual_consumption را به‌روزرسانی می‌کند
    - confirmed_by_warehouseman را True می‌کند
    - sent_to_manager_for_revalidation را False می‌کند
    """
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        audit_logger.alert(f"دسترسی غیرمجاز به resolve برنامه - برنامه {program_id}")
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=400)
    
    try:
        program = get_object_or_404(ProductionProgram, id=program_id)
        
        with transaction.atomic():
            # دریافت همه stock entries مربوط به برنامه که uncommitted هستند
            uncommitted_entries = StockEntry.objects.filter(
                (Q(notes__icontains=f'برنامه {program.program_id}') |
                 Q(notes__icontains=f'برنامه {program.id}') |
                 Q(notes__icontains=f'program {program.program_id}') |
                 Q(notes__icontains=f'program {program.id}')) &
                Q(is_committed=False)
            )
            
            # Commit کردن همه stock entries
            committed_count = 0
            for entry in uncommitted_entries:
                try:
                    entry.commit()
                    committed_count += 1
                    bug_logger.info(f"Stock entry {entry.id} commit شد در resolve")
                except Exception as e:
                    bug_logger.error(f"خطا در commit stock entry {entry.id}: {str(e)}")
                    continue
            
            # به‌روزرسانی actual_consumption از تمام stock entries مربوط به برنامه
            all_stock_entries = StockEntry.objects.filter(
                Q(notes__icontains=f'برنامه {program.program_id}') |
                Q(notes__icontains=f'برنامه {program.id}') |
                Q(notes__icontains=f'program {program.program_id}') |
                Q(notes__icontains=f'program {program.id}')
            )
            
            actual_consumption = calculate_actual_consumption_from_stock_entries(program, all_stock_entries)
            program.actual_consumption = actual_consumption
            
            # به‌روزرسانی وضعیت برنامه
            program.confirmed_by_warehouseman = True
            program.sent_to_manager_for_revalidation = False
            program.save(update_fields=['actual_consumption', 'confirmed_by_warehouseman', 'sent_to_manager_for_revalidation'])
            
            audit_logger.info(f"Resolve برنامه {program_id} انجام شد: {committed_count} stock entry commit شد توسط مدیر {request.user.username}")
            bug_logger.info(f"Resolve برنامه {program_id} انجام شد: {committed_count} stock entry commit شد")
        
        return JsonResponse({
            'success': True,
            'message': f'همه ثبت‌های انبار تایید شدند ({committed_count} مورد) و وضعیت برنامه به‌روزرسانی شد'
        })
        
    except Exception as e:
        bug_logger.error(f"خطا در resolve برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

