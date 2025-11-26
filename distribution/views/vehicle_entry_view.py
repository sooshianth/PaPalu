from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TransportAttachmentModel import TransportAttachment
from core.TransportFolder.LoadingScheduleInfoModel import LoadingScheduleInfo
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.AllocationFolder.AllocationModel import Allocation
from django.contrib.contenttypes.models import ContentType
from access.helpers import check_field_access_prefer_edit
import re

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_person_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Person"""
    if user.is_superuser:
        return {'name': True, 'national_id': True, 'description': True}
    
    accessible_fields = {}
    accessible_fields['name'] = check_field_access_prefer_edit(user, Person, 'name')
    accessible_fields['national_id'] = check_field_access_prefer_edit(user, Person, 'national_id')
    accessible_fields['description'] = check_field_access_prefer_edit(user, Person, 'description')
    return accessible_fields


def get_accessible_truck_info_fields(user):
    """بررسی دسترسی کاربر به فیلدهای TruckInfo"""
    if user.is_superuser:
        return {'plate_number': True, 'vehicle_type': True, 'loading_type': True}
    
    from core.TransportFolder.TruckInfoModel import TruckInfo
    
    accessible_fields = {}
    accessible_fields['plate_number'] = check_field_access_prefer_edit(user, TruckInfo, 'plate_number')
    accessible_fields['vehicle_type'] = check_field_access_prefer_edit(user, TruckInfo, 'vehicle_type')
    accessible_fields['loading_type'] = check_field_access_prefer_edit(user, TruckInfo, 'loading_type')
    return accessible_fields


@login_required
def vehicle_entry_list_view(request):
    """
    لیست حمل‌های در انتظار ورود به کارخانه
    """
    audit_logger.info("درخواست مشاهده لیست حمل‌های در انتظار ورود به کارخانه")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_VIEW_VEHICLE_ENTRY_LIST.value):
        audit_logger.activity("تلاش برای دسترسی به لیست ورود خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست ورود خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت حمل‌های در انتظار ورود به کارخانه
    transports = Transport.objects.filter(
        status='pending_vehicle_entry'
    ).select_related('driver').prefetch_related(
        'truck_infos'
    ).order_by('-waybill_date', 'waybill_number')
    
    # آماده‌سازی اطلاعات حمل‌ها
    transports_with_info = []
    for transport in transports:
        # دریافت اطلاعات راننده
        driver_name = None
        driver_national_id = None
        driver_mobile = None
        if transport.driver:
            driver_name = transport.driver.name
            driver_national_id = transport.driver.national_id
            # دریافت شماره همراه راننده
            person_content_type = ContentType.objects.get_for_model(Person)
            mobile_phone = PhoneNumber.objects.filter(
                content_type=person_content_type,
                object_id=transport.driver.national_id,
                phone_type='mobile'
            ).first()
            if mobile_phone:
                driver_mobile = mobile_phone.number
        
        # دریافت اطلاعات کامیون
        truck_info = transport.truck_infos.first()
        plate_number = None
        vehicle_type = None
        loading_type = None
        if truck_info:
            plate_number = truck_info.plate_number
            vehicle_type = truck_info.get_vehicle_type_display() if truck_info.vehicle_type else None
            loading_type = truck_info.get_loading_type_display() if truck_info.loading_type else None
        
        # بررسی کامل بودن اطلاعات
        is_complete = bool(
            driver_national_id and 
            driver_name and 
            driver_mobile and 
            plate_number
        )
        
        transports_with_info.append({
            'transport': transport,
            'driver_name': driver_name,
            'driver_national_id': driver_national_id,
            'driver_mobile': driver_mobile,
            'plate_number': plate_number,
            'vehicle_type': vehicle_type,
            'loading_type': loading_type,
            'is_complete': is_complete,
        })
    
    # بررسی دسترسی فیلدها
    accessible_person_fields = get_accessible_person_fields(request.user)
    accessible_truck_info_fields = get_accessible_truck_info_fields(request.user)
    
    bug_logger.debug(f"تعداد {len(transports_with_info)} حمل در انتظار ورود به کارخانه لود شد")
    
    context = {
        'transports_with_info': transports_with_info,
        'accessible_person_fields': accessible_person_fields,
        'accessible_truck_info_fields': accessible_truck_info_fields,
        'page_title': 'لیست حمل‌های در انتظار ورود به کارخانه',
    }
    return render(request, 'distribution/vehicle_entry_list.html', context)


@login_required
def register_vehicle_entry_view(request, waybill_number):
    """
    ثبت ورود خودرو به کارخانه
    """
    audit_logger.info(f"درخواست ثبت ورود خودرو برای حمل {waybill_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_REGISTER_VEHICLE_ENTRY.value):
        audit_logger.activity("تلاش برای ثبت ورود خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به ثبت ورود خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if transport.status != 'pending_vehicle_entry':
        messages.error(request, 'این حمل در وضعیت مناسب برای ثبت ورود نیست.')
        return redirect('distribution:vehicle_entry_list')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # دریافت داده‌های فرم
                driver_national_id = request.POST.get('driver_national_id', '').strip()
                driver_name = request.POST.get('driver_name', '').strip()
                driver_mobile = request.POST.get('driver_mobile', '').strip()
                driver_description = request.POST.get('driver_description', '').strip()
                
                # اطلاعات پلاک
                plate_part1 = request.POST.get('plate_part1', '').strip()
                plate_part2 = request.POST.get('plate_part2', '').strip()
                plate_part3 = request.POST.get('plate_part3', '').strip()
                
                vehicle_type = request.POST.get('vehicle_type', '').strip()
                loading_type = request.POST.get('loading_type', '').strip()
                
                # اعتبارسنجی داده‌های اجباری
                if not driver_national_id:
                    messages.error(request, 'شماره ملی راننده الزامی است.')
                    return redirect('distribution:vehicle_entry_list')
                
                # اعتبارسنجی شماره ملی (10 رقم)
                if not re.match(r'^\d{10}$', driver_national_id):
                    messages.error(request, 'شماره ملی باید 10 رقم باشد.')
                    return redirect('distribution:vehicle_entry_list')
                
                if not driver_name:
                    messages.error(request, 'نام راننده الزامی است.')
                    return redirect('distribution:vehicle_entry_list')
                
                if not driver_mobile:
                    messages.error(request, 'شماره همراه راننده الزامی است.')
                    return redirect('distribution:vehicle_entry_list')
                
                # اعتبارسنجی شماره همراه (09XXXXXXXXX)
                if not re.match(r'^09\d{9}$', driver_mobile):
                    messages.error(request, 'شماره همراه باید با فرمت 09XXXXXXXXX باشد.')
                    return redirect('distribution:vehicle_entry_list')
                
                # اعتبارسنجی پلاک
                if not plate_part1 or not plate_part2 or not plate_part3:
                    messages.error(request, 'تمام بخش‌های پلاک الزامی است.')
                    return redirect('distribution:vehicle_entry_list')
                
                # ساخت پلاک کامل
                plate_number = f"{plate_part1}|{plate_part2}|{plate_part3}"
                
                # اعتبارسنجی فایل کارت ملی
                national_card_file = request.FILES.get('national_card_file')
                if not national_card_file:
                    messages.error(request, 'آپلود کارت ملی الزامی است.')
                    return redirect('distribution:vehicle_entry_list')
                
                # بررسی فرمت فایل
                allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
                file_name = national_card_file.name.lower()
                if '.' in file_name:
                    file_extension = '.' + file_name.split('.')[-1]
                else:
                    file_extension = ''
                if file_extension not in allowed_extensions:
                    messages.error(request, 'فرمت فایل کارت ملی باید JPG، PNG یا PDF باشد.')
                    return redirect('distribution:vehicle_entry_list')
                
                # ایجاد یا به‌روزرسانی Person برای راننده
                driver_person, created = Person.objects.get_or_create(
                    national_id=driver_national_id,
                    defaults={
                        'name': driver_name,
                        'type': 'driver',
                        'description': driver_description or None,
                    }
                )
                
                # به‌روزرسانی اطلاعات اگر Person از قبل وجود داشت
                if not created:
                    driver_person.name = driver_name
                    if driver_description:
                        driver_person.description = driver_description
                    driver_person.type = 'driver'
                    driver_person.save()
                
                # اضافه یا به‌روزرسانی شماره همراه
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
                
                # به‌روزرسانی حمل با راننده
                transport.driver = driver_person
                transport.save()
                
                # بررسی تکراری نبودن پلاک برای حمل‌های دیگر
                existing_truck_other = TruckInfo.objects.filter(plate_number=plate_number).exclude(transport=transport).first()
                if existing_truck_other:
                    messages.error(request, 'این پلاک قبلاً برای حمل دیگری ثبت شده است.')
                    return redirect('distribution:vehicle_entry_list')
                
                # ایجاد یا به‌روزرسانی TruckInfo
                # چون plate_number primary key است، باید بررسی کنیم که آیا برای این transport وجود دارد
                existing_truck_for_transport = TruckInfo.objects.filter(transport=transport).first()
                
                if existing_truck_for_transport:
                    # اگر پلاک متفاوت است، باید پلاک قبلی را حذف کنیم و پلاک جدید را ایجاد کنیم
                    if existing_truck_for_transport.plate_number != plate_number:
                        existing_truck_for_transport.delete()
                        truck_info = TruckInfo.objects.create(
                            plate_number=plate_number,
                            transport=transport,
                            vehicle_type=vehicle_type or None,
                            loading_type=loading_type or None,
                        )
                    else:
                        # به‌روزرسانی اطلاعات موجود
                        truck_info = existing_truck_for_transport
                        if vehicle_type:
                            truck_info.vehicle_type = vehicle_type
                        if loading_type:
                            truck_info.loading_type = loading_type
                        truck_info.save()
                else:
                    # ایجاد TruckInfo جدید
                    truck_info = TruckInfo.objects.create(
                        plate_number=plate_number,
                        transport=transport,
                        vehicle_type=vehicle_type or None,
                        loading_type=loading_type or None,
                    )
                
                # آپلود کارت ملی
                TransportAttachment.objects.create(
                    transport=transport,
                    attachment_type='national_card',
                    file=national_card_file
                )
                
                # تغییر وضعیت حمل به loading (در حال بارگیری)
                transport.status = 'loading'
                transport.save()
                
                # ثبت زمان ورود خودرو
                schedule_info, created = LoadingScheduleInfo.objects.get_or_create(
                    transport=transport
                )
                schedule_info.vehicle_entry_time = timezone.now()
                schedule_info.save(update_fields=['vehicle_entry_time'])
                
                # بررسی تغییر وضعیت تخصیص
                if transport.allocation_id:
                    allocation = Allocation.objects.filter(allocation_number=transport.allocation_id).first()
                    if allocation and allocation.allocation_status == 'pending_vehicle_entry':
                        # بررسی اینکه آیا همه حمل‌های تخصیص به loading رسیدند
                        all_transports = Transport.objects.filter(allocation_id=allocation.allocation_number)
                        all_transports_count = all_transports.count()
                        loading_transports_count = all_transports.filter(status='loading').count()
                        
                        # اگر همه حمل‌ها به loading رسیدند، تخصیص را به pending_loading ببر
                        if all_transports_count > 0 and all_transports_count == loading_transports_count:
                            allocation.allocation_status = 'pending_loading'
                            allocation.save(update_fields=['allocation_status'])
                            bug_logger.info(f"وضعیت تخصیص {allocation.allocation_number} به 'در انتظار بارگیری' تغییر کرد")
                
                bug_logger.info(f"ورود خودرو برای حمل {waybill_number} ثبت شد")
                messages.success(request, f'ورود خودرو برای حمل {waybill_number} با موفقیت ثبت شد.')
                audit_logger.activity(f"ورود خودرو برای حمل {waybill_number} ثبت شد توسط کاربر {request.user.username}")
                
                return redirect('distribution:vehicle_entry_list')
                
        except Exception as e:
            bug_logger.error(f"خطا در ثبت ورود خودرو: {str(e)}")
            messages.error(request, f'خطا در ثبت ورود خودرو: {str(e)}')
            return redirect('distribution:vehicle_entry_list')
    
    # برای GET request، اطلاعات حمل را برمی‌گردانیم (برای AJAX)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        driver_name = None
        driver_national_id = None
        driver_mobile = None
        driver_description = None
        plate_part1 = None
        plate_part2 = None
        plate_part3 = None
        vehicle_type = None
        loading_type = None
        
        if transport.driver:
            driver_name = transport.driver.name
            driver_national_id = transport.driver.national_id
            driver_description = transport.driver.description
            person_content_type = ContentType.objects.get_for_model(Person)
            mobile_phone = PhoneNumber.objects.filter(
                content_type=person_content_type,
                object_id=transport.driver.national_id,
                phone_type='mobile'
            ).first()
            if mobile_phone:
                driver_mobile = mobile_phone.number
        
        truck_info = transport.truck_infos.first()
        if truck_info:
            # تجزیه پلاک
            plate_parts = truck_info.plate_number.split('|')
            if len(plate_parts) == 3:
                plate_part1 = plate_parts[0]
                plate_part2 = plate_parts[1]
                plate_part3 = plate_parts[2]
            vehicle_type = truck_info.vehicle_type
            loading_type = truck_info.loading_type
        
        # بررسی دسترسی فیلدها
        accessible_person_fields = get_accessible_person_fields(request.user)
        
        response_data = {
            'waybill_number': transport.waybill_number,
            'allocation_id': transport.allocation_id,
            'plate_part1': plate_part1,
            'plate_part2': plate_part2,
            'plate_part3': plate_part3,
            'vehicle_type': vehicle_type,
            'loading_type': loading_type,
        }
        
        # فقط فیلدهایی که کاربر دسترسی دارد را اضافه کن
        if accessible_person_fields.get('name'):
            response_data['driver_name'] = driver_name
        if accessible_person_fields.get('national_id'):
            response_data['driver_national_id'] = driver_national_id
        if accessible_person_fields.get('description'):
            response_data['driver_description'] = driver_description
        
        # شماره همراه را همیشه نشان بده (چون مربوط به PhoneNumber است، نه Person)
        response_data['driver_mobile'] = driver_mobile
        
        return JsonResponse(response_data)
    
    # در غیر این صورت به لیست برگرد
    return redirect('distribution:vehicle_entry_list')

