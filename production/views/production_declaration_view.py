from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

import logging
from core.logging_levels import *

from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from production.forms.program_form import ProductionProgramForm
from production.forms.production_form import ProductionForm

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
        # دریافت برنامه‌های تولید بر اساس وضعیت
        try:
            confirmed_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.CONFIRMED
            ).select_related('product', 'production_info').order_by('execution_date', 'predicted_start_time')
            bug_logger.debug(f"تعداد برنامه‌های تایید شده: {confirmed_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"خطا در بارگذاری برنامه‌های تایید شده: {str(e)}")
            confirmed_programs = ProductionProgram.objects.none()
        
        try:
            in_progress_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.IN_PROGRESS
            ).select_related('product', 'production_info').order_by('execution_date', 'predicted_start_time')
            bug_logger.debug(f"تعداد برنامه‌های در حال اجرا: {in_progress_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"خطا در بارگذاری برنامه‌های در حال اجرا: {str(e)}")
            in_progress_programs = ProductionProgram.objects.none()
        
        try:
            completed_programs = ProductionProgram.objects.filter(
                status=ProductionProgram.Status.COMPLETED
            ).select_related('product', 'production_info').order_by('-execution_date', '-predicted_end_time')[:20]
            bug_logger.debug(f"تعداد برنامه‌های تکمیل شده: {completed_programs.count()}")
        except Exception as e:
            bug_logger.warning(f"خطا در بارگذاری برنامه‌های تکمیل شده: {str(e)}")
            completed_programs = ProductionProgram.objects.none()
        
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
            'completed_programs': completed_programs,
            'raw_materials_inventory': raw_materials_inventory,
        }
        
        bug_logger.info("صفحه اعلام تولید با موفقیت بارگذاری شد")
        return render(request, 'production_declaration.html', context)
    
    except Exception as e:
        bug_logger.error(f"خطای کلی در بارگذاری صفحه اعلام تولید: {str(e)}")
        audit_logger.alert("خطای کلی در دسترسی به صفحه اعلام تولید")
        
        # بازگشت صفحه خالی در صورت خطا
        context = {
            'confirmed_programs': ProductionProgram.objects.none(),
            'in_progress_programs': ProductionProgram.objects.none(),
            'completed_programs': ProductionProgram.objects.none(),
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
        
        context = {
            'form': form,
            'program': program,
            'is_create': is_create,
            'raw_materials_inventory': raw_materials_inventory,
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
