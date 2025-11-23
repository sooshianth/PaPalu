from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction
from decimal import Decimal
from django.utils import timezone

import logging
import traceback
import json
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


@login_required
def manager_resolve_program(request, program_id):
    """
    صفحه حل مشکلات تولید توسط مدیر
    مدیر می‌تواند همه چیز را ویرایش کند، stock entry ایجاد کند و برنامه را تایید نهایی کند
    """
    # بررسی دسترسی task - فقط مدیر با تسک PRODUCTION_MANAGER_SOLVE_ISSUES
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        audit_logger.alert(f"دسترسی غیرمجاز به حل مشکلات تولید - برنامه {program_id} - کاربر {request.user.username}")
        return HttpResponseForbidden("شما اجازه دسترسی به این صفحه را ندارید.")
    
    audit_logger.info(f"دسترسی مدیر به حل مشکلات برنامه {program_id} - کاربر {request.user.username}")
    
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
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'save':
                return handle_save_program(request, program)
            elif action == 'confirm':
                return handle_confirm_program(request, program)
            else:
                messages.error(request, "عملیات نامعتبر")
                return redirect('production:manager_resolve_program', program_id=program_id)
        
        # GET request - نمایش صفحه
        # دریافت ثبت‌های انبار مرتبط
        stock_entries = StockEntry.objects.filter(
            Q(notes__icontains=f'برنامه {program.program_id}') |
            Q(notes__icontains=f'برنامه {program.id}')
        ).order_by('-transaction_date')
        
        # دریافت موجودی فعلی انبارها
        warehouses = Warehouse.objects.filter(
            warehouse_type__in=['primary', 'production', 'secondary']
        ).prefetch_related('inventory_items')
        
        warehouse_inventories = {}
        for warehouse in warehouses:
            inventory_items = warehouse.inventory_items.all()
            warehouse_inventories[warehouse.id] = {
                'warehouse': warehouse,
                'items': inventory_items
            }
        
        # دریافت BOM items و actual consumption
        bom_items_data = []
        if program.production_info:
            bom_items = program.production_info.bom_items.all()
            actual_consumption = program.actual_consumption or {}
            
            for bom_item in bom_items:
                bom_id_str = str(bom_item.id)
                bom_quantity = bom_item.quantity or Decimal('0')
                required_quantity = bom_quantity * (program.produced_weight_ton or Decimal('0'))
                
                # محاسبه برداشت واقعی
                actual_dist = actual_consumption.get(bom_id_str, {})
                total_actual = sum(Decimal(str(amount)) for amount in actual_dist.values())
                
                variance = total_actual - required_quantity
                variance_percent = (variance / required_quantity * 100) if required_quantity > 0 else Decimal('0')
                
                bom_items_data.append({
                    'bom_item': bom_item,
                    'required_quantity': required_quantity,
                    'actual_quantity': total_actual,
                    'variance': variance,
                    'variance_percent': variance_percent,
                })
        
        # دریافت لیست همه مواد اولیه و محصولات برای فرم‌ها
        all_raw_materials = RawMaterial.objects.all()
        all_products = Product.objects.all()
        all_warehouses = Warehouse.objects.all()
        
        # آماده‌سازی داده‌های actual consumption برای JavaScript
        actual_consumption_json = json.dumps(program.actual_consumption or {})
        
        context = {
            'program': program,
            'stock_entries': stock_entries,
            'warehouse_inventories': warehouse_inventories,
            'bom_items_data': bom_items_data,
            'all_raw_materials': all_raw_materials,
            'all_products': all_products,
            'all_warehouses': all_warehouses,
            'actual_consumption_json': actual_consumption_json,
        }
        
        bug_logger.info(f"صفحه حل مشکلات برنامه {program_id} با موفقیت بارگذاری شد")
        return render(request, 'manager_resolve_program.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در بارگذاری صفحه حل مشکلات برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, "خطا در بارگذاری صفحه")
        return redirect('production:warehouse_production_list')


def handle_save_program(request, program):
    """ذخیره تغییرات برنامه بدون تایید نهایی"""
    try:
        with transaction.atomic():
            # بروزرسانی فیلدهای برنامه
            program.produced_weight_ton = Decimal(request.POST.get('produced_weight_ton', 0))
            program.planned_weight_ton = Decimal(request.POST.get('planned_weight_ton', 0))
            
            # بروزرسانی actual_consumption
            actual_consumption_str = request.POST.get('actual_consumption', '{}')
            try:
                actual_consumption = json.loads(actual_consumption_str)
                program.actual_consumption = actual_consumption
            except json.JSONDecodeError:
                bug_logger.error(f"خطا در پارس کردن actual_consumption: {actual_consumption_str}")
            
            # سایر فیلدهای قابل ویرایش
            if request.POST.get('execution_date'):
                program.execution_date = request.POST.get('execution_date')
            if request.POST.get('started_at'):
                program.started_at = request.POST.get('started_at')
            if request.POST.get('completed_at'):
                program.completed_at = request.POST.get('completed_at')
            if request.POST.get('packaging_type'):
                program.packaging_type = request.POST.get('packaging_type')
            
            program.save()
            
            audit_logger.info(f"ذخیره تغییرات برنامه {program.id} توسط مدیر {request.user.username}")
            messages.success(request, "تغییرات با موفقیت ذخیره شد")
            
    except Exception as e:
        bug_logger.error(f"خطا در ذخیره برنامه {program.id}: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, f"خطا در ذخیره تغییرات: {str(e)}")
    
    return redirect('production:manager_resolve_program', program_id=program.id)


def handle_confirm_program(request, program):
    """تایید نهایی و بازگرداندن به وضعیت تایید شده انبار"""
    try:
        with transaction.atomic():
            # ابتدا تغییرات را ذخیره کن
            handle_save_program(request, program)
            
            # سپس وضعیت را تغییر بده
            program.sent_to_manager_for_revalidation = False
            program.confirmed_by_warehouseman = True
            program.reason_for_warehouse_disapprove = None
            program.save()
            
            audit_logger.info(f"تایید نهایی برنامه {program.id} توسط مدیر {request.user.username}")
            messages.success(request, "برنامه تولید با موفقیت تایید و بازگردانده شد")
            
    except Exception as e:
        bug_logger.error(f"خطا در تایید نهایی برنامه {program.id}: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, f"خطا در تایید نهایی: {str(e)}")
        return redirect('production:manager_resolve_program', program_id=program.id)
    
    return redirect('production:warehouse_production_list')


@login_required
def manager_create_stock_entry(request, program_id):
    """
    ایجاد stock entry جدید توسط مدیر
    API endpoint برای AJAX
    """
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=400)
    
    try:
        program = get_object_or_404(ProductionProgram, id=program_id)
        
        with transaction.atomic():
            # ایجاد stock entry
            notes = request.POST.get('notes', '')
            stock_entry = StockEntry.objects.create(
                transaction_date=timezone.now(),
                notes=notes or f'تصحیح دستی توسط مدیر - برنامه {program.program_id or program.id}',
                is_committed=False
            )
            
            # پردازش source stocks
            source_stocks_data = json.loads(request.POST.get('source_stocks', '[]'))
            for source_data in source_stocks_data:
                item_type = source_data.get('item_type')  # 'raw_material' or 'product'
                item_id = source_data.get('item_id')
                warehouse_id = source_data.get('warehouse_id')
                quantity = Decimal(str(source_data.get('quantity', 0)))
                
                if quantity <= 0:
                    continue
                
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
            
            # پردازش target stocks
            target_stocks_data = json.loads(request.POST.get('target_stocks', '[]'))
            for target_data in target_stocks_data:
                item_type = target_data.get('item_type')  # 'raw_material' or 'product'
                item_id = target_data.get('item_id')
                warehouse_id = target_data.get('warehouse_id')
                quantity = Decimal(str(target_data.get('quantity', 0)))
                
                if quantity <= 0:
                    continue
                
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
            
            # Commit the stock entry
            should_commit = request.POST.get('commit', 'false').lower() == 'true'
            if should_commit:
                stock_entry.commit()
                audit_logger.info(f"Stock entry {stock_entry.id} ایجاد و commit شد توسط مدیر {request.user.username}")
            else:
                audit_logger.info(f"Stock entry {stock_entry.id} ایجاد شد (uncommitted) توسط مدیر {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'stock_entry_id': stock_entry.id,
                'message': 'ثبت انبار با موفقیت ایجاد شد'
            })
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد stock entry: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def manager_delete_stock_entry(request, entry_id):
    """حذف stock entry (فقط uncommitted)"""
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=400)
    
    try:
        stock_entry = get_object_or_404(StockEntry, id=entry_id)
        
        if stock_entry.is_committed:
            return JsonResponse({'success': False, 'error': 'نمی‌توان ثبت تایید شده را حذف کرد'}, status=400)
        
        with transaction.atomic():
            stock_entry.delete()
            audit_logger.info(f"Stock entry {entry_id} حذف شد توسط مدیر {request.user.username}")
            
        return JsonResponse({'success': True, 'message': 'ثبت انبار با موفقیت حذف شد'})
        
    except Exception as e:
        bug_logger.error(f"خطا در حذف stock entry {entry_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def manager_commit_stock_entry(request, entry_id):
    """Commit کردن stock entry"""
    if not user_has_task(request.user, TaskChoices.PRODUCTION_MANAGER_SOLVE_ISSUES.value):
        return JsonResponse({'success': False, 'error': 'دسترسی غیرمجاز'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'متد نامعتبر'}, status=400)
    
    try:
        stock_entry = get_object_or_404(StockEntry, id=entry_id)
        
        if stock_entry.is_committed:
            return JsonResponse({'success': False, 'error': 'این ثبت قبلاً تایید شده است'}, status=400)
        
        with transaction.atomic():
            stock_entry.commit()
            audit_logger.info(f"Stock entry {entry_id} commit شد توسط مدیر {request.user.username}")
            
        return JsonResponse({'success': True, 'message': 'ثبت انبار با موفقیت تایید شد'})
        
    except Exception as e:
        bug_logger.error(f"خطا در commit stock entry {entry_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
