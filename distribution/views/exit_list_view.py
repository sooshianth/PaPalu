from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django_tables2 import RequestConfig
import logging
import os
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.TransportFolder.ProductInfoModel import ProductInfo
from core.TransportFolder.TransportAttachmentModel import TransportAttachment
from core.AllocationFolder.AllocationModel import Allocation
from distribution.exit_table import ExitTable

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
    ).select_related('driver', 'allocation', 'allocation__order').prefetch_related(
        'truck_infos', 'product_infos'
    ).order_by('-waybill_date', 'waybill_number')
    
    # آماده‌سازی اطلاعات حمل‌ها برای جدول
    # استفاده از یک class ساده که transport و اطلاعات مرتبط را نگه می‌دارد
    class TransportRow:
        def __init__(self, transport):
            self.transport = transport
            
            # دریافت شماره سفارش
            order_number = None
            if transport.allocation:
                allocation = transport.allocation
                if allocation and allocation.order:
                    order_number = allocation.order.order_number if hasattr(allocation.order, 'order_number') else None
            
            self.order_number = order_number or 'نامشخص'
            
            # دریافت شناسه تخصیص
            self.allocation_id = transport.allocation.allocation_number if transport.allocation else 'نامشخص'
            
            # دریافت اطلاعات کامیون
            truck_info = transport.truck_infos.first()
            plate_number = None
            if truck_info:
                plate_number = truck_info.plate_number
            
            self.plate_number = plate_number or 'نامشخص'
            
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
            
            self.product_name = product_name or 'نامشخص'
            self.quantity = quantity or 0
        
        def __getattr__(self, name):
            # اگر attribute در self وجود نداشت، از transport بگیر
            if hasattr(self.transport, name):
                return getattr(self.transport, name)
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    transports_data = [TransportRow(transport) for transport in transports]
    
    # ایجاد جدول
    table = ExitTable(transports_data)
    
    # تنظیم صفحه‌بندی
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    bug_logger.debug(f"تعداد {len(transports_data)} حمل در انتظار خروج لود شد")
    
    context = {
        'table': table,
        'page_title': 'لیست حمل‌های در انتظار خروج',
    }
    return render(request, 'distribution/exit_list.html', context)


@login_required
def print_waybill_pdf_view(request, waybill_number):
    """
    دانلود فایل پیوست بارنامه
    """
    audit_logger.info(f"درخواست دانلود فایل بارنامه برای حمل {waybill_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_PRINT_WAYBILL_PDF.value):
        audit_logger.activity("تلاش برای دانلود فایل بارنامه بدون دسترسی")
        messages.error(request, 'شما دسترسی به دانلود فایل بارنامه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if transport.status != 'pending_exit':
        messages.error(request, 'این حمل در وضعیت مناسب برای دانلود بارنامه نیست.')
        return redirect('distribution:exit_list')
    
    try:
        # جستجوی فایل پیوست بارنامه
        waybill_attachment = transport.attachments.filter(
            attachment_type='official_gazette'
        ).first()
        
        if not waybill_attachment or not waybill_attachment.file:
            messages.error(request, 'فایل بارنامه برای این حمل یافت نشد.')
            bug_logger.warning(f"فایل بارنامه برای حمل {waybill_number} یافت نشد")
            return redirect('distribution:exit_list')
        
        # بررسی وجود فایل در سیستم فایل
        if not os.path.exists(waybill_attachment.file.path):
            messages.error(request, 'فایل بارنامه در سیستم فایل یافت نشد.')
            bug_logger.error(f"فایل بارنامه در مسیر {waybill_attachment.file.path} یافت نشد")
            return redirect('distribution:exit_list')
        
        # استخراج پسوند فایل اصلی
        original_filename = os.path.basename(waybill_attachment.file.name)
        file_extension = os.path.splitext(original_filename)[1] or '.pdf'  # پیش‌فرض .pdf اگر پسوند نداشت
        
        # ساخت نام فایل بر اساس شماره بارنامه
        filename = f"waybill_{waybill_number}{file_extension}"
        
        # تعیین نوع محتوا بر اساس پسوند فایل
        content_type = 'application/pdf'  # پیش‌فرض
        if file_extension.lower() == '.pdf':
            content_type = 'application/pdf'
        elif file_extension.lower() in ('.jpg', '.jpeg'):
            content_type = 'image/jpeg'
        elif file_extension.lower() == '.png':
            content_type = 'image/png'
        
        # باز کردن فایل و ارسال آن
        file_response = FileResponse(
            waybill_attachment.file.open('rb'),
            content_type=content_type
        )
        file_response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        bug_logger.info(f"فایل بارنامه {waybill_number} با موفقیت دانلود شد")
        audit_logger.activity(f"فایل بارنامه {waybill_number} توسط کاربر {request.user.username} دانلود شد")
        
        return file_response
        
    except Exception as e:
        bug_logger.error(f"خطا در دانلود فایل بارنامه: {str(e)}")
        messages.error(request, f'خطا در دانلود فایل بارنامه: {str(e)}')
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
            if transport.allocation:
                allocation = transport.allocation
                # بررسی اینکه آیا همه حمل‌های تخصیص به completed رسیدند
                all_transports = Transport.objects.filter(allocation=allocation)
                all_transports_count = all_transports.count()
                completed_transports = all_transports.filter(status='completed')
                completed_count = completed_transports.count()
                
                # اگر همه حمل‌ها به completed رسیدند و تخصیص هنوز completed نیست، آن را به completed ببر
                if all_transports_count > 0 and all_transports_count == completed_count:
                    if allocation.allocation_status != 'completed':
                        allocation.allocation_status = 'completed'
                        allocation.save(update_fields=['allocation_status'])
                        bug_logger.info(f"وضعیت تخصیص {allocation.allocation_number} به 'تکمیل شده' تغییر کرد")
                        audit_logger.activity(f"وضعیت تخصیص {allocation.allocation_number} به 'تکمیل شده' تغییر کرد")
                    
                    # بررسی تغییر وضعیت سفارش
                    if allocation.order:
                        order = allocation.order
                        # دریافت همه تخصیص‌های مرتبط سفارش (تخصیص‌هایی که در فرآیند هستند)
                        relevant_allocations = Allocation.objects.filter(
                            order=order
                        ).exclude(
                            allocation_status__in=['planned', 'pending_approval', 'pending_shipping', 'canceled']
                        )
                        
                        # بررسی اینکه آیا همه تخصیص‌های مرتبط به completed رسیدند
                        if relevant_allocations.exists():
                            all_completed = all(
                                alloc.allocation_status == 'completed' 
                                for alloc in relevant_allocations
                            )
                            
                            if all_completed:
                                order.status = 'pending_unloading_approval'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"وضعیت سفارش {order.order_number if hasattr(order, 'order_number') else 'نامشخص'} به 'در انتظار تایید تسویه' تغییر کرد")
                                audit_logger.activity(f"وضعیت سفارش {order.order_number if hasattr(order, 'order_number') else 'نامشخص'} به 'در انتظار تایید تسویه' تغییر کرد")
            
            bug_logger.info(f"خروج خودرو برای حمل {waybill_number} ثبت شد")
            messages.success(request, f'خروج خودرو برای حمل {waybill_number} با موفقیت ثبت شد.')
            audit_logger.activity(f"خروج خودرو برای حمل {waybill_number} ثبت شد توسط کاربر {request.user.username}")
            
            return redirect('distribution:exit_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در ثبت خروج خودرو: {str(e)}")
        messages.error(request, f'خطا در ثبت خروج خودرو: {str(e)}')
        return redirect('distribution:exit_list')

