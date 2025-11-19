from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from sales.views.allocation_list import (
    calculate_order_total_quantity,
    calculate_allocation_total_quantity,
    get_delivery_address_info
)

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def approve_allocation_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تأیید تخصیص»
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تأیید تخصیص")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity("تلاش برای دسترسی به لیست تأیید تخصیص بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_allocation_approval').order_by('-created_at')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    # بررسی برابری مقادیر برای هر سفارش
    orders_with_info = []
    for order in orders_qs.select_related('registered_by', 'customer'):
        allocations = Allocation.objects.filter(order=order).select_related('order')
        order_total = calculate_order_total_quantity(order)
        allocation_total = calculate_allocation_total_quantity(order)
        is_balanced = abs(order_total - allocation_total) < 0.001
        
        # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند (وضعیت 'approved')
        all_inquired = all(allocation.allocation_status == 'approved' for allocation in allocations)
        
        orders_with_info.append({
            'order': order,
            'allocations_count': allocations.count(),
            'order_total': order_total,
            'allocation_total': allocation_total,
            'is_balanced': is_balanced,
            'all_inquired': all_inquired,
        })

    bug_logger.debug(f"تعداد {len(orders_with_info)} سفارش در انتظار تأیید تخصیص لود شد")
    
    if len(orders_with_info) > 0:
        bug_logger.info("لیست سفارش‌های در انتظار تأیید تخصیص با موفقیت نمایش داده شد")

    context = {
        'orders_with_info': orders_with_info,
        'page_title': 'سفارش‌های در انتظار تأیید تخصیص',
    }
    return render(request, 'allocation/approve_allocation_list.html', context)


@login_required
def approve_allocation_detail_view(request, order_number):
    """
    صفحه جزئیات تأیید تخصیص برای یک سفارش
    - نمایش همه تخصیص‌های سفارش
    - دکمه تأیید استعلام برای هر تخصیص
    - بررسی برابری مقادیر
    - بعد از تأیید همه تخصیص‌ها، سفارش به "در انتظار کارخانه" می‌رود
    """
    audit_logger.info(f"درخواست مشاهده جزئیات تأیید تخصیص سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity(f"تلاش برای دسترسی به جزئیات تأیید تخصیص سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_allocation_approval':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_allocation_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تأیید تخصیص نیست.')
        return redirect('sales:approve_allocation_list')

    # محاسبه مقادیر
    order_total = calculate_order_total_quantity(order)
    allocation_total = calculate_allocation_total_quantity(order)
    is_balanced = abs(order_total - allocation_total) < 0.001
    difference = order_total - allocation_total

    # دریافت تخصیص‌ها
    allocations = Allocation.objects.filter(order=order).select_related('order').prefetch_related('product_infos__product')
    
    # آماده‌سازی اطلاعات تخصیص‌ها
    allocations_with_info = []
    for allocation in allocations:
        delivery_info = None
        is_inquired = False
        
        if allocation.delivery_postal_code:
            delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
            # بررسی اینکه آیا استعلام تأیید شده است (وضعیت allocation باید 'approved' باشد)
            if allocation.allocation_status == 'approved':
                is_inquired = True
        
        # محاسبه مقدار این تخصیص
        allocation_quantity = 0
        for product_info in allocation.product_infos.all():
            quantity = float(product_info.quantity or 0)
            unit = product_info.unit
            if unit == 'kg':
                allocation_quantity += quantity
            elif unit == 'ton':
                allocation_quantity += quantity * 1000
            elif unit == 'gr':
                allocation_quantity += quantity / 1000
        
        allocations_with_info.append({
            'allocation': allocation,
            'delivery_info': delivery_info,
            'is_inquired': is_inquired,
            'quantity': allocation_quantity,
            'product_infos': allocation.product_infos.all(),
        })
    
    # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند
    all_inquired = all(item['is_inquired'] for item in allocations_with_info)

    context = {
        'order': order,
        'allocations_with_info': allocations_with_info,
        'order_total': order_total,
        'allocation_total': allocation_total,
        'is_balanced': is_balanced,
        'difference': difference,
        'all_inquired': all_inquired,
        'page_title': f'تأیید تخصیص سفارش {order_number}',
    }
    return render(request, 'allocation/approve_allocation_detail.html', context)


@login_required
def approve_allocation_inquiry_view(request, order_number, allocation_number):
    """
    تأیید استعلام برای یک تخصیص
    - استعلام کد پستی و شناسه یکتا
    - بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند
    - اگر همه استعلام شدند، وضعیت سفارش به "در انتظار کارخانه" تغییر می‌کند
    """
    audit_logger.info(f"درخواست تأیید استعلام تخصیص {allocation_number} برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity(f"تلاش برای تأیید استعلام تخصیص {allocation_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number, order=order)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_allocation_approval':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_allocation_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تأیید تخصیص نیست.')
        return redirect('sales:approve_allocation_list')

    if not allocation.delivery_postal_code:
        bug_logger.warning(f"تخصیص {allocation_number} کد پستی ندارد")
        messages.error(request, 'این تخصیص کد پستی ندارد.')
        return redirect('sales:approve_allocation_detail', order_number=order_number)

    try:
        with transaction.atomic():
            # استعلام کد پستی و شناسه یکتا
            delivery_address = DeliveryAddress.objects.get(postal_code=allocation.delivery_postal_code)
            
            if not delivery_address.unique_delivery_id:
                bug_logger.warning(f"آدرس تحویل با کد پستی {allocation.delivery_postal_code} شناسه یکتا ندارد")
                messages.error(request, 'آدرس تحویل شناسه یکتا ندارد. لطفاً ابتدا شناسه یکتا را ثبت کنید.')
                return redirect('sales:approve_allocation_detail', order_number=order_number)
            
            # بررسی برابری مقادیر
            order_total = calculate_order_total_quantity(order)
            allocation_total = calculate_allocation_total_quantity(order)
            is_balanced = abs(order_total - allocation_total) < 0.001
            
            if not is_balanced:
                bug_logger.warning(f"مقادیر سفارش {order_number} برابر نیست (سفارش: {order_total}, تخصیص: {allocation_total})")
                messages.error(request, 'مقادیر تخصیص‌ها با سفارش برابر نیست. لطفاً ابتدا تخصیص‌ها را اصلاح کنید.')
                return redirect('sales:approve_allocation_detail', order_number=order_number)
            
            # تغییر وضعیت تخصیص به 'approved' برای نشان دادن تأیید استعلام
            allocation.allocation_status = 'approved'
            allocation.save(update_fields=['allocation_status'])
            
            # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند
            allocations = Allocation.objects.filter(order=order)
            all_inquired = all(alloc.allocation_status == 'approved' for alloc in allocations)
            
            bug_logger.info(f"استعلام تخصیص {allocation_number} برای سفارش {order_number} تأیید شد و وضعیت به approved تغییر کرد")
            
            if all_inquired:
                # تغییر وضعیت سفارش به "در انتظار کارخانه"
                order.status = 'pending_factory'
                order.save(update_fields=['status'])
                bug_logger.info(f"همه تخصیص‌های سفارش {order_number} استعلام شد و وضعیت به pending_factory تغییر کرد")
                messages.success(request, 'همه تخصیص‌ها تأیید شدند و سفارش به "در انتظار کارخانه" ارسال شد.')
            else:
                messages.success(request, 'استعلام این تخصیص تأیید شد. لطفاً سایر تخصیص‌ها را نیز تأیید کنید.')
            
            audit_logger.activity(f"استعلام تخصیص {allocation_number} برای سفارش {order_number} تأیید شد")
            return redirect('sales:approve_allocation_detail', order_number=order_number)
            
    except DeliveryAddress.DoesNotExist:
        bug_logger.error(f"آدرس تحویل با کد پستی {allocation.delivery_postal_code} یافت نشد")
        messages.error(request, 'آدرس تحویل یافت نشد.')
        return redirect('sales:approve_allocation_detail', order_number=order_number)
    except Exception as e:
        bug_logger.error(f"خطا در تأیید استعلام تخصیص {allocation_number} برای سفارش {order_number}: {str(e)}")
        messages.error(request, f'خطا در تأیید استعلام: {str(e)}')
        return redirect('sales:approve_allocation_detail', order_number=order_number)

