from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig
import jdatetime
from datetime import datetime

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.ApprovalInfoModel import ApprovalInfo
from core.AllocationFolder.AllocationModel import Allocation
from core.TransportFolder.TransportModel import Transport
from sales.forms.unload_approval_form import UnloadApprovalForm
from sales.tables.tables_settlement import UnloadApprovalOrderTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def unload_approval_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تایید تخلیه»
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تایید تخلیه")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_UNLOAD.value):
        audit_logger.activity("تلاش برای مشاهده لیست تایید تخلیه بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید تخلیه سفارش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_unloading_approval').select_related('customer').order_by('-created_at')

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار تایید تخلیه لود شد")

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = {
        'order_number': True,
        'customer': True,
        'allocations': True,
        'transports': True,
        'actions': True,
    }
    
    # ایجاد جدول با django-tables2
    table = UnloadApprovalOrderTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'سفارش‌های در انتظار تایید تخلیه',
    }
    return render(request, 'unload_approval/unload_approval_list.html', context)


@login_required
def unload_approval_detail_view(request, order_number):
    """
    تایید تخلیه سفارش
    """
    audit_logger.info(f"درخواست تایید تخلیه برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_UNLOAD.value):
        audit_logger.activity(f"تلاش برای تایید تخلیه سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تایید تخلیه سفارش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if order.status != 'pending_unloading_approval':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_unloading_approval می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تایید تخلیه نیست.')
        return redirect('sales:unload_approval_list')

    # دریافت تخصیص‌های سفارش
    allocations = Allocation.objects.filter(order=order).order_by('allocation_number')
    
    # دریافت حمل‌های مرتبط با تخصیص‌ها
    transports = Transport.objects.filter(allocation__in=allocations).select_related('driver', 'allocation').prefetch_related('truck_infos', 'product_infos').order_by('waybill_number')
    
    # آماده‌سازی اطلاعات برای نمایش
    allocations_with_transports = []
    for allocation in allocations:
        alloc_transports = transports.filter(allocation=allocation)
        allocations_with_transports.append({
            'allocation': allocation,
            'transports': alloc_transports,
        })
    
    if request.method == 'POST':
        form = UnloadApprovalForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # دریافت داده‌های فرم
                    unload_approval_date = form.cleaned_data['unload_approval_time']
                    customer_feedback = form.cleaned_data.get('customer_feedback', '').strip()
                    
                    # تبدیل تاریخ میلادی به شمسی با datetime کامل
                    if isinstance(unload_approval_date, datetime):
                        # اگر datetime است
                        j_datetime = jdatetime.datetime.fromgregorian(datetime=unload_approval_date)
                    else:
                        # اگر date است، زمان فعلی را اضافه می‌کنیم
                        now = datetime.now()
                        unload_approval_datetime = datetime.combine(unload_approval_date, now.time())
                        j_datetime = jdatetime.datetime.fromgregorian(datetime=unload_approval_datetime)
                    
                    # ایجاد یا به‌روزرسانی ApprovalInfo
                    approval_info, created = ApprovalInfo.objects.get_or_create(
                        order=order,
                        defaults={
                            'unload_approval_time': j_datetime,
                            'customer_feedback': customer_feedback,
                        }
                    )
                    
                    if not created:
                        approval_info.unload_approval_time = j_datetime
                        approval_info.customer_feedback = customer_feedback
                        approval_info.save(update_fields=['unload_approval_time', 'customer_feedback'])
                    
                    # تغییر وضعیت سفارش به pending_settlement (در انتظار تسویه)
                    order.status = 'pending_settlement'
                    order.save(update_fields=['status'])
                    
                    bug_logger.info(f"تایید تخلیه برای سفارش {order_number} ثبت شد و به وضعیت 'در انتظار تسویه' تغییر کرد")
                    messages.success(request, f'تایید تخلیه برای سفارش {order_number} با موفقیت ثبت شد. سفارش در حال حاضر در وضعیت «در انتظار تسویه» قرار دارد.')
                    audit_logger.activity(f"تایید تخلیه برای سفارش {order_number} ثبت شد و به وضعیت 'در انتظار تسویه' تغییر کرد توسط کاربر {request.user.username}")
                    
                    return redirect('sales:unload_approval_list')
                    
            except Exception as e:
                bug_logger.error(f"خطا در تایید تخلیه: {str(e)}")
                messages.error(request, f'خطا در تایید تخلیه: {str(e)}')
        else:
            # نمایش خطاهای فرم
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # برای GET request، فرم را با مقداردهی اولیه پر می‌کنیم
        initial_data = {}
        
        # دریافت ApprovalInfo موجود
        approval_info = ApprovalInfo.objects.filter(order=order).first()
        if approval_info and approval_info.unload_approval_time:
            # تبدیل jDateTimeField به تاریخ میلادی برای نمایش در فرم
            if isinstance(approval_info.unload_approval_time, jdatetime.datetime):
                g_datetime = approval_info.unload_approval_time.togregorian()
                initial_data['unload_approval_time'] = g_datetime.date()
            elif isinstance(approval_info.unload_approval_time, jdatetime.date):
                g_date = approval_info.unload_approval_time.togregorian()
                initial_data['unload_approval_time'] = g_date
        
        form = UnloadApprovalForm(initial=initial_data)
    
    context = {
        'form': form,
        'order': order,
        'allocations_with_transports': allocations_with_transports,
        'page_title': f'تایید تخلیه - سفارش {order.order_number}',
    }
    return render(request, 'unload_approval/unload_approval_detail.html', context)

