from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.TransportFolder.ProductInfoModel import ProductInfo
from core.AllocationFolder.AllocationModel import Allocation
from django.template.loader import render_to_string

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def exit_list_view(request):
    """
    لیست حمل‌های در انتظار خروج
    """
    audit_logger.info("درخواست مشاهده لیست حمل‌های در انتظار خروج")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_VIEW_EXIT_LIST.value):
        audit_logger.activity("تلاش برای دسترسی به لیست حمل‌های در انتظار خروج بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست حمل‌های در انتظار خروج را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت حمل‌های در انتظار خروج
    transports = Transport.objects.filter(
        status='pending_exit'
    ).select_related('driver').prefetch_related(
        'truck_infos', 'product_infos'
    ).order_by('-waybill_date', 'waybill_number')
    
    # آماده‌سازی اطلاعات حمل‌ها
    transports_with_info = []
    for transport in transports:
        # دریافت شماره سفارش
        order_number = None
        if transport.allocation_id:
            allocation = Allocation.objects.filter(allocation_number=transport.allocation_id).first()
            if allocation and allocation.order:
                order_number = allocation.order.order_number if hasattr(allocation.order, 'order_number') else None
        
        # دریافت اطلاعات کامیون
        truck_info = transport.truck_infos.first()
        plate_number = None
        if truck_info:
            plate_number = truck_info.plate_number
        
        # دریافت اطلاعات محصول
        product_info = transport.product_infos.first()
        product_name = None
        quantity = None
        if product_info:
            if product_info.product:
                product_name = product_info.product.name
            elif product_info.raw_material:
                product_name = product_info.raw_material.name
            # مقدار از وزن خالص استفاده می‌شود
            quantity = transport.net_weight
        
        transports_with_info.append({
            'transport': transport,
            'order_number': order_number or 'نامشخص',
            'allocation_id': transport.allocation_id or 'نامشخص',
            'plate_number': plate_number or 'نامشخص',
            'product_name': product_name or 'نامشخص',
            'quantity': quantity or 0,
        })
    
    bug_logger.debug(f"تعداد {len(transports_with_info)} حمل در انتظار خروج لود شد")
    
    context = {
        'transports_with_info': transports_with_info,
        'page_title': 'لیست حمل‌های در انتظار خروج',
    }
    return render(request, 'distribution/exit_list.html', context)


@login_required
def print_waybill_pdf_view(request, waybill_number):
    """
    چاپ PDF بارنامه
    """
    audit_logger.info(f"درخواست چاپ PDF بارنامه برای حمل {waybill_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_PRINT_WAYBILL_PDF.value):
        audit_logger.activity("تلاش برای چاپ PDF بارنامه بدون دسترسی")
        messages.error(request, 'شما دسترسی به چاپ PDF بارنامه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if transport.status != 'pending_exit':
        messages.error(request, 'این حمل در وضعیت مناسب برای چاپ بارنامه نیست.')
        return redirect('distribution:exit_list')
    
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        messages.error(request, "خطا: پکیج WeasyPrint به درستی نصب نشده است. لطفاً با مدیر سیستم تماس بگیرید.")
        return redirect('distribution:exit_list')
    
    try:
        bug_logger.debug(f"تولید PDF برای بارنامه {waybill_number}")
        
        # دریافت اطلاعات کامل
        truck_info = transport.truck_infos.first()
        product_info = transport.product_infos.first()
        allocation = None
        order = None
        if transport.allocation_id:
            allocation = Allocation.objects.filter(allocation_number=transport.allocation_id).first()
            if allocation:
                order = allocation.order
        
        # آماده‌سازی اطلاعات برای PDF
        context = {
            'transport': transport,
            'truck_info': truck_info,
            'product_info': product_info,
            'allocation': allocation,
            'order': order,
        }
        
        # رندر HTML
        html_string = render_to_string('distribution/waybill_pdf_template.html', context)
        
        # تبدیل به PDF
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        
        # کانفیگ فونت برای فارسی
        font_config = FontConfiguration()
        
        # CSS برای فونت وزیر
        css = CSS(string='''
            @font-face {
                font-family: 'Vazir';
                src: url('/static/fonts/Vazir-Regular.ttf') format('truetype');
            }
            @font-face {
                font-family: 'Vazir';
                font-weight: bold;
                src: url('/static/fonts/Vazir-Bold.ttf') format('truetype');
            }
            body {
                font-family: 'Vazir', Arial, sans-serif;
                direction: rtl;
                text-align: right;
            }
        ''', font_config=font_config)
        
        # تولید PDF
        pdf_file = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        # پاسخ HTTP
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="waybill_{waybill_number}.pdf"'
        
        bug_logger.info(f"PDF بارنامه {waybill_number} با موفقیت تولید شد")
        audit_logger.activity(f"PDF بارنامه {waybill_number} توسط کاربر {request.user.username} چاپ شد")
        
        return response
        
    except Exception as e:
        bug_logger.error(f"خطا در تولید PDF بارنامه: {str(e)}")
        messages.error(request, f'خطا در تولید PDF بارنامه: {str(e)}')
        return redirect('distribution:exit_list')


@login_required
def mark_vehicle_exited_view(request, waybill_number):
    """
    ثبت خروج خودرو - تغییر وضعیت حمل به تکمیل شده
    و بررسی تغییر وضعیت تخصیص و سفارش
    """
    audit_logger.info(f"درخواست ثبت خروج خودرو برای حمل {waybill_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_MARK_VEHICLE_EXITED.value):
        audit_logger.activity("تلاش برای ثبت خروج خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به ثبت خروج خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if transport.status != 'pending_exit':
        messages.error(request, 'این حمل در وضعیت مناسب برای ثبت خروج نیست.')
        return redirect('distribution:exit_list')
    
    try:
        with transaction.atomic():
            # تغییر وضعیت حمل به completed (تکمیل بارگیری)
            transport.status = 'completed'
            transport.save(update_fields=['status'])
            
            # بررسی تغییر وضعیت تخصیص
            if transport.allocation_id:
                allocation = Allocation.objects.filter(allocation_number=transport.allocation_id).first()
                if allocation:
                    # بررسی اینکه آیا همه حمل‌های تخصیص به completed رسیدند
                    all_transports = Transport.objects.filter(allocation_id=allocation.allocation_number)
                    all_transports_count = all_transports.count()
                    completed_transports_count = all_transports.filter(status='completed').count()
                    
                    # اگر همه حمل‌ها به completed رسیدند، تخصیص را به delivered ببر
                    if all_transports_count > 0 and all_transports_count == completed_transports_count:
                        allocation.allocation_status = 'delivered'
                        allocation.save(update_fields=['allocation_status'])
                        bug_logger.info(f"وضعیت تخصیص {allocation.allocation_number} به 'تحویل شده' تغییر کرد")
                        
                        # بررسی تغییر وضعیت سفارش
                        if allocation.order:
                            order = allocation.order
                            # دریافت همه تخصیص‌های سفارش
                            relevant_allocations = Allocation.objects.filter(
                                order=order
                            ).exclude(
                                allocation_status__in=['planned', 'pending_approval', 'pending_shipping', 'canceled']
                            )
                            
                            # فقط تخصیص‌هایی که حداقل یک حمل دارند را بررسی می‌کنیم
                            allocations_with_transports = []
                            for alloc in relevant_allocations:
                                alloc_transports = Transport.objects.filter(allocation_id=alloc.allocation_number)
                                if alloc_transports.exists():
                                    allocations_with_transports.append(alloc)
                            
                            # بررسی اینکه آیا همه تخصیص‌های دارای حمل به delivered رسیدند
                            if allocations_with_transports:
                                all_delivered = all(
                                    alloc.allocation_status == 'delivered' 
                                    for alloc in allocations_with_transports
                                )
                                
                                if all_delivered:
                                    order.status = 'pending_unloading_approval'
                                    order.save(update_fields=['status'])
                                    bug_logger.info(f"وضعیت سفارش {order.order_number if hasattr(order, 'order_number') else 'نامشخص'} به 'در انتظار تایید تخلیه' تغییر کرد")
                                    audit_logger.activity(f"وضعیت سفارش {order.order_number if hasattr(order, 'order_number') else 'نامشخص'} به 'در انتظار تایید تخلیه' تغییر کرد")
            
            bug_logger.info(f"خروج خودرو برای حمل {waybill_number} ثبت شد")
            messages.success(request, f'خروج خودرو برای حمل {waybill_number} با موفقیت ثبت شد.')
            audit_logger.activity(f"خروج خودرو برای حمل {waybill_number} ثبت شد توسط کاربر {request.user.username}")
            
            return redirect('distribution:exit_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در ثبت خروج خودرو: {str(e)}")
        messages.error(request, f'خطا در ثبت خروج خودرو: {str(e)}')
        return redirect('distribution:exit_list')

