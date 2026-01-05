from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Sum, Q
from decimal import Decimal

import logging
from core.logging_levels import *
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field

from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.ProductFolder.ProductModel import Product

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def to_persian_digits(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    if text is None:
        return ''
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


def persian_number_with_comma(value, decimal_places=2):
    """فرمت کردن عدد با کاما و تبدیل به فارسی"""
    if value is None:
        return '-'
    try:
        num_float = float(value)
        if decimal_places == 0:
            formatted = f"{num_float:,.0f}"
        else:
            formatted = f"{num_float:,.{decimal_places}f}"
        return to_persian_digits(formatted)
    except (ValueError, TypeError):
        return str(value)


def get_accessible_warehouse_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Warehouse - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['warehouse_id'] = user_can_access_field(user, Warehouse, 'warehouse_id', 'view')
    accessible_fields['name'] = user_can_access_field(user, Warehouse, 'name', 'view')
    accessible_fields['warehouse_type'] = user_can_access_field(user, Warehouse, 'warehouse_type', 'view')
    accessible_fields['warehouse_capacity'] = user_can_access_field(user, Warehouse, 'warehouse_capacity', 'view')
    accessible_fields['used_capacity'] = user_can_access_field(user, Warehouse, 'used_capacity', 'view')
    accessible_fields['remaining_capacity'] = user_can_access_field(user, Warehouse, 'remaining_capacity', 'view')
    return accessible_fields


def get_accessible_inventory_item_fields(user):
    """بررسی دسترسی کاربر به فیلدهای InventoryItem - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['quantity'] = user_can_access_field(user, InventoryItem, 'quantity', 'view')
    accessible_fields['item'] = user_can_access_field(user, InventoryItem, 'item', 'view')
    return accessible_fields


def get_accessible_raw_material_fields(user):
    """بررسی دسترسی کاربر به فیلدهای RawMaterial - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['name'] = user_can_access_field(user, RawMaterial, 'name', 'view')
    accessible_fields['raw_material_id'] = user_can_access_field(user, RawMaterial, 'raw_material_id', 'view')
    return accessible_fields


def get_accessible_product_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Product - فقط مشاهده"""
    accessible_fields = {}
    accessible_fields['name'] = user_can_access_field(user, Product, 'name', 'view')
    accessible_fields['code'] = user_can_access_field(user, Product, 'code', 'view')
    return accessible_fields


@login_required
def warehouse_view(request):
    """
    نمایش انبارها در سه بخش:
    - انبار مواد اولیه (primary)
    - انبار تولید (production)
    - انبار محصولات (secondary)
    """
    # بررسی دسترسی task
    if not user_has_task(request.user, TaskChoices.PRODUCTION_VIEW_WAREHOUSE.value):
        audit_logger.alert(f"دسترسی غیرمجاز به مشاهده انبار")
        return HttpResponseForbidden("شما اجازه دسترسی به این صفحه را ندارید.")
    
    audit_logger.info("دسترسی به مشاهده انبار")
    
    try:
        # دریافت انبارهای مواد اولیه
        primary_warehouses = Warehouse.objects.filter(
            warehouse_type='primary'
        ).prefetch_related('inventory_items').order_by('name')
        
        # دریافت انبارهای تولید
        production_warehouses = Warehouse.objects.filter(
            warehouse_type='production'
        ).prefetch_related('inventory_items').order_by('name')
        
        # دریافت انبارهای محصولات
        secondary_warehouses = Warehouse.objects.filter(
            warehouse_type='secondary'
        ).prefetch_related('inventory_items').order_by('name')
        
        # محاسبه اطلاعات برای هر انبار
        def calculate_warehouse_info(warehouse):
            # محاسبه مجموع موجودی از InventoryItem
            total_used = Decimal('0')
            items_data = []
            
            capacity = float(warehouse.warehouse_capacity) if warehouse.warehouse_capacity else 0
            
            for inv_item in warehouse.inventory_items.all():
                if inv_item.quantity:
                    total_used += Decimal(str(inv_item.quantity))
                    
                    # اطلاعات آیتم
                    item_name = str(inv_item.item) if inv_item.item else 'نامشخص'
                    item_type = 'rawmaterial' if inv_item.is_raw_material else 'product'
                    quantity = float(inv_item.quantity)
                    unit = 'کیلوگرم'  # همه وزن‌ها به کیلوگرم نمایش داده می‌شوند
                    
                    # محاسبه درصد این آیتم از کل ظرفیت
                    item_percentage = (quantity / capacity * 100) if capacity > 0 else 0
                    
                    items_data.append({
                        'name': item_name,
                        'type': item_type,
                        'quantity': quantity,
                        'unit': unit,
                        'percentage': item_percentage
                    })
            
            # محاسبه درصد استفاده کل
            used = float(total_used)
            percentage = (used / capacity * 100) if capacity > 0 else 0
            # محدود کردن درصد به حداکثر 100%
            percentage = min(percentage, 100)
            remaining = capacity - used if capacity > 0 else 0
            
            # فرمت کردن اعداد با کاما و تبدیل به فارسی
            capacity_formatted = persian_number_with_comma(capacity, 2)
            used_formatted = persian_number_with_comma(used, 2)
            remaining_formatted = persian_number_with_comma(remaining, 2)
            percentage_formatted = persian_number_with_comma(percentage, 1)
            
            # فرمت کردن مقادیر آیتم‌ها و محاسبه مختصات برای نمودار SVG
            import math
            colors = ['#28a745', '#17a2b8', '#ffc107', '#fd7e14', '#dc3545', '#6f42c1', '#e83e8c', '#20c997', '#6c757d', '#0dcaf0']
            center_x, center_y = 90, 90  # مرکز SVG
            radius = 90
            
            current_angle = -90  # شروع از بالا (درجه)
            
            # محاسبه مجموع زوایا برای محدود کردن به 360 درجه (100%)
            total_angle = 0
            if capacity > 0:
                total_angle = (used / capacity) * 360
            else:
                total_angle = 0
            
            # محدود کردن به حداکثر 360 درجه (100%)
            if total_angle > 360:
                total_angle = 360
                scale_factor = 360 / ((used / capacity) * 360) if capacity > 0 and used > 0 else 1
            else:
                scale_factor = 1
            
            for idx, item in enumerate(items_data):
                item['quantity_formatted'] = persian_number_with_comma(item['quantity'], 2)
                item['percentage_formatted'] = persian_number_with_comma(item['percentage'], 1)
                item['color'] = colors[idx % len(colors)]
                
                # محاسبه زاویه برای نمودار (بر اساس کل ظرفیت) با محدودیت 360 درجه
                if capacity > 0:
                    angle_deg = (item['quantity'] / capacity) * 360 * scale_factor
                else:
                    angle_deg = 0
                
                # اگر مجموع زوایا از 360 بیشتر شد، فقط تا 360 نمایش بده
                if current_angle + angle_deg > -90 + 360:
                    angle_deg = (-90 + 360) - current_angle
                    if angle_deg < 0:
                        angle_deg = 0
                
                # تبدیل درجه به رادیان
                start_angle_rad = math.radians(current_angle)
                end_angle_rad = math.radians(current_angle + angle_deg)
                
                # محاسبه مختصات نقاط شروع و پایان
                start_x = center_x + radius * math.cos(start_angle_rad)
                start_y = center_y + radius * math.sin(start_angle_rad)
                end_x = center_x + radius * math.cos(end_angle_rad)
                end_y = center_y + radius * math.sin(end_angle_rad)
                
                # تعیین اینکه آیا arc بزرگ است یا کوچک
                large_arc = 1 if angle_deg > 180 else 0
                
                item['start_angle'] = current_angle
                item['end_angle'] = current_angle + angle_deg
                item['angle'] = angle_deg
                item['start_x'] = round(start_x, 2)
                item['start_y'] = round(start_y, 2)
                item['end_x'] = round(end_x, 2)
                item['end_y'] = round(end_y, 2)
                item['large_arc'] = large_arc
                
                current_angle += angle_deg
                
                # اگر به 360 درجه رسیدیم، دیگر ادامه نده
                if current_angle >= -90 + 360:
                    break
            
            # محاسبه برای نمایش درصد کل (اگر آیتمی نباشد)
            chart_data = {}
            if not items_data and capacity > 0:
                angle_deg = min(percentage, 100)  # حداکثر 100%
                start_angle_rad = math.radians(-90)
                end_angle_rad = math.radians(-90 + angle_deg)
                end_x = center_x + radius * math.cos(end_angle_rad)
                end_y = center_y + radius * math.sin(end_angle_rad)
                large_arc = 1 if angle_deg > 180 else 0
                chart_data['end_x'] = round(end_x, 2)
                chart_data['end_y'] = round(end_y, 2)
                chart_data['large_arc'] = large_arc
            
            result = {
                'warehouse': warehouse,
                'capacity': capacity,
                'used': used,
                'remaining': remaining,
                'percentage': min(percentage, 100),  # حداکثر 100%
                'capacity_formatted': capacity_formatted,
                'used_formatted': used_formatted,
                'remaining_formatted': remaining_formatted,
                'percentage_formatted': percentage_formatted,
                'items': items_data,
                'items_count': len(items_data),
                'unit': 'کیلوگرم'  # واحد نمایش
            }
            
            # اضافه کردن داده‌های نمودار
            result.update(chart_data)
            
            return result
        
        # محاسبه اطلاعات برای هر بخش
        primary_data = [calculate_warehouse_info(w) for w in primary_warehouses]
        production_data = [calculate_warehouse_info(w) for w in production_warehouses]
        secondary_data = [calculate_warehouse_info(w) for w in secondary_warehouses]
        
        # بررسی دسترسی فیلدها
        accessible_warehouse_fields = get_accessible_warehouse_fields(request.user)
        accessible_inventory_item_fields = get_accessible_inventory_item_fields(request.user)
        accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
        accessible_product_fields = get_accessible_product_fields(request.user)
        
        context = {
            'primary_warehouses': primary_data,
            'production_warehouses': production_data,
            'secondary_warehouses': secondary_data,
            'accessible_warehouse_fields': accessible_warehouse_fields,
            'accessible_inventory_item_fields': accessible_inventory_item_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_product_fields': accessible_product_fields,
        }
        
        bug_logger.info(f"مشاهده انبار با موفقیت بارگذاری شد")
        return render(request, 'warehouse_view.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در بارگذاری مشاهده انبار: {str(e)}", exc_info=True)
        return render(request, 'warehouse_view.html', {
            'error': 'خطا در بارگذاری اطلاعات انبار'
        })

