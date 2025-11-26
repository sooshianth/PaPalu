from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
import logging
import jdatetime
from datetime import date as datetime_date
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.LoadingScheduleInfoModel import LoadingScheduleInfo
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.AllocationFolder.AllocationModel import Allocation
from django.contrib.contenttypes.models import ContentType
from access.helpers import check_field_access_prefer_edit
from distribution.forms.waybill_registration_form import WaybillRegistrationForm
from core.TransportFolder.TransportAttachmentModel import TransportAttachment

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
    
    accessible_fields = {}
    accessible_fields['plate_number'] = check_field_access_prefer_edit(user, TruckInfo, 'plate_number')
    accessible_fields['vehicle_type'] = check_field_access_prefer_edit(user, TruckInfo, 'vehicle_type')
    accessible_fields['loading_type'] = check_field_access_prefer_edit(user, TruckInfo, 'loading_type')
    return accessible_fields


@login_required
def waybill_list_view(request):
    """
    لیست حمل‌های در انتظار بارنامه
    """
    audit_logger.info("درخواست مشاهده لیست حمل‌های در انتظار بارنامه")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_VIEW_WAYBILL_LIST.value):
        audit_logger.activity("تلاش برای دسترسی به لیست حمل‌های در انتظار بارنامه بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست حمل‌های در انتظار بارنامه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت حمل‌های در انتظار بارنامه
    transports = Transport.objects.filter(
        status='pending_waybill'
    ).select_related('driver').prefetch_related(
        'truck_infos', 'loading_schedule_infos'
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
        
        # دریافت تاریخ و ساعت ورود
        vehicle_entry_time = None
        schedule_info = transport.loading_schedule_infos.first()
        if schedule_info and schedule_info.vehicle_entry_time:
            vehicle_entry_time = schedule_info.vehicle_entry_time
        
        # دریافت اطلاعات راننده
        driver_name = None
        driver_national_id = None
        driver_mobile = None
        if transport.driver:
            driver_name = transport.driver.name
            driver_national_id = transport.driver.national_id
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
        if truck_info:
            plate_number = truck_info.plate_number
        
        # دریافت اسم باربری
        carrier_name = transport.carrier_recruitment or 'نامشخص'
        
        transports_with_info.append({
            'transport': transport,
            'order_number': order_number or 'نامشخص',
            'allocation_id': transport.allocation_id or 'نامشخص',
            'vehicle_entry_time': vehicle_entry_time,
            'empty_weight': transport.empty_weight,
            'gross_weight': transport.gross_weight,
            'driver_name': driver_name or 'نامشخص',
            'driver_mobile': driver_mobile or 'نامشخص',
            'plate_number': plate_number or 'نامشخص',
            'driver_national_id': driver_national_id or 'نامشخص',
            'carrier_name': carrier_name,
        })
    
    # بررسی دسترسی فیلدها
    accessible_person_fields = get_accessible_person_fields(request.user)
    accessible_truck_info_fields = get_accessible_truck_info_fields(request.user)
    
    bug_logger.debug(f"تعداد {len(transports_with_info)} حمل در انتظار بارنامه لود شد")
    
    context = {
        'transports_with_info': transports_with_info,
        'accessible_person_fields': accessible_person_fields,
        'accessible_truck_info_fields': accessible_truck_info_fields,
        'page_title': 'لیست حمل‌های در انتظار بارنامه',
    }
    return render(request, 'distribution/waybill_list.html', context)


@login_required
def register_waybill_view(request, waybill_number):
    """
    ثبت اطلاعات بارنامه
    """
    audit_logger.info(f"درخواست ثبت اطلاعات بارنامه برای حمل {waybill_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_REGISTER_WAYBILL.value):
        audit_logger.activity("تلاش برای ثبت اطلاعات بارنامه بدون دسترسی")
        messages.error(request, 'شما دسترسی به ثبت اطلاعات بارنامه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if transport.status != 'pending_waybill':
        messages.error(request, 'این حمل در وضعیت مناسب برای ثبت بارنامه نیست.')
        return redirect('distribution:waybill_list')
    
    # آماده‌سازی اطلاعات برای نمایش
    driver_name = None
    driver_national_id = None
    driver_mobile = None
    if transport.driver:
        driver_name = transport.driver.name
        driver_national_id = transport.driver.national_id
        person_content_type = ContentType.objects.get_for_model(Person)
        mobile_phone = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=transport.driver.national_id,
            phone_type='mobile'
        ).first()
        if mobile_phone:
            driver_mobile = mobile_phone.number
    
    truck_info = transport.truck_infos.first()
    plate_number = None
    if truck_info:
        plate_number = truck_info.plate_number
    
    # دریافت شماره سفارش
    order_number = None
    if transport.allocation_id:
        allocation = Allocation.objects.filter(allocation_number=transport.allocation_id).first()
        if allocation and allocation.order:
            order_number = allocation.order.order_number if hasattr(allocation.order, 'order_number') else None
    
    # دریافت تاریخ و ساعت ورود
    vehicle_entry_time = None
    schedule_info = transport.loading_schedule_infos.first()
    if schedule_info and schedule_info.vehicle_entry_time:
        vehicle_entry_time = schedule_info.vehicle_entry_time
    
    if request.method == 'POST':
        form = WaybillRegistrationForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # دریافت داده‌های فرم
                    waybill_number_new = form.cleaned_data['waybill_number']
                    waybill_serial = form.cleaned_data['waybill_serial']
                    waybill_date = form.cleaned_data['waybill_date']
                    cardex_code = form.cleaned_data['cardex_code']
                    contract_code = form.cleaned_data['contract_code']
                    waybill_file = form.cleaned_data['waybill_file']
                    
                    # به‌روزرسانی اطلاعات Transport
                    transport.waybill_serial = waybill_serial
                    # تبدیل تاریخ میلادی از فرم به تاریخ جلالی
                    if waybill_date:
                        if isinstance(waybill_date, jdatetime.date):
                            # اگر قبلاً جلالی است، مستقیماً استفاده می‌کنیم
                            transport.waybill_date = waybill_date
                        elif isinstance(waybill_date, datetime_date):
                            # تبدیل از datetime.date میلادی به jdatetime.date جلالی
                            transport.waybill_date = jdatetime.date.fromgregorian(date=waybill_date)
                        else:
                            # اگر نوع دیگری است، سعی می‌کنیم آن را به جلالی تبدیل کنیم
                            transport.waybill_date = jdatetime.date.fromgregorian(date=waybill_date)
                    else:
                        transport.waybill_date = None
                    transport.cardex_code = cardex_code
                    transport.contract_code = contract_code
                    
                    # تغییر وضعیت حمل به pending_exit (در انتظار خروج)
                    transport.status = 'pending_exit'
                    transport.save()
                    
                    # ثبت زمان ثبت بارنامه در LoadingScheduleInfo
                    schedule_info, created = LoadingScheduleInfo.objects.get_or_create(
                        transport=transport
                    )
                    schedule_info.vehicle_exit_time = timezone.now()
                    schedule_info.save(update_fields=['vehicle_exit_time'])
                    
                    # ذخیره فایل بارنامه
                    attachment = TransportAttachment.objects.create(
                        transport=transport,
                        attachment_type='official_gazette',
                        file=waybill_file,
                        description='بارنامه حمل'
                    )
                    
                    # بررسی تغییر وضعیت تخصیص
                    if transport.allocation_id:
                        allocation = Allocation.objects.filter(allocation_number=transport.allocation_id).first()
                        if allocation and allocation.allocation_status == 'pending_waybill':
                            # بررسی اینکه آیا همه حمل‌های تخصیص به pending_exit رسیدند
                            all_transports = Transport.objects.filter(allocation_id=allocation.allocation_number)
                            all_transports_count = all_transports.count()
                            pending_exit_transports_count = all_transports.filter(status='pending_exit').count()
                            
                            # اگر همه حمل‌ها به pending_exit رسیدند، تخصیص را به pending_exit ببر
                            if all_transports_count > 0 and all_transports_count == pending_exit_transports_count:
                                allocation.allocation_status = 'pending_exit'
                                allocation.save(update_fields=['allocation_status'])
                                bug_logger.info(f"وضعیت تخصیص {allocation.allocation_number} به 'در انتظار خروج' تغییر کرد")
                    
                    bug_logger.info(f"اطلاعات بارنامه برای حمل {waybill_number} ثبت شد")
                    messages.success(request, f'اطلاعات بارنامه برای حمل {waybill_number} با موفقیت ثبت شد.')
                    audit_logger.activity(f"اطلاعات بارنامه برای حمل {waybill_number} ثبت شد توسط کاربر {request.user.username}")
                    
                    return redirect('distribution:waybill_list')
                    
            except Exception as e:
                bug_logger.error(f"خطا در ثبت اطلاعات بارنامه: {str(e)}")
                messages.error(request, f'خطا در ثبت اطلاعات بارنامه: {str(e)}')
        else:
            # نمایش خطاهای فرم
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # برای GET request، فرم را با داده‌های موجود پر می‌کنیم
        initial_data = {}
        
        # اگر اطلاعات بارنامه قبلاً ثبت شده، آن‌ها را پر می‌کنیم
        if transport.waybill_serial:
            initial_data['waybill_serial'] = transport.waybill_serial
        if transport.waybill_date:
            initial_data['waybill_date'] = transport.waybill_date
        else:
            # پیش‌فرض امروز (جلالی)
            initial_data['waybill_date'] = jdatetime.date.today()
        if transport.cardex_code:
            initial_data['cardex_code'] = transport.cardex_code
        if transport.contract_code:
            initial_data['contract_code'] = transport.contract_code
        
        # شماره بارنامه همیشه همان waybill_number فعلی است
        initial_data['waybill_number'] = transport.waybill_number
        
        # ایجاد فرم با مقداردهی اولیه
        form = WaybillRegistrationForm(initial=initial_data)
    
    # بررسی دسترسی فیلدها
    accessible_person_fields = get_accessible_person_fields(request.user)
    
    context = {
        'form': form,
        'transport': transport,
        'driver_name': driver_name,
        'driver_national_id': driver_national_id,
        'driver_mobile': driver_mobile,
        'plate_number': plate_number,
        'order_number': order_number or 'نامشخص',
        'vehicle_entry_time': vehicle_entry_time,
        'empty_weight': transport.empty_weight,
        'gross_weight': transport.gross_weight,
        'accessible_person_fields': accessible_person_fields,
        'page_title': f'ثبت اطلاعات بارنامه - {transport.waybill_number}',
    }
    return render(request, 'distribution/waybill_detail.html', context)

