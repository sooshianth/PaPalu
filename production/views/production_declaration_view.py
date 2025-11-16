from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template.loader import render_to_string

import logging
from core.logging_levels import *

from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductModel import Product
from production.forms.program_form import ProductionProgramForm
from production.forms.production_form import ProductionForm
import json

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def production_declaration_view(request):
    """
    صفحه اعلام تولید
    نمایش برنامه‌های تولید بر اساس وضعیت و موجودی مواد اولیه
    """
    audit_logger.info("دسترسی به صفحه اعلام تولید")
    bug_logger.debug("شروع بارگذاری صفحه اعلام تولید")
    
    try:
        # Get search parameters for each table separately
        search_id_confirmed = request.GET.get('search_id_confirmed', '').strip()
        search_product_confirmed = request.GET.get('search_product_confirmed', '').strip()
        
        search_id_progress = request.GET.get('search_id_progress', '').strip()
        search_product_progress = request.GET.get('search_product_progress', '').strip()
        
        search_id_completed = request.GET.get('search_id_completed', '').strip()
        search_product_completed = request.GET.get('search_product_completed', '').strip()
        
        # Get sort parameters for each table
        sort_by_confirmed = request.GET.get('sort_confirmed', 'execution_date')
        sort_dir_confirmed = request.GET.get('dir_confirmed', 'asc')
        
        sort_by_progress = request.GET.get('sort_progress', 'execution_date')
        sort_dir_progress = request.GET.get('dir_progress', 'asc')
        
        sort_by_completed = request.GET.get('sort_completed', 'execution_date')
        sort_dir_completed = request.GET.get('dir_completed', 'desc')
        
        # Validate sort columns
        allowed_sorts = ['id', 'execution_date', 'predicted_start_time', 'predicted_end_time', 'planned_weight_ton', 'status']
        
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
            
            # Apply search filters for confirmed table
            if search_id_confirmed:
                confirmed_programs = confirmed_programs.filter(id__icontains=search_id_confirmed)
            if search_product_confirmed:
                confirmed_programs = confirmed_programs.filter(product__name__icontains=search_product_confirmed)
            
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
            
            # Apply search filters for in-progress table
            if search_id_progress:
                in_progress_programs = in_progress_programs.filter(id__icontains=search_id_progress)
            if search_product_progress:
                in_progress_programs = in_progress_programs.filter(product__name__icontains=search_product_progress)
            
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
            
            # Apply search filters for completed table
            if search_id_completed:
                completed_programs_qs = completed_programs_qs.filter(id__icontains=search_id_completed)
            if search_product_completed:
                completed_programs_qs = completed_programs_qs.filter(product__name__icontains=search_product_completed)
            
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
                            if raw_material:
                                raw_materials_inventory.append({
                                    'raw_material_id': getattr(raw_material, 'raw_material_id', '-'),
                                    'name': getattr(raw_material, 'name', '-'),
                                    'warehouse': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'quantity': item.quantity if item.quantity else 0,
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
            # Search parameters for each table
            'search_id_confirmed': search_id_confirmed,
            'search_product_confirmed': search_product_confirmed,
            'search_id_progress': search_id_progress,
            'search_product_progress': search_product_progress,
            'search_id_completed': search_id_completed,
            'search_product_completed': search_product_completed,
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
                        # Auto-fill started_at to now if not already set
                        if not instance.started_at:
                            instance.started_at = timezone.now()
                    elif action == 'complete':
                        instance.status = ProductionProgram.Status.COMPLETED
                        # Auto-fill completed_at to now if not already set
                        if not instance.completed_at:
                            instance.completed_at = timezone.now()
                    
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
                            if raw_material:
                                raw_materials_inventory.append({
                                    'raw_material_id': getattr(raw_material, 'raw_material_id', '-'),
                                    'name': getattr(raw_material, 'name', '-'),
                                    'warehouse': item.warehouse.warehouse_id if item.warehouse else '-',
                                    'quantity': item.quantity if item.quantity else 0,
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
                        bom_items.append({
                            'raw_material_id': bom.raw_material.raw_material_id if bom.raw_material else '-',
                            'raw_material_name': bom.raw_material.name if bom.raw_material else '-',
                            'quantity': str(bom.quantity) if bom.quantity else '0',
                            'unit_used': bom.unit_used or '-',
                        })
                    
                    bom_data[prod_info.id] = {
                        'program_id': prod_info.formula_id or '',
                        'min_batch_production': str(prod_info.min_batch_production) if prod_info.min_batch_production else '',
                        'specific_production_instruction': prod_info.specific_production_instruction or '',
                        'bom_items': bom_items
                    }
        except Exception as e:
            bug_logger.error(f"خطا در آماده‌سازی داده‌های BOM: {str(e)}")
        
        context = {
            'form': form,
            'program': program,
            'is_create': is_create,
            'raw_materials_inventory': raw_materials_inventory,
            'production_infos_json': json.dumps(production_infos_data),
            'bom_data_json': json.dumps(bom_data),
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
        }
        return render(request, 'production_declaration_crud.html', context)
