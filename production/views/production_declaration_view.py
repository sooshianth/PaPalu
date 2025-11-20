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


def create_production_stock_entry(production_program, warehouse_distribution, request):
    """
    ایجاد ثبت انبار برای شروع تولید
    
    Args:
        production_program: برنامه تولید
        warehouse_distribution: دیکشنری توزیع انبارها {bom_id: [{warehouse: str, percent: int}, ...]}
        request: Django request object
    
    Returns:
        StockEntry object or None if failed
    """
    try:
        with transaction.atomic():
            # ایجاد ثبت انبار
            stock_entry = StockEntry.objects.create(
                transaction_date=timezone.now(),
                notes=f'شروع تولید برنامه {production_program.program_id or production_program.id}',
                is_committed=False
            )
            
            bug_logger.info(f"ثبت انبار {stock_entry.id} ایجاد شد")
            
            # دریافت content type برای ماده اولیه و محصول
            raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
            product_ct = ContentType.objects.get_for_model(Product)
            
            # محاسبه مقدار مصرف کل برای هر ماده اولیه
            if not production_program.production_info:
                bug_logger.error("برنامه تولید فاقد اطلاعات فرمول است")
                return None
            
            planned_weight = production_program.planned_weight_ton or Decimal('0')
            min_batch = production_program.production_info.min_batch_production or Decimal('1')
            
            # پردازش هر BOM item
            for bom in production_program.production_info.bom_items.all():
                bom_id_str = str(bom.id)
                
                # بررسی اینکه آیا توزیع برای این BOM موجود است
                if bom_id_str not in warehouse_distribution:
                    bug_logger.warning(f"توزیع انبار برای BOM {bom.id} یافت نشد")
                    continue
                
                bug_logger.debug(f"پردازش BOM {bom.id}: {bom.raw_material.name if bom.raw_material else 'نامشخص'}")
                
                # ایجاد SourceStock برای هر انبار
                for dist in warehouse_distribution[bom_id_str]:
                    warehouse_id = dist['warehouse']
                    
                    # Use the actual amount provided from frontend
                    amount = Decimal(str(dist['amount']))
                    
                    bug_logger.debug(f"برداشت {amount} از انبار {warehouse_id}")
                    
                    # پیدا کردن انبار
                    try:
                        warehouse = Warehouse.objects.get(warehouse_id=warehouse_id)
                    except Warehouse.DoesNotExist:
                        bug_logger.error(f"انبار {warehouse_id} یافت نشد")
                        continue
                    
                    # ایجاد SourceStock (کاهش از انبار اولیه)
                    if amount > 0:
                        source_stock = SourceStock.objects.create(
                            stock_entry=stock_entry,
                            from_content_type=raw_material_ct,
                            from_object_id=bom.raw_material.id,
                            from_warehouse=warehouse,
                            quantity=amount,
                            unit='ton'  # واحد پیش‌فرض
                        )
                        bug_logger.debug(f"SourceStock ایجاد شد: {source_stock}")
            
            # ایجاد TargetStock (افزایش به انبار تولید)
            # پیدا کردن انبار تولید
            try:
                production_warehouse = Warehouse.objects.filter(warehouse_type='production').first()
                if not production_warehouse:
                    bug_logger.warning("انبار تولید یافت نشد - ثبت انبار بدون TargetStock ایجاد می‌شود")
                else:
                    # افزودن محصول به انبار تولید
                    if production_program.product:
                        target_stock = TargetStock.objects.create(
                            stock_entry=stock_entry,
                            to_content_type=product_ct,
                            to_object_id=production_program.product.id,
                            to_warehouse=production_warehouse,
                            quantity=planned_weight,
                            unit='ton'
                        )
                        bug_logger.debug(f"TargetStock ایجاد شد: {target_stock}")
                
            except Exception as e:
                bug_logger.error(f"خطا در ایجاد TargetStock: {str(e)}")
            
            # تأیید تراکنش
            stock_entry.commit()
            bug_logger.info(f"ثبت انبار {stock_entry.id} تأیید شد")
            
            return stock_entry
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد ثبت انبار: {str(e)}")
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
                    
                    # ساخت لیست موجودی مواد اولیه
                    for item in inventory_items:
                        try:
                            raw_material = item.item  # Generic relation
                            if raw_material is None:
                                bug_logger.warning(f"ماده اولیه با شناسه {item.object_id} یافت نشد")
                                continue
                            
                            if raw_material:
                                raw_materials_inventory.append({
                                    'raw_material_id': getattr(raw_material, 'raw_material_id', '-'),
                                    'name': getattr(raw_material, 'name', '-'),
                                    'warehouse': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'quantity': str(item.quantity) if item.quantity else '0',
                                    'unit': item.unit or 'تن',
                                })
                        except Exception as e:
                            bug_logger.warning(f"خطا در بارگذاری ماده اولیه: {str(e)}")
                            continue
                    
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
                    
                    # Handle actual consumption data (for IN_PROGRESS and COMPLETED status)
                    if instance.status in [ProductionProgram.Status.IN_PROGRESS, ProductionProgram.Status.COMPLETED]:
                        actual_consumption = {}
                        # Collect actual consumption data from POST
                        for key, value in request.POST.items():
                            if key.startswith('actual_consumption_'):
                                bom_id = key.replace('actual_consumption_', '')
                                if value and value.strip():
                                    try:
                                        actual_consumption[bom_id] = str(Decimal(value))
                                        bug_logger.debug(f"مصرف واقعی BOM {bom_id}: {value}")
                                    except (ValueError, TypeError) as e:
                                        bug_logger.warning(f"خطا در تبدیل مصرف واقعی BOM {bom_id}: {str(e)}")
                        
                        # Validate that all BOM items have actual consumption when completing
                        if action == 'complete' and instance.production_info:
                            bom_items = instance.production_info.bom_items.all()
                            missing_consumption = []
                            for bom in bom_items:
                                bom_id_str = str(bom.id)
                                if bom_id_str not in actual_consumption or not actual_consumption[bom_id_str]:
                                    missing_consumption.append(bom.raw_material.name if bom.raw_material else f"BOM #{bom.id}")
                            
                            if missing_consumption:
                                bug_logger.warning(f"تکمیل رد شد: مصرف واقعی برای {len(missing_consumption)} ماده اولیه وارد نشده است")
                                messages.error(request, f'لطفاً مقدار مصرف واقعی را برای تمام مواد اولیه وارد کنید. موارد ناقص: {", ".join(missing_consumption)}')
                                # Don't save and return to form
                                warehouse_dist_data = program.warehouse_distribution if program and program.warehouse_distribution else {}
                                context = {
                                    'form': form,
                                    'program': program,
                                    'is_create': is_create,
                                    'raw_materials_inventory': raw_materials_inventory,
                                    'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
                                    'production_infos_json': json.dumps(production_infos_data),
                                    'bom_data_json': json.dumps(bom_data),
                                    'warehouse_distribution_json': json.dumps(warehouse_dist_data),
                                }
                                return render(request, 'production_declaration_crud.html', context)
                        
                        instance.actual_consumption = actual_consumption
                        bug_logger.info(f"داده‌های مصرف واقعی ذخیره شد: {len(actual_consumption)} آیتم")
                    
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
                    
                    for item in inventory_items:
                        try:
                            raw_material = item.item
                            if raw_material is None:
                                bug_logger.warning(f"ماده اولیه با شناسه {item.object_id} یافت نشد")
                                continue
                            
                            if raw_material:
                                raw_materials_inventory.append({
                                    'raw_material_id': getattr(raw_material, 'raw_material_id', '-'),
                                    'name': getattr(raw_material, 'name', '-'),
                                    'warehouse': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'quantity': str(item.quantity) if item.quantity else '0',
                                    'unit': item.unit or 'تن',
                                })
                        except Exception as e:
                            bug_logger.warning(f"خطا در بارگذاری ماده اولیه: {str(e)}")
                            continue
                    
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
        
        context = {
            'form': form,
            'program': program,
            'is_create': is_create,
            'raw_materials_inventory': raw_materials_inventory,
            'raw_materials_inventory_json': json.dumps(raw_materials_inventory),
            'production_infos_json': json.dumps(production_infos_data),
            'bom_data_json': json.dumps(bom_data),
            'warehouse_distribution_json': json.dumps(warehouse_distribution_data),
            'program_status': program.status if program else 'draft',
        }
        
        if is_create:
            bug_logger.info("صفحه ایجاد برنامه تولید با موفقیت بارگذاری شد")
        else:
            bug_logger.info(f"صفحه جزئیات برنامه {program_id} با موفقیت بارگذاری شد")
        
        return render(request, 'production_declaration_crud.html', context)
    
    except Exception as e:
        bug_logger.error(f"خطای کلی در بارگذاری صفحه: {str(e)}")
        audit_logger.alert(f"خطای کلی در دسترسی به صفحه برنامه تولید")
        
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
        }
        return render(request, 'production_declaration_crud.html', context)
