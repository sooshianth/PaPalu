from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, F
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.AllocationFolder.AllocationSchedulingInfoModel import AllocationSchedulingInfo
from core.OrderFolder.OrderModel import Order
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.WarehouseFolder.WarehouseModel import Warehouse
from core.WarehouseFolder.InventoryItemModel import InventoryItem
from core.ProductFolder import Product
from django.contrib.contenttypes.models import ContentType
from access.helpers import check_field_access_prefer_edit

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_product_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Product"""
    if user.is_superuser:
        return {'name': True, 'code': True}
    
    accessible_fields = {}
    accessible_fields['name'] = check_field_access_prefer_edit(user, Product, 'name')
    accessible_fields['code'] = check_field_access_prefer_edit(user, Product, 'code')
    return accessible_fields


def get_accessible_allocation_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Allocation"""
    if user.is_superuser:
        return {'allocation_number': True, 'allocation_priority': True}
    
    accessible_fields = {}
    accessible_fields['allocation_number'] = check_field_access_prefer_edit(user, Allocation, 'allocation_number')
    accessible_fields['allocation_priority'] = check_field_access_prefer_edit(user, Allocation, 'allocation_priority')
    return accessible_fields


def get_accessible_order_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Order"""
    if user.is_superuser:
        return {'order_number': True}
    
    accessible_fields = {}
    accessible_fields['order_number'] = check_field_access_prefer_edit(user, Order, 'order_number')
    return accessible_fields


def get_product_inventory_aggregated():
    """
    محاسبه موجودی تجمیعی محصولات در همه انبارهای مواد ثانویه
    """
    # دریافت انبارهای مواد ثانویه
    secondary_warehouses = Warehouse.objects.filter(warehouse_type='secondary')
    
    # دریافت ContentType برای Product
    product_content_type = ContentType.objects.get_for_model(Product)
    
    # محاسبه موجودی تجمیعی برای هر محصول
    inventory_items = InventoryItem.objects.filter(
        warehouse__in=secondary_warehouses,
        content_type=product_content_type
    ).values('object_id').annotate(
        total_quantity=Sum('quantity')
    )
    
    # تبدیل به دیکشنری برای دسترسی آسان‌تر
    inventory_dict = {}
    for item in inventory_items:
        try:
            product = Product.objects.get(id=item['object_id'])
            inventory_dict[product.id] = {
                'product': product,
                'total_quantity': item['total_quantity'] or 0
            }
        except Product.DoesNotExist:
            continue
    
    return inventory_dict


def get_production_programs_info():
    """
    دریافت اطلاعات برنامه‌های تولید در حال اجرا و در صف تولید
    """
    # برنامه‌های در حال اجرا
    in_progress = ProductionProgram.objects.filter(
        status=ProductionProgram.Status.IN_PROGRESS
    ).select_related('product', 'production_info').order_by('-created_at')
    
    # برنامه‌های در صف تولید (تأیید شده)
    in_queue = ProductionProgram.objects.filter(
        status=ProductionProgram.Status.CONFIRMED
    ).select_related('product', 'production_info').order_by('priority_index', '-created_at')
    
    return {
        'in_progress': in_progress,
        'in_queue': in_queue
    }


@login_required
def shipping_announcement_list_view(request):
    """
    لیست تخصیص‌های در انتظار اعلام بار
    نمایش اطلاعات کامل شامل محصولات، موجودی و برنامه‌های تولید
    """
    audit_logger.info("درخواست مشاهده لیست تخصیص‌های در انتظار اعلام بار")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_VIEW_SHIPPING_ANNOUNCEMENT_LIST.value):
        audit_logger.activity("تلاش برای دسترسی به لیست اعلام بار بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست اعلام بار را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت تخصیص‌های در انتظار اعلام بار
    allocations = Allocation.objects.filter(
        allocation_status='pending_shipping'
    ).select_related('order', 'order__customer').prefetch_related(
        'product_infos__product'
    ).order_by('-allocation_priority', '-created_at')
    
    # آماده‌سازی اطلاعات تخصیص‌ها
    allocations_with_info = []
    for allocation in allocations:
        # محاسبه محصولات و مقادیر
        products_info = []
        total_quantity_kg = 0
        
        for product_info in allocation.product_infos.all():
            quantity = float(product_info.quantity or 0)
            unit = product_info.unit
            
            # تبدیل به کیلوگرم
            if unit == 'kg':
                quantity_kg = quantity
            elif unit == 'ton':
                quantity_kg = quantity * 1000
            elif unit == 'gr':
                quantity_kg = quantity / 1000
            else:
                quantity_kg = quantity  # در صورت عدم تطابق، همان مقدار را نگه می‌داریم
            
            total_quantity_kg += quantity_kg
            
            products_info.append({
                'product': product_info.product,
                'quantity': quantity,
                'unit': product_info.get_unit_display(),
                'quantity_kg': quantity_kg
            })
        
        allocations_with_info.append({
            'allocation': allocation,
            'order_number': allocation.order.order_number if allocation.order else '-',
            'products_info': products_info,
            'total_quantity_kg': total_quantity_kg
        })
    
    # دریافت موجودی محصولات
    inventory_dict = get_product_inventory_aggregated()
    
    # دریافت اطلاعات برنامه‌های تولید
    production_info = get_production_programs_info()
    
    # بررسی دسترسی فیلدها
    accessible_product_fields = get_accessible_product_fields(request.user)
    accessible_allocation_fields = get_accessible_allocation_fields(request.user)
    accessible_order_fields = get_accessible_order_fields(request.user)
    
    bug_logger.debug(f"تعداد {len(allocations_with_info)} تخصیص در انتظار اعلام بار لود شد")
    
    context = {
        'allocations_with_info': allocations_with_info,
        'inventory_dict': inventory_dict,
        'production_programs': production_info,
        'accessible_product_fields': accessible_product_fields,
        'accessible_allocation_fields': accessible_allocation_fields,
        'accessible_order_fields': accessible_order_fields,
        'page_title': 'لیست تخصیص‌های در انتظار اعلام بار',
    }
    return render(request, 'distribution/shipping_announcement_list.html', context)


@login_required
def shipping_announcement_process_view(request):
    """
    پردازش اعلام بار برای تخصیص‌های انتخاب شده
    """
    audit_logger.info("درخواست پردازش اعلام بار")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_PROCESS_SHIPPING_ANNOUNCEMENT.value):
        audit_logger.activity("تلاش برای پردازش اعلام بار بدون دسترسی")
        messages.error(request, 'شما دسترسی به پردازش اعلام بار را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    if request.method == 'POST':
        allocation_numbers = request.POST.getlist('allocation_numbers')
        shipping_method = request.POST.get('shipping_method')
        
        if not allocation_numbers:
            messages.error(request, 'لطفاً حداقل یک تخصیص را انتخاب کنید.')
            return redirect('distribution:shipping_announcement_list')
        
        if not shipping_method:
            messages.error(request, 'لطفاً شیوه اعلام بار را انتخاب کنید.')
            return redirect('distribution:shipping_announcement_list')
        
        if shipping_method not in ['customer_vehicle', 'carrier']:
            messages.error(request, 'شیوه اعلام بار نامعتبر است.')
            return redirect('distribution:shipping_announcement_list')
        
        try:
            with transaction.atomic():
                now = timezone.now()
                updated_count = 0
                
                for allocation_number in allocation_numbers:
                    try:
                        allocation = Allocation.objects.get(
                            allocation_number=allocation_number,
                            allocation_status='pending_shipping'
                        )
                        
                        # به‌روزرسانی وضعیت و شیوه اعلام بار
                        allocation.allocation_status = 'pending_vehicle_recruitment'
                        allocation.shipping_announcement_method = shipping_method
                        allocation.save(update_fields=['allocation_status', 'shipping_announcement_method'])
                        
                        # به‌روزرسانی زمان اعلام بار در AllocationSchedulingInfo
                        scheduling_info, created = AllocationSchedulingInfo.objects.get_or_create(
                            allocation=allocation
                        )
                        scheduling_info.shipping_announcement_time = now
                        scheduling_info.save(update_fields=['shipping_announcement_time'])
                        
                        updated_count += 1
                        bug_logger.info(f"تخصیص {allocation_number} به وضعیت pending_vehicle_recruitment تغییر کرد")
                        
                    except Allocation.DoesNotExist:
                        bug_logger.warning(f"تخصیص {allocation_number} یافت نشد یا در وضعیت مناسب نیست")
                        continue
                
                if updated_count > 0:
                    messages.success(
                        request, 
                        f'{updated_count} تخصیص با موفقیت اعلام بار شد و به "در انتظار جذب خودرو" تغییر وضعیت داد.'
                    )
                    audit_logger.activity(f"{updated_count} تخصیص اعلام بار شد توسط کاربر {request.user.username}")
                else:
                    messages.warning(request, 'هیچ تخصیصی به‌روزرسانی نشد.')
                
                return redirect('distribution:shipping_announcement_list')
                
        except Exception as e:
            bug_logger.error(f"خطا در پردازش اعلام بار: {str(e)}")
            messages.error(request, f'خطا در پردازش اعلام بار: {str(e)}')
            return redirect('distribution:shipping_announcement_list')
    
    return redirect('distribution:shipping_announcement_list')


@login_required
def shipping_announcement_single_view(request):
    """
    پردازش اعلام بار برای یک تخصیص (جداگانه)
    """
    audit_logger.info("درخواست پردازش اعلام بار جداگانه")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_PROCESS_SHIPPING_ANNOUNCEMENT.value):
        audit_logger.activity("تلاش برای پردازش اعلام بار بدون دسترسی")
        messages.error(request, 'شما دسترسی به پردازش اعلام بار را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    if request.method == 'POST':
        allocation_number = request.POST.get('allocation_number')
        shipping_method = request.POST.get('shipping_method')
        
        if not allocation_number:
            messages.error(request, 'شماره تخصیص مشخص نشده است.')
            return redirect('distribution:shipping_announcement_list')
        
        if not shipping_method:
            messages.error(request, 'لطفاً شیوه اعلام بار را انتخاب کنید.')
            return redirect('distribution:shipping_announcement_list')
        
        if shipping_method not in ['customer_vehicle', 'carrier']:
            messages.error(request, 'شیوه اعلام بار نامعتبر است.')
            return redirect('distribution:shipping_announcement_list')
        
        try:
            with transaction.atomic():
                allocation = Allocation.objects.get(
                    allocation_number=allocation_number,
                    allocation_status='pending_shipping'
                )
                
                now = timezone.now()
                
                # به‌روزرسانی وضعیت و شیوه اعلام بار
                allocation.allocation_status = 'pending_vehicle_recruitment'
                allocation.shipping_announcement_method = shipping_method
                allocation.save(update_fields=['allocation_status', 'shipping_announcement_method'])
                
                # به‌روزرسانی زمان اعلام بار در AllocationSchedulingInfo
                scheduling_info, created = AllocationSchedulingInfo.objects.get_or_create(
                    allocation=allocation
                )
                scheduling_info.shipping_announcement_time = now
                scheduling_info.save(update_fields=['shipping_announcement_time'])
                
                bug_logger.info(f"تخصیص {allocation_number} به صورت جداگانه اعلام بار شد و به وضعیت pending_vehicle_recruitment تغییر کرد")
                messages.success(request, f'تخصیص {allocation_number} با موفقیت اعلام بار شد.')
                audit_logger.activity(f"تخصیص {allocation_number} اعلام بار شد توسط کاربر {request.user.username}")
                
                return redirect('distribution:shipping_announcement_list')
                
        except Allocation.DoesNotExist:
            bug_logger.warning(f"تخصیص {allocation_number} یافت نشد یا در وضعیت مناسب نیست")
            messages.error(request, 'تخصیص یافت نشد یا در وضعیت مناسب برای اعلام بار نیست.')
            return redirect('distribution:shipping_announcement_list')
        except Exception as e:
            bug_logger.error(f"خطا در پردازش اعلام بار جداگانه: {str(e)}")
            messages.error(request, f'خطا در پردازش اعلام بار: {str(e)}')
            return redirect('distribution:shipping_announcement_list')
    
    return redirect('distribution:shipping_announcement_list')

