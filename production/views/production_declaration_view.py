from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template.loader import render_to_string
from django.db import transaction
from decimal import Decimal

import logging
from core.logging_levels import *

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
from production.forms.program_form import ProductionProgramForm
from production.forms.production_form import ProductionForm
import json

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


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
        
        with transaction.atomic():
            # دریافت content types
            raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
            product_ct = ContentType.objects.get_for_model(Product)
            
            if not production_program.production_info:
                bug_logger.error("برنامه تولید فاقد اطلاعات فرمول است")
                return None
            
            # پیدا کردن انبار تولید
            production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
            if not production_warehouse:
                bug_logger.error("انبار تولید یافت نشد")
                return None
            
            # مرحله 1: تصحیح برداشت واقعی
            # مقایسه warehouse_distribution (برنامه‌ریزی شده) با actual_consumption (واقعی)
            warehouse_distribution = production_program.warehouse_distribution or {}
            
            for bom in production_program.production_info.bom_items.all():
                bom_id_str = str(bom.id)
                
                if bom_id_str not in warehouse_distribution:
                    continue
                
                planned_dist = warehouse_distribution[bom_id_str]
                actual_dist = actual_consumption.get(bom_id_str, {})
                
                # برای هر انبار، تفاوت را محاسبه کن
                for planned_item in planned_dist:
                    warehouse_id = planned_item['warehouse']
                    planned_amount = Decimal(str(planned_item.get('amount', 0)))
                    actual_amount = Decimal(str(actual_dist.get(warehouse_id, 0)))
                    
                    difference = actual_amount - planned_amount
                    
                    if difference != 0:
                        # ایجاد ثبت انبار برای تصحیح
                        correction_entry = StockEntry.objects.create(
                            transaction_date=timezone.now(),
                            notes=f'تصحیح برداشت واقعی برنامه {production_program.program_id or production_program.id} - {bom.raw_material.name if bom.raw_material else "ماده اولیه"} - انبار {warehouse_id}',
                            is_committed=False
                        )
                        
                        try:
                            source_warehouse = Warehouse.objects.get(warehouse_id=warehouse_id)
                        except Warehouse.DoesNotExist:
                            bug_logger.error(f"انبار {warehouse_id} یافت نشد")
                            continue
                        
                        if difference > 0:
                            # برداشت بیشتر از برنامه - کاهش از انبار اولیه و افزایش به انبار تولید
                            bug_logger.info(f"تصحیح: {difference} تن بیشتر برداشت شده از {warehouse_id} برای {bom.raw_material.name if bom.raw_material else 'ماده اولیه'}")
                            
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
                            # برداشت کمتر از برنامه - برگشت به انبار اولیه
                            return_amount = abs(difference)
                            bug_logger.info(f"تصحیح: {return_amount} تن کمتر برداشت شده، برگشت به {warehouse_id} برای {bom.raw_material.name if bom.raw_material else 'ماده اولیه'}")
                            
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
                        bug_logger.info(f"ثبت انبار تصحیح {correction_entry.id} تأیید شد")
            
            # مرحله 2: تبدیل تمام مواد اولیه در انبار تولید به محصول نهایی
            # و انتقال به انبار محصول
            produced_weight = production_program.produced_weight_ton or Decimal('0')
            
            if produced_weight > 0 and production_program.product:
                completion_entry = StockEntry.objects.create(
                    transaction_date=timezone.now(),
                    notes=f'تکمیل تولید برنامه {production_program.program_id or production_program.id} - تبدیل مواد اولیه به محصول نهایی',
                    is_committed=False
                )
                
                # کاهش تمام مواد اولیه از انبار تولید (بر اساس مصرف واقعی کل)
                for bom in production_program.production_info.bom_items.all():
                    bom_id_str = str(bom.id)
                    actual_dist = actual_consumption.get(bom_id_str, {})
                    
                    # جمع کل برداشت واقعی از تمام انبارها
                    total_actual = sum(Decimal(str(amount)) for amount in actual_dist.values())
                    
                    if total_actual > 0:
                        SourceStock.objects.create(
                            stock_entry=completion_entry,
                            from_content_type=raw_material_ct,
                            from_object_id=bom.raw_material.id,
                            from_warehouse=production_warehouse,
                            quantity=total_actual,
                        )
                        bug_logger.debug(f"کاهش {total_actual} تن {bom.raw_material.name if bom.raw_material else 'ماده اولیه'} از انبار تولید")
                
                # افزایش محصول نهایی به انبار محصول
                TargetStock.objects.create(
                    stock_entry=completion_entry,
                    to_content_type=product_ct,
                    to_object_id=production_program.product.id,
                    to_warehouse=product_warehouse,
                    quantity=produced_weight,
                )
                bug_logger.info(f"افزایش {produced_weight} تن محصول {production_program.product.name} به انبار {product_warehouse.name}")
                
                completion_entry.commit()
                stock_entries.append(completion_entry)
                bug_logger.info(f"ثبت انبار تکمیل {completion_entry.id} تأیید شد")
            
            bug_logger.info(f"تکمیل موفقیت‌آمیز: {len(stock_entries)} ثبت انبار ایجاد شد")
            return stock_entries
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد ثبت‌های انبار تکمیل: {str(e)}")
        import traceback
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
        with transaction.atomic():
            # ایجاد ثبت انبار
            stock_entry = StockEntry.objects.create(
                transaction_date=timezone.now(),
                notes=f'شروع تولید برنامه {production_program.program_id or production_program.id} - انتقال مواد اولیه به انبار تولید',
                is_committed=False
            )
            
            bug_logger.info(f"ثبت انبار {stock_entry.id} برای شروع تولید ایجاد شد")
            
            # دریافت content type برای ماده اولیه
            raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
            
            # محاسبه مقدار مصرف کل برای هر ماده اولیه
            if not production_program.production_info:
                bug_logger.error("برنامه تولید فاقد اطلاعات فرمول است")
                return None
            
            # استفاده از انبار تولید از برنامه (اگر انتخاب شده باشد)
            production_warehouse = production_program.production_warehouse
            if not production_warehouse:
                # در صورت نبودن، اولین انبار تولید را استفاده کن
                production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
                if not production_warehouse:
                    bug_logger.error("انبار تولید یافت نشد")
                    return None
            
            # پردازش هر BOM item
            for bom in production_program.production_info.bom_items.all():
                bom_id_str = str(bom.id)
                
                # بررسی اینکه آیا توزیع برای این BOM موجود است
                if bom_id_str not in warehouse_distribution:
                    bug_logger.warning(f"توزیع انبار برای BOM {bom.id} یافت نشد")
                    continue
                
                bug_logger.debug(f"پردازش BOM {bom.id}: {bom.raw_material.name if bom.raw_material else 'نامشخص'}")
                
                # ایجاد SourceStock و TargetStock برای هر انبار (انتقال یک به یک)
                for dist in warehouse_distribution[bom_id_str]:
                    warehouse_identifier = dist['warehouse']
                    amount = Decimal(str(dist['amount']))
                    
                    bug_logger.debug(f"انتقال {amount} از انبار {warehouse_identifier} به انبار تولید")
                    
                    # پیدا کردن انبار اولیه - try warehouse_id, name, or id
                    source_warehouse = None
                    try:
                        # First try as warehouse_id (numeric string like "33", "22", "11")
                        source_warehouse = Warehouse.objects.get(warehouse_id=warehouse_identifier)
                        bug_logger.debug(f"انبار پیدا شد با warehouse_id: {warehouse_identifier}")
                    except Warehouse.DoesNotExist:
                        try:
                            # Then try as name (display name like "سیلو 1", "انبار زمینی")
                            source_warehouse = Warehouse.objects.get(name=warehouse_identifier)
                            bug_logger.debug(f"انبار پیدا شد با name: {warehouse_identifier}")
                        except Warehouse.DoesNotExist:
                            try:
                                # Finally try as primary key (integer id)
                                source_warehouse = Warehouse.objects.get(id=int(warehouse_identifier))
                                bug_logger.debug(f"انبار پیدا شد با id: {warehouse_identifier}")
                            except (Warehouse.DoesNotExist, ValueError):
                                bug_logger.error(f"انبار {warehouse_identifier} یافت نشد (warehouse_id، name یا id)")
                                continue
                    
                    if not source_warehouse:
                        bug_logger.error(f"انبار {warehouse_identifier} یافت نشد")
                        continue
                    
                    if amount > 0:
                        # ایجاد SourceStock (کاهش از انبار اولیه)
                        source_stock = SourceStock.objects.create(
                            stock_entry=stock_entry,
                            from_content_type=raw_material_ct,
                            from_object_id=bom.raw_material.id,
                            from_warehouse=source_warehouse,
                            quantity=amount,
                        )
                        bug_logger.debug(f"SourceStock ایجاد شد: {source_stock}")
                        
                        # ایجاد TargetStock (افزایش به انبار تولید - به عنوان ماده اولیه)
                        target_stock = TargetStock.objects.create(
                            stock_entry=stock_entry,
                            to_content_type=raw_material_ct,
                            to_object_id=bom.raw_material.id,
                            to_warehouse=production_warehouse,
                            quantity=amount,
                        )
                        bug_logger.debug(f"TargetStock به انبار تولید ایجاد شد: {target_stock}")
            
            # تأیید تراکنش
            stock_entry.commit()
            bug_logger.info(f"ثبت انبار {stock_entry.id} تأیید شد - مواد اولیه به انبار تولید منتقل شدند")
            
            return stock_entry
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد ثبت انبار شروع تولید: {str(e)}")
        import traceback
        bug_logger.error(traceback.format_exc())
        return None


def production_declaration_view(request):
    """
    صفحه اعلام تولید
    نمایش برنامه‌های تولید بر اساس وضعیت و موجودی مواد اولیه
    """
    audit_logger.info("دسترسی به صفحه اعلام تولید")
    bug_logger.debug("شروع بارگذاری صفحه اعلام تولید")
    
    try:
        # Get consolidated search parameters for each table
        search_confirmed = request.GET.get('search_confirmed', '').strip()
        search_progress = request.GET.get('search_progress', '').strip()
        search_completed = request.GET.get('search_completed', '').strip()
        
        # Get sort parameters for each table
        sort_by_confirmed = request.GET.get('sort_confirmed', 'execution_date')
        sort_dir_confirmed = request.GET.get('dir_confirmed', 'asc')
        
        sort_by_progress = request.GET.get('sort_progress', 'execution_date')
        sort_dir_progress = request.GET.get('dir_progress', 'asc')
        
        sort_by_completed = request.GET.get('sort_completed', 'execution_date')
        sort_dir_completed = request.GET.get('dir_completed', 'desc')
        
        # Validate sort columns
        allowed_sorts = ['id', 'program_id', 'execution_date', 'predicted_start_time', 'predicted_end_time', 'planned_weight_ton', 'status', 'started_at', 'completed_at']
        
        if sort_by_confirmed not in allowed_sorts:
            sort_by_confirmed = 'execution_date'
        if sort_by_progress not in allowed_sorts:
            sort_by_progress = 'execution_date'
        if sort_by_completed not in allowed_sorts:
            sort_by_completed = 'execution_date'
        
        # Build order_by strings
        order_by_confirmed = f'-{sort_by_confirmed}' if sort_dir_confirmed == 'desc' else sort_by_confirmed
        order_by_progress = f'-{sort_by_progress}' if sort_dir_progress == 'desc' else sort_by_progress
        order_by_completed = f'-{sort_by_completed}' if sort_dir_completed == 'desc' else sort_by_completed
        
        # دریافت برنامه‌های تولید بر اساس وضعیت
        try:
            confirmed_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.CONFIRMED
            ).select_related('product', 'production_info')
            
            # Apply consolidated search filter for confirmed table
            if search_confirmed:
                confirmed_programs = confirmed_programs.filter(
                    Q(id__icontains=search_confirmed) | 
                    Q(product__name__icontains=search_confirmed)
                )
            
            # Apply sorting for confirmed table
            confirmed_programs = confirmed_programs.order_by(order_by_confirmed, 'id')
            bug_logger.debug(f"تعداد برنامه‌های تایید شده: {confirmed_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"خطا در بارگذاری برنامه‌های تایید شده: {str(e)}")
            confirmed_programs = ProductionProgram.objects.none()
        
        try:
            in_progress_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.IN_PROGRESS
            ).select_related('product', 'production_info')
            
            # Apply consolidated search filter for in-progress table
            if search_progress:
                in_progress_programs = in_progress_programs.filter(
                    Q(id__icontains=search_progress) | 
                    Q(product__name__icontains=search_progress)
                )
            
            # Apply sorting for in-progress table
            in_progress_programs = in_progress_programs.order_by(order_by_progress, 'id')
            bug_logger.debug(f"تعداد برنامه‌های در حال اجرا: {in_progress_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"خطا در بارگذاری برنامه‌های در حال اجرا: {str(e)}")
            in_progress_programs = ProductionProgram.objects.none()
        
        # Pagination for completed programs
        try:
            completed_programs_qs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.COMPLETED
            ).select_related('product', 'production_info')
            
            # Apply consolidated search filter for completed table
            if search_completed:
                completed_programs_qs = completed_programs_qs.filter(
                    Q(id__icontains=search_completed) | 
                    Q(product__name__icontains=search_completed)
                )
            
            # Apply sorting for completed table
            completed_programs_qs = completed_programs_qs.order_by(order_by_completed, 'id')
            
            bug_logger.debug(f"تعداد کل برنامه‌های تکمیل شده: {completed_programs_qs.count()}")
            
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
            bug_logger.warning(f"خطا در بارگذاری برنامه‌های تکمیل شده: {str(e)}")
            completed_page = Paginator(ProductionProgram.objects.none(), 10).page(1)
        
        # دریافت موجودی مواد اولیه از انبارهای اولیه
        raw_materials_inventory = []
        try:
            # پیدا کردن انبارهای اولیه
            primary_warehouses = Warehouse.objects.filter(warehouse_type='primary')
            bug_logger.debug(f"تعداد انبارهای اولیه: {primary_warehouses.count()}")
            
            if primary_warehouses.exists():
                # دریافت content type برای RawMaterial
                try:
                    raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
                    
                    # دریافت آیتم‌های موجودی که ماده اولیه هستند
                    inventory_items = InventoryItem.objects.filter(
                        warehouse__in=primary_warehouses,
                        content_type=raw_material_ct
                    ).select_related('warehouse', 'content_type')
                    
                    bug_logger.debug(f"تعداد آیتم‌های موجودی مواد اولیه: {inventory_items.count()}")
                    
                    # گروه‌بندی مواد اولیه بر اساس ID و جمع موجودی از انبارها
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
                                bug_logger.warning(f"ماده اولیه با شناسه {item.object_id} یافت نشد")
                                continue
                            
                            if raw_material:
                                rm_id = getattr(raw_material, 'raw_material_id', '-')
                                quantity = item.quantity if item.quantity else Decimal('0')
                                
                                # جمع کردن موجودی کل
                                raw_materials_grouped[rm_id]['raw_material_id'] = rm_id
                                raw_materials_grouped[rm_id]['name'] = getattr(raw_material, 'name', '-')
                                raw_materials_grouped[rm_id]['total_quantity'] += quantity
                                raw_materials_grouped[rm_id]['unit'] = item.unit or 'تن'
                                
                                # ذخیره جزئیات انبار
                                raw_materials_grouped[rm_id]['warehouses'].append({
                                    'warehouse_id': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'warehouse_name': item.warehouse.name if (item.warehouse and item.warehouse.name) else (str(item.warehouse) if item.warehouse else '-'),
                                    'quantity': str(quantity),
                                })
                        except Exception as e:
                            bug_logger.warning(f"خطا در بارگذاری ماده اولیه: {str(e)}")
                            continue
                    
                    # تبدیل به لیست
                    for rm_id, data in raw_materials_grouped.items():
                        raw_materials_inventory.append({
                            'raw_material_id': data['raw_material_id'],
                            'name': data['name'],
                            'total_quantity': str(data['total_quantity']),
                            'unit': data['unit'],
                            'warehouses': data['warehouses']
                        })
                    
                    bug_logger.debug(f"تعداد مواد اولیه پردازش شده: {len(raw_materials_inventory)}")
                    
                except ContentType.DoesNotExist:
                    bug_logger.warning("ContentType برای RawMaterial یافت نشد")
                except Exception as e:
                    bug_logger.warning(f"خطا در دریافت موجودی مواد اولیه: {str(e)}")
            else:
                bug_logger.info("هیچ انبار اولیه‌ای یافت نشد")
        
        except Exception as e:
            bug_logger.error(f"خطای کلی در دریافت موجودی مواد اولیه: {str(e)}")
        
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
        }
        
        bug_logger.info("صفحه اعلام تولید با موفقیت بارگذاری شد")
        
        # Handle AJAX requests for pagination/filtering
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            table_type = request.GET.get('table', 'completed')
            
            if table_type == 'confirmed':
                programs_html = render_to_string(
                    'production/_confirmed_programs_tbody.html',
                    {'confirmed_programs': confirmed_programs},
                    request=request
                )
                return JsonResponse({
                    'programs_html': programs_html,
                    'total_count': confirmed_programs.count()
                })
            elif table_type == 'progress':
                programs_html = render_to_string(
                    'production/_progress_programs_tbody.html',
                    {'in_progress_programs': in_progress_programs},
                    request=request
                )
                return JsonResponse({
                    'programs_html': programs_html,
                    'total_count': in_progress_programs.count()
                })
            else:  # completed
                programs_html = render_to_string(
                    'production/_completed_programs_tbody.html',
                    {'completed_page': completed_page},
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
        bug_logger.error(f"خطای کلی در بارگذاری صفحه اعلام تولید: {str(e)}")
        audit_logger.alert("خطای کلی در دسترسی به صفحه اعلام تولید")
        
        # بازگشت صفحه خالی در صورت خطا
        context = {
            'confirmed_programs': ProductionProgram.objects.none(),
            'in_progress_programs': ProductionProgram.objects.none(),
            'completed_page': Paginator(ProductionProgram.objects.none(), 10).page(1),
            'raw_materials_inventory': [],
            'raw_materials_inventory_json': json.dumps([]),
        }
        return render(request, 'production_declaration.html', context)


def production_program_crud_view(request, program_id=None):
    """
    صفحه ساخت/ویرایش برنامه تولید
    نمایش و ویرایش تمام جزئیات یک برنامه تولید به همراه موجودی مواد اولیه
    اگر program_id نباشد، حالت ساخت جدید
    """
    is_create = program_id is None
    
    if is_create:
        audit_logger.info("دسترسی به صفحه ایجاد برنامه تولید جدید")
        bug_logger.debug("شروع بارگذاری صفحه ایجاد برنامه تولید")
        program = None
    else:
        audit_logger.info(f"دسترسی به جزئیات برنامه تولید {program_id}")
        bug_logger.debug(f"شروع بارگذاری جزئیات برنامه {program_id}")
    
    try:
        # دریافت برنامه تولید (اگر ویرایش)
        if not is_create:
            try:
                program = get_object_or_404(
                    ProductionProgram.objects.select_related('product', 'production_info'),
                    id=program_id
                )
                bug_logger.debug(f"برنامه تولید {program_id} با موفقیت بارگذاری شد")
            except Exception as e:
                bug_logger.error(f"خطا در بارگذاری برنامه تولید {program_id}: {str(e)}")
                audit_logger.activity(f"تلاش برای دسترسی به برنامه تولید نامعتبر {program_id}")
                raise
        
        # پردازش فرم
        if request.method == 'POST':
            action = request.POST.get('action', 'save')
            
            if is_create:
                form = ProductionForm(request.POST)
                audit_logger.info("ارسال فرم ایجاد برنامه تولید جدید")
            else:
                form = ProductionForm(request.POST, instance=program)
                audit_logger.info(f"ارسال فرم ویرایش برنامه تولید {program_id}")
            
            if form.is_valid():
                try:
                    instance = form.save(commit=False)
                    
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
                            bug_logger.info(f"تاریخ شروع واقعی از popup دریافت شد: {instance.actual_start_date}")
                        
                        # Set started_at (time only)
                        if started_at_str:
                            instance.started_at = started_at_str
                            bug_logger.info(f"زمان شروع واقعی از popup دریافت شد: {instance.started_at}")
                        else:
                            from datetime import datetime
                            instance.started_at = timezone.now().time()
                            bug_logger.info(f"زمان شروع واقعی به زمان فعلی تنظیم شد")
                        
                        # Set production warehouse
                        if production_warehouse_id:
                            try:
                                instance.production_warehouse = Warehouse.objects.get(id=production_warehouse_id)
                                bug_logger.info(f"انبار تولید: {instance.production_warehouse.name}")
                            except Warehouse.DoesNotExist:
                                bug_logger.error(f"انبار تولید با شناسه {production_warehouse_id} یافت نشد")
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
                                        bug_logger.warning(f"خطا در تبدیل مقدار برای BOM {bom_id}: {str(e)}")
                        
                        bug_logger.info(f"توزیع انبار دریافت شد: {len(clean_distribution)} BOM item")
                        
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
                            bug_logger.debug(f"توزیع انبار با مقادیر ذخیره شد: {warehouse_dist_with_amounts}")
                        
                        # Create stock entry if we have distribution data
                        if clean_distribution:
                            stock_entry = create_production_stock_entry(instance, clean_distribution, request)
                            if stock_entry:
                                bug_logger.info(f"ثبت انبار {stock_entry.id} برای برنامه {instance.id} ایجاد و تأیید شد")
                                messages.success(request, f'ثبت انبار با موفقیت ایجاد شد (شناسه: {stock_entry.id})')
                            else:
                                bug_logger.error(f"خطا در ایجاد ثبت انبار برای برنامه {instance.id}")
                                messages.warning(request, 'خطا در ایجاد ثبت انبار')
                        else:
                            bug_logger.warning("داده توزیع انبار دریافت نشد")
                    elif action == 'complete':
                        instance.status = ProductionProgram.Status.COMPLETED
                        # Handle popup data for complete action
                        produced_weight_str = request.POST.get('produced_weight_ton')
                        completed_at_str = request.POST.get('completed_at')
                        product_warehouse_id = request.POST.get('product_warehouse')
                        
                        if produced_weight_str:
                            try:
                                instance.produced_weight_ton = Decimal(produced_weight_str)
                                bug_logger.info(f"وزن تولید شده از popup دریافت شد: {instance.produced_weight_ton}")
                            except (ValueError, TypeError) as e:
                                bug_logger.warning(f"خطا در تبدیل وزن تولید شده: {str(e)}")
                        
                        # Set completed_at (time only)
                        if completed_at_str:
                            instance.completed_at = completed_at_str
                            bug_logger.info(f"زمان تکمیل از popup دریافت شد: {instance.completed_at}")
                        else:
                            from datetime import datetime
                            instance.completed_at = timezone.now().time()
                            bug_logger.info(f"زمان تکمیل به زمان فعلی تنظیم شد")
                        
                        # Set product warehouse
                        if product_warehouse_id:
                            try:
                                instance.product_warehouse = Warehouse.objects.get(id=product_warehouse_id)
                                bug_logger.info(f"انبار محصول نهایی: {instance.product_warehouse.name}")
                            except Warehouse.DoesNotExist:
                                bug_logger.error(f"انبار با شناسه {product_warehouse_id} یافت نشد")
                                messages.error(request, 'انبار محصول نهایی نامعتبر است')
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
                                            bug_logger.debug(f"مصرف واقعی BOM {bom_id} از انبار {warehouse}: {amount}")
                                        except (ValueError, TypeError) as e:
                                            bug_logger.warning(f"خطا در تبدیل مصرف واقعی BOM {bom_id}, warehouse {warehouse}: {str(e)}")
                        
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
                                bug_logger.warning(f"تکمیل رد شد: مصرف واقعی برای {len(missing_consumption)} ماده اولیه وارد نشده است")
                                messages.error(request, f'لطفاً مقدار مصرف واقعی را برای تمام مواد اولیه وارد کنید. موارد ناقص: {", ".join(missing_consumption)}')
                                # Don't save and return to form
                                warehouse_dist_data = program.warehouse_distribution if program and program.warehouse_distribution else {}
                                available_warehouses = Warehouse.objects.exclude(
                                    warehouse_type__in=['supplier', 'production']
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
                        
                        instance.actual_consumption = actual_consumption
                        bug_logger.info(f"داده‌های مصرف واقعی (انبار-محور) ذخیره شد: {len(actual_consumption)} BOM آیتم")
                        
                        # Create completion stock entries (corrections + final product transfer)
                        if instance.product_warehouse and actual_consumption:
                            stock_entries = create_completion_stock_entries(
                                instance, 
                                actual_consumption, 
                                instance.product_warehouse, 
                                request
                            )
                            if stock_entries:
                                bug_logger.info(f"{len(stock_entries)} ثبت انبار برای تکمیل تولید ایجاد شد")
                                messages.success(request, f'تکمیل تولید با موفقیت انجام شد. {len(stock_entries)} ثبت انبار ایجاد شد.')
                            else:
                                bug_logger.error("خطا در ایجاد ثبت‌های انبار تکمیل")
                                messages.warning(request, 'برنامه تکمیل شد اما خطا در ایجاد ثبت‌های انبار رخ داد')
                        else:
                            bug_logger.warning("انبار محصول یا مصرف واقعی موجود نیست - ثبت انبار ایجاد نشد")
                    
                    instance.save()
                    
                    if is_create:
                        bug_logger.info(f"برنامه تولید جدید با شناسه {instance.id} ایجاد شد")
                        messages.success(request, f'برنامه تولید با موفقیت ایجاد شد.')
                    else:
                        bug_logger.info(f"برنامه تولید {program_id} با موفقیت ویرایش شد")
                        messages.success(request, f'برنامه تولید با موفقیت ذخیره شد.')
                    
                    return redirect(reverse('production:program_crud', args=[instance.id]))
                    
                except Exception as e:
                    bug_logger.error(f"خطا در ذخیره برنامه تولید: {str(e)}")
                    messages.error(request, f'خطا در ذخیره برنامه تولید: {str(e)}')
            else:
                bug_logger.warning(f"فرم برنامه تولید نامعتبر است: {form.errors}")
                messages.error(request, 'لطفاً خطاهای فرم را بررسی کنید.')
        else:
            # GET request
            if is_create:
                form = ProductionForm()
            else:
                form = ProductionForm(instance=program)
        
        # دریافت موجودی مواد اولیه از انبارهای اولیه
        raw_materials_inventory = []
        try:
            primary_warehouses = Warehouse.objects.filter(warehouse_type='primary')
            bug_logger.debug(f"تعداد انبارهای اولیه: {primary_warehouses.count()}")
            
            if primary_warehouses.exists():
                try:
                    raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
                    
                    inventory_items = InventoryItem.objects.filter(
                        warehouse__in=primary_warehouses,
                        content_type=raw_material_ct
                    ).select_related('warehouse', 'content_type')
                    
                    bug_logger.debug(f"تعداد آیتم‌های موجودی: {inventory_items.count()}")
                    
                    # گروه‌بندی مواد اولیه بر اساس ID و جمع موجودی از انبارها
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
                                bug_logger.warning(f"ماده اولیه با شناسه {item.object_id} یافت نشد")
                                continue
                            
                            if raw_material:
                                rm_id = getattr(raw_material, 'raw_material_id', '-')
                                quantity = item.quantity if item.quantity else Decimal('0')
                                
                                # جمع کردن موجودی کل
                                raw_materials_grouped[rm_id]['raw_material_id'] = rm_id
                                raw_materials_grouped[rm_id]['name'] = getattr(raw_material, 'name', '-')
                                raw_materials_grouped[rm_id]['total_quantity'] += quantity
                                raw_materials_grouped[rm_id]['unit'] = item.unit or 'تن'
                                
                                # ذخیره جزئیات انبار
                                raw_materials_grouped[rm_id]['warehouses'].append({
                                    'warehouse_id': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'warehouse_name': item.warehouse.name if (item.warehouse and item.warehouse.name) else (str(item.warehouse) if item.warehouse else '-'),
                                    'quantity': str(quantity),
                                })
                        except Exception as e:
                            bug_logger.warning(f"خطا در بارگذاری ماده اولیه: {str(e)}")
                            continue
                    
                    # تبدیل به لیست
                    for rm_id, data in raw_materials_grouped.items():
                        raw_materials_inventory.append({
                            'raw_material_id': data['raw_material_id'],
                            'name': data['name'],
                            'total_quantity': str(data['total_quantity']),
                            'unit': data['unit'],
                            'warehouses': data['warehouses']
                        })
                    
                except ContentType.DoesNotExist:
                    bug_logger.warning("ContentType برای RawMaterial یافت نشد")
                except Exception as e:
                    bug_logger.warning(f"خطا در دریافت موجودی مواد اولیه: {str(e)}")
            else:
                bug_logger.info("هیچ انبار اولیه‌ای یافت نشد")
        
        except Exception as e:
            bug_logger.error(f"خطای کلی در دریافت موجودی مواد اولیه: {str(e)}")
        
        # Prepare production info and BOM data for JavaScript
        production_infos_data = {}
        bom_data = {}
        
        # Get actual consumption data if editing existing program
        actual_consumption_data = {}
        if not is_create and program:
            actual_consumption_data = program.actual_consumption or {}
        
        try:
            all_production_infos = ProductionInfo.objects.all().select_related('product').prefetch_related('bom_items')
            for prod_info in all_production_infos:
                product_id = prod_info.product.id if prod_info.product else None
                if product_id:
                    if product_id not in production_infos_data:
                        production_infos_data[product_id] = []
                    
                    production_infos_data[product_id].append({
                        'id': prod_info.id,
                        'program_id': prod_info.formula_id or '',
                        'min_batch_production': str(prod_info.min_batch_production) if prod_info.min_batch_production else '',
                        'specific_production_instruction': prod_info.specific_production_instruction or '',
                    })
                    
                    # Prepare BOM data
                    bom_items = []
                    for bom in prod_info.bom_items.all():
                        # Get actual consumption for this BOM item if exists
                        bom_id_str = str(bom.id)
                        actual_consumption = actual_consumption_data.get(bom_id_str, '')
                        
                        # Convert Decimal to string if needed
                        if actual_consumption and hasattr(actual_consumption, '__float__'):
                            actual_consumption = str(actual_consumption)
                        
                        bom_items.append({
                            'id': bom.id,
                            'raw_material_id': bom.raw_material.raw_material_id if bom.raw_material else '-',
                            'raw_material_name': bom.raw_material.name if bom.raw_material else '-',
                            'quantity': str(bom.quantity) if bom.quantity else '0',
                            'unit_used': bom.raw_material.primary_unit if (bom.raw_material and bom.raw_material.primary_unit) else '-',
                            'actual_consumption': str(actual_consumption) if actual_consumption else '',
                        })
                    
                    bom_data[prod_info.id] = {
                        'program_id': prod_info.formula_id or '',
                        'min_batch_production': str(prod_info.min_batch_production) if prod_info.min_batch_production else '',
                        'specific_production_instruction': prod_info.specific_production_instruction or '',
                        'bom_items': bom_items
                    }
        except Exception as e:
            bug_logger.error(f"خطا در آماده‌سازی داده‌های BOM: {str(e)}")
        
        # Get warehouse distribution if exists
        warehouse_distribution_data = {}
        if program and program.warehouse_distribution:
            warehouse_distribution_data = program.warehouse_distribution
        
        # Prepare actual consumption JSON
        actual_consumption_data = {}
        if program and program.actual_consumption:
            actual_consumption_data = program.actual_consumption
        
        # Get available warehouses for product warehouse selection
        # Filter to non-supplier, non-production warehouses (secondary, primary, consumer)
        available_warehouses = Warehouse.objects.exclude(
            warehouse_type__in=['supplier', 'production']
        ).order_by('name')
        
        # Get production warehouses
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
            'warehouse_distribution_json': json.dumps(warehouse_distribution_data),
            'actual_consumption_json': json.dumps(actual_consumption_data),
            'program_status': program.status if program else 'draft',
            'warehouses': available_warehouses,
            'production_warehouses': production_warehouses,
        }
        
        if is_create:
            bug_logger.info("صفحه ایجاد برنامه تولید با موفقیت بارگذاری شد")
        else:
            bug_logger.info(f"صفحه جزئیات برنامه {program_id} با موفقیت بارگذاری شد")
        
        return render(request, 'production_declaration_crud.html', context)
    
    except Exception as e:
        bug_logger.error(f"خطای کلی در بارگذاری صفحه: {str(e)}")
        audit_logger.alert(f"خطای کلی در دسترسی به صفحه برنامه تولید")
        
        available_warehouses = Warehouse.objects.exclude(
            warehouse_type__in=['supplier', 'production']
        ).order_by('name')
        production_warehouses = Warehouse.objects.filter(
            warehouse_type='production'
        ).order_by('name')
        
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
        }
        return render(request, 'production_declaration_crud.html', context)
