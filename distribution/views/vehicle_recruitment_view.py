from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.AllocationFolder.AllocationModel import Allocation
from core.OrderFolder.OrderModel import Order
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.PersonModel import Person
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TransportAttachmentModel import TransportAttachment
from core.TransportFolder.LoadingScheduleInfoModel import LoadingScheduleInfo
from core.TransportFolder.TruckInfoModel import TruckInfo
from django.contrib.contenttypes.models import ContentType
from sales.views.allocation_list_view import get_delivery_address_info

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def vehicle_recruitment_list_view(request):
    """
    لیست تخصیص‌های در انتظار جذب خودرو
    """
    audit_logger.info("درخواست مشاهده لیست تخصیص‌های در انتظار جذب خودرو")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_RECRUIT_VEHICLE.value):
        audit_logger.activity("تلاش برای دسترسی به لیست جذب خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به جذب خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت تخصیص‌های در انتظار جذب خودرو
    allocations = Allocation.objects.filter(
        allocation_status='pending_vehicle_recruitment'
    ).select_related('order', 'order__customer').prefetch_related(
        'product_infos__product'
    ).order_by('-allocation_priority', '-created_at')
    
    # آماده‌سازی اطلاعات تخصیص‌ها
    allocations_with_info = []
    for allocation in allocations:
        # دریافت اطلاعات آدرس تحویل
        delivery_info = None
        if allocation.delivery_postal_code:
            delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
        
        # شمارش تعداد حمل‌های ایجاد شده برای این تخصیص
        transports_count = Transport.objects.filter(
            allocation_id=allocation.allocation_number
        ).count()
        
        allocations_with_info.append({
            'allocation': allocation,
            'order_number': allocation.order.order_number if allocation.order else '-',
            'delivery_info': delivery_info,
            'transports_count': transports_count,
        })
    
    bug_logger.debug(f"تعداد {len(allocations_with_info)} تخصیص در انتظار جذب خودرو لود شد")
    
    context = {
        'allocations_with_info': allocations_with_info,
        'page_title': 'لیست تخصیص‌های در انتظار جذب خودرو',
    }
    return render(request, 'distribution/vehicle_recruitment_list.html', context)


@login_required
def create_transport_view(request, allocation_number):
    """
    ایجاد حمل جدید برای یک تخصیص
    """
    audit_logger.info(f"درخواست ایجاد حمل برای تخصیص {allocation_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_RECRUIT_VEHICLE.value):
        audit_logger.activity("تلاش برای ایجاد حمل بدون دسترسی")
        messages.error(request, 'شما دسترسی به جذب خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number)
    
    if allocation.allocation_status != 'pending_vehicle_recruitment':
        messages.error(request, 'این تخصیص در وضعیت مناسب برای جذب خودرو نیست.')
        return redirect('distribution:vehicle_recruitment_list')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # دریافت داده‌های فرم
                waybill_number = request.POST.get('waybill_number')
                carrier_recruitment = request.POST.get('carrier_recruitment')
                vehicle_type_official = request.POST.get('vehicle_type_official')
                driver_national_id = request.POST.get('driver_national_id', '').strip()
                driver_name = request.POST.get('driver_name', '').strip()
                driver_mobile = request.POST.get('driver_mobile', '').strip()
                driver_description = request.POST.get('driver_description', '').strip()
                
                # اعتبارسنجی داده‌های اجباری
                if not waybill_number:
                    messages.error(request, 'شماره بارنامه الزامی است.')
                    return redirect('distribution:vehicle_recruitment_list')
                
                if not carrier_recruitment:
                    messages.error(request, 'باربری جذب الزامی است.')
                    return redirect('distribution:vehicle_recruitment_list')
                
                if not vehicle_type_official:
                    messages.error(request, 'نوع ماشین الزامی است.')
                    return redirect('distribution:vehicle_recruitment_list')
                
                # بررسی تکراری نبودن شماره بارنامه
                if Transport.objects.filter(waybill_number=waybill_number).exists():
                    messages.error(request, 'شماره بارنامه تکراری است.')
                    return redirect('distribution:vehicle_recruitment_list')
                
                # ایجاد یا به‌روزرسانی Person برای راننده (اگر اطلاعات راننده داده شده)
                driver_person = None
                if driver_national_id:
                    driver_person, created = Person.objects.get_or_create(
                        national_id=driver_national_id,
                        defaults={
                            'name': driver_name or None,
                            'type': 'driver',
                            'description': driver_description or None,
                        }
                    )
                    # به‌روزرسانی اطلاعات اگر Person از قبل وجود داشت
                    if not created:
                        if driver_name:
                            driver_person.name = driver_name
                        if driver_description:
                            driver_person.description = driver_description
                        driver_person.type = 'driver'
                        driver_person.save()
                    
                    # اضافه کردن شماره همراه به PhoneNumber
                    if driver_mobile:
                        person_content_type = ContentType.objects.get_for_model(Person)
                        phone_number, created = PhoneNumber.objects.get_or_create(
                            content_type=person_content_type,
                            object_id=driver_person.national_id,
                            phone_type='mobile',
                            defaults={'number': driver_mobile, 'is_primary': True}
                        )
                        if not created:
                            phone_number.number = driver_mobile
                            phone_number.save()
                
                # ایجاد حمل
                transport = Transport.objects.create(
                    waybill_number=waybill_number,
                    allocation_id=allocation.allocation_number,
                    delivery_postal_code=allocation.delivery_postal_code,
                    direction='outbound',
                    carrier_recruitment=carrier_recruitment,
                    vehicle_type_official=vehicle_type_official,
                    driver=driver_person,
                    status='pending_vehicle_entry',
                )
                
                # ایجاد LoadingScheduleInfo
                LoadingScheduleInfo.objects.create(
                    transport=transport
                )
                
                # پردازش فایل‌های پیوست (کارت ملی و روزنامه رسمی)
                national_card_file = request.FILES.get('national_card_file')
                official_gazette_file = request.FILES.get('official_gazette_file')
                
                if national_card_file:
                    TransportAttachment.objects.create(
                        transport=transport,
                        attachment_type='national_card',
                        file=national_card_file
                    )
                
                if official_gazette_file:
                    TransportAttachment.objects.create(
                        transport=transport,
                        attachment_type='official_gazette',
                        file=official_gazette_file
                    )
                
                bug_logger.info(f"حمل {waybill_number} برای تخصیص {allocation_number} ایجاد شد")
                messages.success(request, f'حمل {waybill_number} با موفقیت ایجاد شد.')
                audit_logger.activity(f"حمل {waybill_number} برای تخصیص {allocation_number} ایجاد شد توسط کاربر {request.user.username}")
                
                return redirect('distribution:vehicle_recruitment_list')
                
        except Exception as e:
            bug_logger.error(f"خطا در ایجاد حمل: {str(e)}")
            messages.error(request, f'خطا در ایجاد حمل: {str(e)}')
            return redirect('distribution:vehicle_recruitment_list')
    
    # برای GET request، اطلاعات تخصیص را برمی‌گردانیم (برای AJAX)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        delivery_info = None
        if allocation.delivery_postal_code:
            delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
        
        return JsonResponse({
            'allocation_number': allocation.allocation_number,
            'order_number': allocation.order.order_number if allocation.order else '-',
            'delivery_info': delivery_info,
        })
    
    # در غیر این صورت به لیست برگرد
    return redirect('distribution:vehicle_recruitment_list')


@login_required
def complete_vehicle_recruitment_view(request, allocation_number):
    """
    تکمیل جذب خودرو برای یک تخصیص
    """
    audit_logger.info(f"درخواست تکمیل جذب خودرو برای تخصیص {allocation_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_RECRUIT_VEHICLE.value):
        audit_logger.activity("تلاش برای تکمیل جذب خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به جذب خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number)
    
    if allocation.allocation_status != 'pending_vehicle_recruitment':
        messages.error(request, 'این تخصیص در وضعیت مناسب برای تکمیل جذب خودرو نیست.')
        return redirect('distribution:vehicle_recruitment_list')
    
    # بررسی اینکه حداقل یک حمل وجود دارد
    transports = Transport.objects.filter(allocation_id=allocation.allocation_number)
    if not transports.exists():
        messages.error(request, 'برای تکمیل جذب خودرو، حداقل باید یک حمل ایجاد شده باشد.')
        return redirect('distribution:vehicle_recruitment_list')
    
    try:
        with transaction.atomic():
            # تغییر وضعیت همه حمل‌ها به pending_vehicle_entry
            transports.update(status='pending_vehicle_entry')
            
            # ثبت زمان جذب خودرو در LoadingScheduleInfo
            now = timezone.now()
            for transport in transports:
                schedule_info, created = LoadingScheduleInfo.objects.get_or_create(
                    transport=transport
                )
                schedule_info.vehicle_attraction_time = now
                schedule_info.save(update_fields=['vehicle_attraction_time'])
            
            # بررسی اینکه آیا همه حمل‌های تخصیص به pending_vehicle_entry رسیدند
            all_transports = Transport.objects.filter(allocation_id=allocation.allocation_number)
            all_transports_count = all_transports.count()
            pending_entry_transports_count = all_transports.filter(status='pending_vehicle_entry').count()
            
            # اگر همه حمل‌ها به pending_vehicle_entry رسیدند، تخصیص را هم به این وضعیت ببر
            if all_transports_count > 0 and all_transports_count == pending_entry_transports_count:
                allocation.allocation_status = 'pending_vehicle_entry'
                allocation.save(update_fields=['allocation_status'])
                bug_logger.info(f"وضعیت تخصیص {allocation_number} به 'در انتظار ورود خودرو به کارخانه' تغییر کرد")
                
                # بررسی اینکه آیا همه تخصیص‌های سفارش به pending_vehicle_entry رسیدند
                if allocation.order:
                    order = allocation.order
                    # دریافت همه تخصیص‌های سفارش که باید حمل داشته باشند
                    # (تخصیص‌هایی که در وضعیت pending_vehicle_recruitment یا بعد از آن هستند)
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
                    
                    # بررسی اینکه آیا همه تخصیص‌های دارای حمل به pending_vehicle_entry رسیدند
                    if allocations_with_transports:
                        all_pending_entry = all(
                            alloc.allocation_status == 'pending_vehicle_entry' 
                            for alloc in allocations_with_transports
                        )
                        
                        if all_pending_entry:
                            order.status = 'pending_vehicle_entry'
                            order.save(update_fields=['status'])
                            bug_logger.info(f"وضعیت سفارش {order.order_number} به 'در انتظار ورود خودرو به کارخانه' تغییر کرد")
                            audit_logger.activity(f"وضعیت سفارش {order.order_number} به 'در انتظار ورود خودرو به کارخانه' تغییر کرد")
            
            bug_logger.info(f"جذب خودرو برای تخصیص {allocation_number} تکمیل شد")
            messages.success(request, f'جذب خودرو برای تخصیص {allocation_number} با موفقیت تکمیل شد.')
            audit_logger.activity(f"جذب خودرو برای تخصیص {allocation_number} تکمیل شد توسط کاربر {request.user.username}")
            
            return redirect('distribution:vehicle_recruitment_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در تکمیل جذب خودرو: {str(e)}")
        messages.error(request, f'خطا در تکمیل جذب خودرو: {str(e)}')
        return redirect('distribution:vehicle_recruitment_list')

