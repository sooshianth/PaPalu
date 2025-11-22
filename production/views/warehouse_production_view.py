from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from decimal import Decimal

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
    """بررسی دسترسی کاربر به فیلدهای ProductionProgram - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['id'] = user_can_access_field(user, ProductionProgram, 'id', 'view')
    accessible_fields['program_id'] = user_can_access_field(user, ProductionProgram, 'program_id', 'view')
    accessible_fields['execution_date'] = user_can_access_field(user, ProductionProgram, 'execution_date', 'view')
    accessible_fields['planned_weight_ton'] = user_can_access_field(user, ProductionProgram, 'planned_weight_ton', 'view')
    accessible_fields['produced_weight_ton'] = user_can_access_field(user, ProductionProgram, 'produced_weight_ton', 'view')
    accessible_fields['packaging_type'] = user_can_access_field(user, ProductionProgram, 'packaging_type', 'view')
    accessible_fields['predicted_start_time'] = user_can_access_field(user, ProductionProgram, 'predicted_start_time', 'view')
    accessible_fields['predicted_end_time'] = user_can_access_field(user, ProductionProgram, 'predicted_end_time', 'view')
    accessible_fields['started_at'] = user_can_access_field(user, ProductionProgram, 'started_at', 'view')
    accessible_fields['completed_at'] = user_can_access_field(user, ProductionProgram, 'completed_at', 'view')
    accessible_fields['status'] = user_can_access_field(user, ProductionProgram, 'status', 'view')
    accessible_fields['product'] = user_can_access_field(user, ProductionProgram, 'product', 'view')
    accessible_fields['product_warehouse'] = user_can_access_field(user, ProductionProgram, 'product_warehouse', 'view')
    accessible_fields['production_warehouse'] = user_can_access_field(user, ProductionProgram, 'production_warehouse', 'view')
    accessible_fields['production_info'] = user_can_access_field(user, ProductionProgram, 'production_info', 'view')
    accessible_fields['actual_consumption'] = user_can_access_field(user, ProductionProgram, 'actual_consumption', 'view')
    accessible_fields['confirmed_by_warehouseman'] = user_can_access_field(user, ProductionProgram, 'confirmed_by_warehouseman', 'view')
    accessible_fields['sent_to_manager_for_revalidation'] = user_can_access_field(user, ProductionProgram, 'sent_to_manager_for_revalidation', 'view')
    accessible_fields['reason_for_warehouse_disapprove'] = user_can_access_field(user, ProductionProgram, 'reason_for_warehouse_disapprove', 'view')
    accessible_fields['created_at'] = user_can_access_field(user, ProductionProgram, 'created_at', 'view')
    accessible_fields['fulfillment_percentage'] = user_can_access_field(user, ProductionProgram, 'fulfillment_percentage', 'view')
    
    return accessible_fields


def get_accessible_product_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Product - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['name'] = user_can_access_field(user, Product, 'name', 'view')
    accessible_fields['packaging_type'] = user_can_access_field(user, Product, 'packaging_type', 'view')
    return accessible_fields


def get_accessible_warehouse_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Warehouse - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['warehouse_id'] = user_can_access_field(user, Warehouse, 'warehouse_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, Warehouse, 'name', 'view')
    accessible_fields['warehouse_type'] = user_can_access_field(user, Warehouse, 'warehouse_type', 'view')
    return accessible_fields


def get_accessible_stock_entry_fields(user):
    """بررسی دسترسی کاربر به فیلدهای StockEntry - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['id'] = user_can_access_field(user, StockEntry, 'id', 'view')
    accessible_fields['transaction_date'] = user_can_access_field(user, StockEntry, 'transaction_date', 'view')
    accessible_fields['notes'] = user_can_access_field(user, StockEntry, 'notes', 'view')
    accessible_fields['is_committed'] = user_can_access_field(user, StockEntry, 'is_committed', 'view')
    return accessible_fields


def get_accessible_inventory_item_fields(user):
    """بررسی دسترسی کاربر به فیلدهای InventoryItem - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['warehouse'] = user_can_access_field(user, InventoryItem, 'warehouse', 'view')
    accessible_fields['quantity'] = user_can_access_field(user, InventoryItem, 'quantity', 'view')
    accessible_fields['item'] = user_can_access_field(user, InventoryItem, 'item', 'view')
    return accessible_fields


def get_accessible_raw_material_fields(user):
    """بررسی دسترسی کاربر به فیلدهای RawMaterial - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['raw_material_id'] = user_can_access_field(user, RawMaterial, 'raw_material_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, RawMaterial, 'name', 'view')
    return accessible_fields


@login_required
def warehouse_production_list(request):
    """
    لیست برنامه‌های تولید تکمیل شده برای تایید انبار
    نمایش دو لیست: تایید شده و تایید نشده
    """
    # بررسی دسترسی task
    if not user_has_task(request.user, TaskChoices.PRODUCTION_APPROVE_REPORT.value):
        audit_logger.alert(f"دسترسی غیرمجاز به لیست اظهار تولید (انبار)")
        return HttpResponseForbidden("شما اجازه دسترسی به این صفحه را ندارید.")
    
    audit_logger.info("دسترسی به لیست اظهار تولید (انبار)")
    
    try:
        # دریافت برنامه‌های تکمیل شده
        completed_programs = ProductionProgram.objects.filter(
            status=ProductionProgram.Status.COMPLETED
        ).select_related(
            'product', 
            'product_warehouse', 
            'production_warehouse',
            'production_info'
        ).order_by('-completed_at')
        
        # تفکیک به تایید شده و تایید نشده
        approved_programs = completed_programs.filter(confirmed_by_warehouseman=True)
        pending_programs = completed_programs.filter(
            confirmed_by_warehouseman=False,
            sent_to_manager_for_revalidation=False
        )
        disapproved_programs = completed_programs.filter(sent_to_manager_for_revalidation=True)
        
        # Pagination for pending
        pending_page = request.GET.get('pending_page', 1)
        pending_paginator = Paginator(pending_programs, 20)
        try:
            pending_programs_page = pending_paginator.page(pending_page)
        except PageNotAnInteger:
            pending_programs_page = pending_paginator.page(1)
        except EmptyPage:
            pending_programs_page = pending_paginator.page(pending_paginator.num_pages)
        
        # Pagination for approved
        approved_page = request.GET.get('approved_page', 1)
        approved_paginator = Paginator(approved_programs, 20)
        try:
            approved_programs_page = approved_paginator.page(approved_page)
        except PageNotAnInteger:
            approved_programs_page = approved_paginator.page(1)
        except EmptyPage:
            approved_programs_page = approved_paginator.page(approved_paginator.num_pages)
        
        # Pagination for disapproved
        disapproved_page = request.GET.get('disapproved_page', 1)
        disapproved_paginator = Paginator(disapproved_programs, 20)
        try:
            disapproved_programs_page = disapproved_paginator.page(disapproved_page)
        except PageNotAnInteger:
            disapproved_programs_page = disapproved_paginator.page(1)
        except EmptyPage:
            disapproved_programs_page = disapproved_paginator.page(disapproved_paginator.num_pages)
        
        # بررسی دسترسی فیلدها
        accessible_production_program_fields = get_accessible_production_program_fields(request.user)
        accessible_product_fields = get_accessible_product_fields(request.user)
        accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
        
        context = {
            'pending_programs': pending_programs_page,
            'approved_programs': approved_programs_page,
            'disapproved_programs': disapproved_programs_page,
            'accessible_production_program_fields': accessible_production_program_fields,
            'accessible_product_fields': accessible_product_fields,
            'accessible_warehouse_fields': accessible_warehouse_fields,
        }
        
        bug_logger.info(f"لیست اظهار تولید (انبار) با موفقیت بارگذاری شد - {pending_programs.count()} در انتظار، {approved_programs.count()} تایید شده")
        return render(request, 'warehouse_production_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در بارگذاری لیست اظهار تولید (انبار): {str(e)}\n{traceback.format_exc()}")
        messages.error(request, "خطا در بارگذاری لیست اظهار تولید")
        return redirect('production:production_declaration')


@login_required
def warehouse_production_detail(request, program_id):
    """
    نمایش جزئیات برنامه تولید برای بررسی و تایید انبار
    شامل: جزئیات برنامه، ثبت‌های انبار، وضعیت فعلی انبارها، قبل و بعد
    """
    # بررسی دسترسی task
    if not user_has_task(request.user, TaskChoices.PRODUCTION_APPROVE_REPORT.value):
        audit_logger.alert(f"دسترسی غیرمجاز به جزئیات اظهار تولید (انبار) - برنامه {program_id}")
        return HttpResponseForbidden("شما اجازه دسترسی به این صفحه را ندارید.")
    
    audit_logger.info(f"دسترسی به جزئیات اظهار تولید (انبار) - برنامه {program_id}")
    
    try:
        program = get_object_or_404(
            ProductionProgram.objects.select_related(
                'product',
                'product_warehouse',
                'production_warehouse',
                'production_info'
            ),
            id=program_id,
            status=ProductionProgram.Status.COMPLETED
        )
        
        # دریافت ثبت‌های انبار مرتبط با این برنامه
        # Find stock entries related to this program through notes or other means
        stock_entries = StockEntry.objects.filter(
            Q(notes__icontains=f'برنامه {program.program_id}') |
            Q(notes__icontains=f'برنامه {program.id}')
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
        
        # محاسبه قبل و بعد (با استفاده از stock entries)
        before_after_calculation = calculate_warehouse_before_after(program, stock_entries)
        
        # بررسی دسترسی فیلدها
        accessible_production_program_fields = get_accessible_production_program_fields(request.user)
        accessible_product_fields = get_accessible_product_fields(request.user)
        accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
        accessible_stock_entry_fields = get_accessible_stock_entry_fields(request.user)
        accessible_inventory_item_fields = get_accessible_inventory_item_fields(request.user)
        accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
        
        context = {
            'program': program,
            'stock_entries': stock_entries,
            'warehouse_inventories': warehouse_inventories,
            'before_after_calculation': before_after_calculation,
            'accessible_production_program_fields': accessible_production_program_fields,
            'accessible_product_fields': accessible_product_fields,
            'accessible_warehouse_fields': accessible_warehouse_fields,
            'accessible_stock_entry_fields': accessible_stock_entry_fields,
            'accessible_inventory_item_fields': accessible_inventory_item_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
        }
        
        bug_logger.info(f"جزئیات اظهار تولید (انبار) برنامه {program_id} با موفقیت بارگذاری شد")
        return render(request, 'warehouse_production_detail.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در بارگذاری جزئیات اظهار تولید (انبار) برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        messages.error(request, "خطا در بارگذاری جزئیات برنامه تولید")
        return redirect('production:warehouse_production_list')


@login_required
def warehouse_approve_program(request, program_id):
    """
    تایید برنامه تولید توسط انباردار
    """
    if request.method != 'POST':
        audit_logger.alert(f"درخواست غیرمجاز به تایید انبار - متد {request.method}")
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر'}, status=400)
    
    # بررسی دسترسی task
    if not user_has_task(request.user, TaskChoices.PRODUCTION_APPROVE_REPORT.value):
        audit_logger.alert(f"دسترسی غیرمجاز به تایید انبار - برنامه {program_id}")
        return JsonResponse({'success': False, 'message': 'شما اجازه انجام این عملیات را ندارید'}, status=403)
    
    audit_logger.info(f"درخواست تایید انبار برای برنامه {program_id}")
    
    try:
        program = get_object_or_404(
            ProductionProgram,
            id=program_id,
            status=ProductionProgram.Status.COMPLETED
        )
        
        if program.confirmed_by_warehouseman:
            return JsonResponse({'success': False, 'message': 'این برنامه قبلاً تایید شده است'}, status=400)
        
        with transaction.atomic():
            program.confirmed_by_warehouseman = True
            program.sent_to_manager_for_revalidation = False
            program.reason_for_warehouse_disapprove = None
            program.save(update_fields=[
                'confirmed_by_warehouseman',
                'sent_to_manager_for_revalidation',
                'reason_for_warehouse_disapprove'
            ])
        
        audit_logger.info(f"برنامه تولید {program_id} توسط انبار تایید شد")
        bug_logger.info(f"برنامه تولید {program_id} توسط انبار تایید شد")
        
        return JsonResponse({'success': True, 'message': 'برنامه تولید با موفقیت تایید شد'})
        
    except Exception as e:
        bug_logger.error(f"خطا در تایید انبار برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': 'خطا در تایید برنامه تولید'}, status=500)


@login_required
def warehouse_disapprove_program(request, program_id):
    """
    عدم تایید برنامه تولید توسط انباردار و ارسال به مدیر
    """
    if request.method != 'POST':
        audit_logger.alert(f"درخواست غیرمجاز به عدم تایید انبار - متد {request.method}")
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر'}, status=400)
    
    # بررسی دسترسی task
    if not user_has_task(request.user, TaskChoices.PRODUCTION_APPROVE_REPORT.value):
        audit_logger.alert(f"دسترسی غیرمجاز به عدم تایید انبار - برنامه {program_id}")
        return JsonResponse({'success': False, 'message': 'شما اجازه انجام این عملیات را ندارید'}, status=403)
    
    reason = request.POST.get('reason', '').strip()
    
    if not reason:
        return JsonResponse({'success': False, 'message': 'لطفاً دلیل عدم تایید را وارد کنید'}, status=400)
    
    audit_logger.info(f"درخواست عدم تایید انبار برای برنامه {program_id}")
    
    try:
        program = get_object_or_404(
            ProductionProgram,
            id=program_id,
            status=ProductionProgram.Status.COMPLETED
        )
        
        if program.confirmed_by_warehouseman:
            return JsonResponse({'success': False, 'message': 'این برنامه قبلاً تایید شده است'}, status=400)
        
        with transaction.atomic():
            program.confirmed_by_warehouseman = False
            program.sent_to_manager_for_revalidation = True
            program.reason_for_warehouse_disapprove = reason
            program.save(update_fields=[
                'confirmed_by_warehouseman',
                'sent_to_manager_for_revalidation',
                'reason_for_warehouse_disapprove'
            ])
        
        audit_logger.activity(f"برنامه تولید {program_id} توسط انبار رد شد و به مدیر ارسال شد")
        bug_logger.info(f"برنامه تولید {program_id} توسط انبار رد شد - دلیل: {reason[:50]}")
        
        return JsonResponse({'success': True, 'message': 'برنامه تولید برای بررسی مجدد به مدیر ارسال شد'})
        
    except Exception as e:
        bug_logger.error(f"خطا در عدم تایید انبار برنامه {program_id}: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'message': 'خطا در عدم تایید برنامه تولید'}, status=500)


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
            
            # محاسبه وضعیت قبل (موجودی فعلی قبل از اعمال تراکنش‌ها)
            current_inventory = InventoryItem.objects.filter(warehouse=warehouse)
            for item in current_inventory:
                item_key = f"{item.content_type.model}_{item.object_id}"
                before_after[warehouse.id]['after'][item_key] = {
                    'item': item.item,
                    'quantity': item.quantity,
                    'unit': item.unit,
                    'item_type': item.item_type
                }
            
            # محاسبه تغییرات از stock entries
            for entry in stock_entries:
                if not entry.is_committed:
                    continue
                
                # بررسی source stocks
                for source in entry.source_stocks.filter(from_warehouse=warehouse):
                    item_key = f"{source.from_content_type.model}_{source.from_object_id}"
                    change_amount = source.quantity or Decimal('0')
                    
                    before_after[warehouse.id]['changes'].append({
                        'type': 'source',
                        'item': source.from_item,
                        'amount': change_amount,
                        'date': entry.transaction_date
                    })
                    
                    # Add to before (reverse the change)
                    if item_key in before_after[warehouse.id]['after']:
                        current_qty = before_after[warehouse.id]['after'][item_key]['quantity'] or Decimal('0')
                        before_qty = current_qty + change_amount
                        before_after[warehouse.id]['before'][item_key] = {
                            'item': source.from_item,
                            'quantity': before_qty,
                            'unit': before_after[warehouse.id]['after'][item_key]['unit'],
                            'item_type': before_after[warehouse.id]['after'][item_key]['item_type']
                        }
                
                # بررسی target stocks
                for target in entry.target_stocks.filter(to_warehouse=warehouse):
                    item_key = f"{target.to_content_type.model}_{target.to_object_id}"
                    change_amount = target.quantity or Decimal('0')
                    
                    before_after[warehouse.id]['changes'].append({
                        'type': 'target',
                        'item': target.to_item,
                        'amount': change_amount,
                        'date': entry.transaction_date
                    })
                    
                    # Add to before (reverse the change)
                    if item_key in before_after[warehouse.id]['after']:
                        current_qty = before_after[warehouse.id]['after'][item_key]['quantity'] or Decimal('0')
                        before_qty = current_qty - change_amount
                        before_after[warehouse.id]['before'][item_key] = {
                            'item': target.to_item,
                            'quantity': before_qty,
                            'unit': before_after[warehouse.id]['after'][item_key]['unit'],
                            'item_type': before_after[warehouse.id]['after'][item_key]['item_type']
                        }
        
        return before_after
        
    except Exception as e:
        bug_logger.error(f"خطا در محاسبه قبل و بعد انبار: {str(e)}\n{traceback.format_exc()}")
        return {}
