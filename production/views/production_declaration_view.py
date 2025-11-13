from django.shortcuts import render
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

import logging
from core.logging_levels import *

from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial

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
        return render(request, 'production/production_declaration.html', context)
    
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
        return render(request, 'production/production_declaration.html', context)
