from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, Count, Case, When, DecimalField, F, BooleanField, Exists, OuterRef, Subquery
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from sales.views.allocation_list_view import (
    calculate_order_total_quantity,
    calculate_allocation_total_quantity,
    get_delivery_address_info
)
from sales.tables.tables_allocation import ApproveAllocationTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def approve_allocation_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تأیید تخصیص»
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تأیید تخصیص")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_ALLOCATION.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity("تلاش برای دسترسی به لیست تأیید تخصیص بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت پارامتر جستجو
    search_query = request.GET.get('search', '').strip()

    orders_qs = Order.objects.filter(status='pending_allocation_approval').select_related('customer', 'registered_by')
    
    # فیلتر کردن سفارش‌هایی که تخصیص رد شده دارند
    orders_qs = orders_qs.exclude(allocations__is_rejected=True).distinct()

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    # اعمال جستجو (شماره سفارش، نام مشتری)
    if search_query:
        orders_qs = orders_qs.filter(
            Q(order_number__icontains=search_query) |
            Q(customer__name__icontains=search_query)
        )

    # افزودن annotate برای فیلدهای محاسبه شده
    # مهم: ابتدا مقدار سفارش را با استفاده از Subquery محاسبه می‌کنیم
    # تا از تکرار مقادیر به دلیل join های متعدد جلوگیری شود
    from core.OrderFolder.OrderItemModel import OrderItem
    
    # محاسبه مقدار سفارش با استفاده از Subquery
    # این کار باعث می‌شود که join های allocations روی محاسبه تأثیر نگذارند
    # استفاده از values().annotate() و سپس Subquery برای برگرداندن یک مقدار
    order_total_subquery = OrderItem.objects.filter(
        order=OuterRef('pk')
    ).values('order').annotate(
        total=Sum(
            Case(
                When(weight_unit='kg', then=F('quantity')),
                When(weight_unit='ton', then=F('quantity') * 1000),
                When(
                    Q(weight_unit='bag') & Q(bag_weight__isnull=False),
                    then=F('quantity') * F('bag_weight')
                ),
                When(weight_unit='piece', then=F('quantity')),
                default=0,
                output_field=DecimalField(max_digits=15, decimal_places=3)
            )
        )
    ).values('total')[:1]
    
    orders_qs = orders_qs.annotate(
        order_total_quantity_kg=Subquery(order_total_subquery, output_field=DecimalField(max_digits=15, decimal_places=3))
    )
    
    # تعداد تخصیص‌ها
    orders_qs = orders_qs.annotate(
        allocations_count=Count('allocations', distinct=True)
    )
    
    # محاسبه مقدار تخصیص شده (کیلوگرم)
    orders_qs = orders_qs.annotate(
        allocation_total_quantity_kg=Sum(
            Case(
                When(allocations__product_infos__unit='kg', then=F('allocations__product_infos__quantity')),
                When(allocations__product_infos__unit='ton', then=F('allocations__product_infos__quantity') * 1000),
                When(allocations__product_infos__unit='gr', then=F('allocations__product_infos__quantity') / 1000),
                default=0,
                output_field=DecimalField(max_digits=15, decimal_places=3)
            )
        )
    )
    
    # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند (وضعیت 'pending_shipping')
    # استفاده از subquery برای بررسی اینکه آیا تخصیصی با وضعیت غیر از 'pending_shipping' وجود دارد
    not_inquired_allocations = Allocation.objects.filter(
        order=OuterRef('pk')
    ).exclude(
        allocation_status='pending_shipping'
    )
    
    # همه استعلام شده‌اند اگر: هیچ تخصیصی با وضعیت غیر از 'pending_shipping' وجود نداشته باشد
    # اگر allocations_count > 0 باشد و not_inquired_allocations خالی باشد، یعنی همه استعلام شده‌اند
    orders_qs = orders_qs.annotate(
        all_inquired_status=Case(
            When(allocations_count=0, then=False),  # اگر تخصیصی وجود نداشته باشد، False
            default=~Exists(not_inquired_allocations),
            output_field=BooleanField()
        )
    )
    
    # مرتب‌سازی پیش‌فرض
    orders_qs = orders_qs.order_by('-created_at')

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار تأیید تخصیص لود شد")
    
    # محاسبه فیلدهای قابل دسترسی (در صورت نیاز)
    accessible_fields = None
    
    # ایجاد جدول با django-tables2
    table = ApproveAllocationTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    if orders_qs.count() > 0:
        bug_logger.info("لیست سفارش‌های در انتظار تأیید تخصیص با موفقیت نمایش داده شد")

    context = {
        'table': table,
        'search_query': search_query,
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
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_ALLOCATION.value):  # TODO: باید task مناسب اضافه شود
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

    # دریافت تخصیص‌ها (فقط تخصیص‌های رد نشده و با status 'pending_approval')
    # superadmin می‌تواند همه را ببیند
    if request.user.is_superuser:
        allocations = Allocation.objects.filter(order=order, is_rejected=False).select_related('order').prefetch_related('product_infos__product')
    else:
        allocations = Allocation.objects.filter(order=order, is_rejected=False, allocation_status='pending_approval').select_related('order').prefetch_related('product_infos__product')
    
    # آماده‌سازی اطلاعات تخصیص‌ها
    allocations_with_info = []
    for allocation in allocations:
        delivery_info = None
        is_inquired = False
        
        if allocation.delivery_postal_code:
            delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
            # بررسی اینکه آیا استعلام تأیید شده است (وضعیت allocation باید 'pending_shipping' باشد)
            if allocation.allocation_status == 'pending_shipping':
                is_inquired = True
        from decimal import Decimal
        allocation_quantity = Decimal('0')
        for product_info in allocation.product_infos.all():
            quantity = Decimal(str(product_info.quantity or 0))
            unit = product_info.unit
            if unit == 'kg':
                allocation_quantity += quantity
            elif unit == 'ton':
                allocation_quantity += quantity * 1000
            elif unit == 'gr':
                allocation_quantity += quantity / 1000
            else:
                allocation_quantity += quantity
        allocations_with_info.append({
            'allocation': allocation,
            'delivery_info': delivery_info,
            'is_inquired': is_inquired,
            'quantity': allocation_quantity,
            'product_infos': allocation.product_infos.all(),
        })
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
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_ALLOCATION.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity(f"تلاش برای تأیید استعلام تخصیص {allocation_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تأیید تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)
    # superadmin می‌تواند همه را ببیند، بقیه فقط pending_approval و رد نشده
    if request.user.is_superuser:
        allocation = get_object_or_404(Allocation, allocation_number=allocation_number, order=order, is_rejected=False)
    else:
        allocation = get_object_or_404(Allocation, allocation_number=allocation_number, order=order, is_rejected=False, allocation_status='pending_approval')

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
            
            # تغییر وضعیت تخصیص به 'pending_shipping' برای نشان دادن تأیید استعلام
            allocation.allocation_status = 'pending_shipping'
            allocation.save(update_fields=['allocation_status'])
            
            # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند (فقط تخصیص‌های رد نشده)
            allocations = Allocation.objects.filter(order=order, is_rejected=False)
            all_inquired = all(alloc.allocation_status == 'pending_shipping' for alloc in allocations)
            
            bug_logger.info(f"استعلام تخصیص {allocation_number} برای سفارش {order_number} تأیید شد و وضعیت به pending_shipping تغییر کرد")
            
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


@login_required
def reject_allocations_view(request, order_number):
    """
    رد تخصیص‌ها و ارجاع به مدیر
    - دریافت لیست تخصیص‌های مشکل‌دار و دلیل رد
    - علامت‌گذاری تخصیص‌ها به عنوان رد شده
    - حذف سفارش از لیست تأیید تخصیص
    """
    audit_logger.info(f"درخواست رد تخصیص‌های سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای رد تخصیص‌های سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به رد تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای رد تخصیص‌های سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_allocation_approval':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_allocation_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای رد تخصیص نیست.')
        return redirect('sales:approve_allocation_list')

    if request.method != 'POST':
        messages.error(request, 'درخواست نامعتبر.')
        return redirect('sales:approve_allocation_detail', order_number=order_number)
    
    try:
        with transaction.atomic():
            # دریافت داده‌های POST
            rejected_allocations = request.POST.getlist('rejected_allocations[]')
            rejection_reasons = {}
            
            for allocation_number in rejected_allocations:
                reason_key = f'rejection_reason_{allocation_number}'
                reason = request.POST.get(reason_key, '').strip()
                if reason:
                    rejection_reasons[allocation_number] = reason
            
            if not rejected_allocations:
                messages.error(request, 'لطفاً حداقل یک تخصیص را برای رد انتخاب کنید.')
                return redirect('sales:approve_allocation_detail', order_number=order_number)
            
            # علامت‌گذاری تخصیص‌ها به عنوان رد شده
            allocations_to_reject = Allocation.objects.filter(
                order=order,
                allocation_number__in=rejected_allocations
            )
            
            for allocation in allocations_to_reject:
                allocation.is_rejected = True
                allocation.rejection_reason = rejection_reasons.get(allocation.allocation_number, '')
                allocation.save(update_fields=['is_rejected', 'rejection_reason'])
            
            bug_logger.info(f"تخصیص‌های {rejected_allocations} برای سفارش {order_number} رد شدند")
            messages.success(request, f'{len(rejected_allocations)} تخصیص رد شد و به مدیر ارجاع داده شد.')
            audit_logger.activity(f"تخصیص‌های سفارش {order_number} رد شدند و به مدیر ارجاع داده شدند")
            
            return redirect('sales:approve_allocation_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در رد تخصیص‌های سفارش {order_number}: {str(e)}", exc_info=True)
        messages.error(request, f'خطا در رد تخصیص‌ها: {str(e)}')
        return redirect('sales:approve_allocation_detail', order_number=order_number)


@login_required
def manage_allocations_list_view(request):
    """
    لیست سفارش‌هایی که تخصیص‌هایشان رد شده است
    فقط superadmin می‌تواند ببیند
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های با تخصیص رد شده")
    
    if not request.user.is_superuser:
        audit_logger.activity("تلاش برای دسترسی به مدیریت تخصیص‌ها بدون دسترسی superadmin")
        messages.error(request, 'شما دسترسی به این بخش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت سفارش‌هایی که حداقل یک تخصیص رد شده دارند
    from core.OrderFolder.OrderItemModel import OrderItem
    
    orders_qs = Order.objects.filter(
        allocations__is_rejected=True
    ).distinct().select_related('customer', 'registered_by')
    
    # محاسبه مقدار سفارش
    order_total_subquery = OrderItem.objects.filter(
        order=OuterRef('pk')
    ).values('order').annotate(
        total=Sum(
            Case(
                When(weight_unit='kg', then=F('quantity')),
                When(weight_unit='ton', then=F('quantity') * 1000),
                When(
                    Q(weight_unit='bag') & Q(bag_weight__isnull=False),
                    then=F('quantity') * F('bag_weight')
                ),
                When(weight_unit='piece', then=F('quantity')),
                default=0,
                output_field=DecimalField(max_digits=15, decimal_places=3)
            )
        )
    ).values('total')[:1]
    
    orders_qs = orders_qs.annotate(
        order_total_quantity_kg=Subquery(order_total_subquery, output_field=DecimalField(max_digits=15, decimal_places=3))
    )
    
    # تعداد تخصیص‌های رد شده
    orders_qs = orders_qs.annotate(
        rejected_allocations_count=Count('allocations', filter=Q(allocations__is_rejected=True), distinct=True)
    )
    
    orders_qs = orders_qs.order_by('-created_at')
    
    context = {
        'orders': orders_qs,
        'page_title': 'مدیریت تخصیص‌های رد شده',
    }
    return render(request, 'allocation/manage_allocations_list.html', context)


@login_required
def manage_allocations_detail_view(request, order_number):
    """
    صفحه جزئیات مدیریت تخصیص‌های رد شده
    - نمایش همه تخصیص‌های سفارش
    - نمایش تخصیص‌های رد شده با دلیل
    - امکان ویرایش تخصیص‌ها
    - دکمه تأیید همه
    """
    audit_logger.info(f"درخواست مشاهده جزئیات مدیریت تخصیص‌های سفارش {order_number}")
    
    if not request.user.is_superuser:
        audit_logger.activity(f"تلاش برای دسترسی به مدیریت تخصیص‌های سفارش {order_number} بدون دسترسی superadmin")
        messages.error(request, 'شما دسترسی به این بخش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    order = get_object_or_404(Order, order_number=order_number)
    
    # دریافت همه تخصیص‌های سفارش
    allocations = Allocation.objects.filter(order=order).select_related('order').prefetch_related('product_infos__product')
    
    # بررسی اینکه آیا تخصیص رد شده‌ای وجود دارد
    has_rejected = allocations.filter(is_rejected=True).exists()
    
    if not has_rejected:
        messages.warning(request, 'این سفارش تخصیص رد شده‌ای ندارد.')
        return redirect('sales:manage_allocations_list')
    
    # محاسبه مقادیر
    order_total = calculate_order_total_quantity(order)
    allocation_total = calculate_allocation_total_quantity(order)
    is_balanced = abs(order_total - allocation_total) < 0.001
    difference = order_total - allocation_total
    
    # آماده‌سازی اطلاعات تخصیص‌ها
    allocations_with_info = []
    for allocation in allocations:
        delivery_info = None
        is_inquired = False
        
        if allocation.delivery_postal_code:
            delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
            if allocation.allocation_status == 'pending_shipping':
                is_inquired = True
        from decimal import Decimal
        allocation_quantity = Decimal('0')
        for product_info in allocation.product_infos.all():
            quantity = Decimal(str(product_info.quantity or 0))
            unit = product_info.unit
            if unit == 'kg':
                allocation_quantity += quantity
            elif unit == 'ton':
                allocation_quantity += quantity * 1000
            elif unit == 'gr':
                allocation_quantity += quantity / 1000
            else:
                allocation_quantity += quantity
        allocations_with_info.append({
            'allocation': allocation,
            'delivery_info': delivery_info,
            'is_inquired': is_inquired,
            'quantity': allocation_quantity,
            'product_infos': allocation.product_infos.all(),
        })
    # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند (فقط تخصیص‌های رد نشده)
    non_rejected_allocations = [item for item in allocations_with_info if not item['allocation'].is_rejected]
    all_inquired = all(item['is_inquired'] for item in non_rejected_allocations) if non_rejected_allocations else False
    
    context = {
        'order': order,
        'allocations_with_info': allocations_with_info,
        'order_total': order_total,
        'allocation_total': allocation_total,
        'is_balanced': is_balanced,
        'difference': difference,
        'all_inquired': all_inquired,
        'page_title': f'مدیریت تخصیص‌های رد شده - سفارش {order_number}',
    }
    return render(request, 'allocation/manage_allocations_detail.html', context)


@login_required
def approve_all_rejected_allocations_view(request, order_number):
    """
    تأیید همه تخصیص‌های رد شده بعد از ویرایش
    - حذف علامت رد از تخصیص‌ها
    - بررسی برابری مقادیر
    - اگر همه تخصیص‌ها تأیید شدند، سفارش به "در انتظار کارخانه" می‌رود
    """
    audit_logger.info(f"درخواست تأیید همه تخصیص‌های رد شده سفارش {order_number}")
    
    if not request.user.is_superuser:
        audit_logger.activity(f"تلاش برای تأیید تخصیص‌های رد شده سفارش {order_number} بدون دسترسی superadmin")
        messages.error(request, 'شما دسترسی به این بخش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    order = get_object_or_404(Order, order_number=order_number)
    
    try:
        with transaction.atomic():
            # بررسی برابری مقادیر قبل از تأیید
            order_total = calculate_order_total_quantity(order)
            allocation_total = calculate_allocation_total_quantity(order)
            is_balanced = abs(order_total - allocation_total) < 0.001
            
            if not is_balanced:
                difference = order_total - allocation_total
                bug_logger.warning(f"مقادیر سفارش {order_number} برابر نیست (سفارش: {order_total}, تخصیص: {allocation_total}, تفاوت: {difference})")
                messages.error(request, f'مقادیر تخصیص‌ها با سفارش برابر نیست. تفاوت: {difference:.2f} کیلوگرم. لطفاً ابتدا تخصیص‌ها را اصلاح کنید.')
                return redirect('sales:manage_allocations_detail', order_number=order_number)
            
            # دریافت همه تخصیص‌های رد شده
            rejected_allocations = Allocation.objects.filter(order=order, is_rejected=True)
            
            if not rejected_allocations.exists():
                messages.warning(request, 'این سفارش تخصیص رد شده‌ای ندارد.')
                return redirect('sales:manage_allocations_detail', order_number=order_number)
            
            # حذف علامت رد
            for allocation in rejected_allocations:
                allocation.is_rejected = False
                allocation.rejection_reason = ''
                allocation.save(update_fields=['is_rejected', 'rejection_reason'])
            
            # بررسی اینکه آیا همه تخصیص‌ها استعلام شده‌اند
            all_allocations = Allocation.objects.filter(order=order)
            all_inquired = all(alloc.allocation_status == 'pending_shipping' for alloc in all_allocations)
            
            if all_inquired:
                # تغییر وضعیت سفارش به "در انتظار کارخانه"
                order.status = 'pending_factory'
                order.save(update_fields=['status'])
                bug_logger.info(f"همه تخصیص‌های سفارش {order_number} تأیید شد و وضعیت به pending_factory تغییر کرد")
                messages.success(request, 'همه تخصیص‌ها تأیید شدند و سفارش به "در انتظار کارخانه" ارسال شد.')
            else:
                # تغییر وضعیت سفارش به "در انتظار تأیید تخصیص" برای ادامه فرآیند
                order.status = 'pending_allocation_approval'
                order.save(update_fields=['status'])
                messages.success(request, 'تخصیص‌ها تأیید شدند. لطفاً استعلام‌ها را نیز تأیید کنید.')
            
            audit_logger.activity(f"همه تخصیص‌های رد شده سفارش {order_number} تأیید شدند")
            return redirect('sales:manage_allocations_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در تأیید تخصیص‌های رد شده سفارش {order_number}: {str(e)}", exc_info=True)
        messages.error(request, f'خطا در تأیید تخصیص‌ها: {str(e)}')
        return redirect('sales:manage_allocations_detail', order_number=order_number)


@login_required
@require_http_methods(["POST"])
def delete_allocation_view(request, order_number, allocation_number):
    """
    حذف یک تخصیص
    فقط superadmin می‌تواند تخصیص را حذف کند
    """
    audit_logger.info(f"درخواست حذف تخصیص {allocation_number} برای سفارش {order_number}")
    
    if not request.user.is_superuser:
        audit_logger.activity(f"تلاش برای حذف تخصیص {allocation_number} بدون دسترسی superadmin")
        messages.error(request, 'شما دسترسی به این بخش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    order = get_object_or_404(Order, order_number=order_number)
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number, order=order)
    
    try:
        with transaction.atomic():
            # حذف تخصیص (product_infos به صورت خودکار حذف می‌شوند به دلیل CASCADE)
            allocation_number_str = allocation.allocation_number
            allocation.delete()
            
            # بررسی وضعیت سفارش
            remaining_allocations = Allocation.objects.filter(order=order).count()
            if remaining_allocations == 0:
                # اگر هیچ تخصیصی باقی نماند، وضعیت سفارش را به pending_allocation برگردان
                if order.status in ['pending_allocation_approval', 'pending_shipping']:
                    order.status = 'pending_allocation'
                    order.save(update_fields=['status'])
            
            audit_logger.activity(f"تخصیص {allocation_number_str} برای سفارش {order_number} حذف شد")
            messages.success(request, f'تخصیص {allocation_number_str} با موفقیت حذف شد.')
            return redirect('sales:manage_allocations_detail', order_number=order_number)
            
    except Exception as e:
        bug_logger.error(f"خطا در حذف تخصیص {allocation_number} برای سفارش {order_number}: {str(e)}", exc_info=True)
        messages.error(request, f'خطا در حذف تخصیص: {str(e)}')
        return redirect('sales:manage_allocations_detail', order_number=order_number)

