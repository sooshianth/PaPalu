from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TransportAttachmentModel import TransportAttachment
from core.TransportFolder.LoadingScheduleInfoModel import LoadingScheduleInfo
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.AttachmentModel import Attachment
from core.AllocationFolder.AllocationModel import Allocation
from django.contrib.contenttypes.models import ContentType
from core.helpers import check_field_access_prefer_edit
from distribution.tables import VehicleEntryTable
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
        status='pending_vehicle_entry',
        direction='outbound'
    ).select_related('driver', 'allocation').prefetch_related(
        'truck_infos'
    ).order_by('-waybill_date', 'waybill_number')
    
    # آماده‌سازی اطلاعات حمل‌ها برای جدول
    # استفاده از یک class ساده که transport و اطلاعات مرتبط را نگه می‌دارد
    class TransportRow:
        def __init__(self, transport):
            self.transport = transport
            
            # دریافت اطلاعات راننده
            self.driver_name = None
            self.driver_national_id = None
            self.driver_mobile = None
            if transport.driver:
                self.driver_name = transport.driver.name
                self.driver_national_id = transport.driver.national_id
                # دریافت شماره همراه راننده
                person_content_type = ContentType.objects.get_for_model(Person)
                mobile_phone = PhoneNumber.objects.filter(
                    content_type=person_content_type,
                    object_id=transport.driver.national_id,
                    phone_type='mobile'
                ).first()
                if mobile_phone:
                    self.driver_mobile = mobile_phone.number
            
            # دریافت اطلاعات کامیون
            truck_info = transport.truck_infos.first()
            self.plate_number = None
            self.vehicle_type = None
            self.loading_type = None
            if truck_info:
                self.plate_number = truck_info.plate_number
                self.vehicle_type = truck_info.get_vehicle_type_display() if truck_info.vehicle_type else None
                self.loading_type = truck_info.get_loading_type_display() if truck_info.loading_type else None
            
            # اگر vehicle_type در TruckInfo وجود نداشت، از Transport.vehicle_type یا vehicle_type_official استفاده کن
            if not self.vehicle_type and transport.vehicle_type:
                self.vehicle_type = transport.get_vehicle_type_display()
            elif not self.vehicle_type and transport.vehicle_type_official:
                self.vehicle_type = transport.get_vehicle_type_official_display()
        
        @property
        def waybill_number(self):
            """دسترسی به waybill_number از transport"""
            return self.transport.waybill_number if self.transport else None
        
        @property
        def allocation(self):
            """دسترسی به allocation از transport"""
            return self.transport.allocation if self.transport else None
        
        def __getattr__(self, name):
            # اگر attribute در self وجود نداشت، از transport بگیر
            if hasattr(self.transport, name):
                return getattr(self.transport, name)
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    transports_data = [TransportRow(transport) for transport in transports]
    
    # ایجاد جدول
    table = VehicleEntryTable(
        transports_data,
        accessible_fields=None,  # table خودش محاسبه می‌کند
        user=request.user
    )
    
    # تنظیم صفحه‌بندی
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    bug_logger.debug(f"تعداد {len(transports_data)} حمل در انتظار ورود به کارخانه لود شد")
    
    context = {
        'table': table,
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
    
    transport = get_object_or_404(
        Transport.objects.select_related('allocation'),
        waybill_number=waybill_number
    )
    
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
                plate_part2 = request.POST.get('plate_part2', '').strip()  # 3 رقم
                plate_part3 = request.POST.get('plate_part3', '').strip()  # حرف
                plate_part4 = request.POST.get('plate_part4', '').strip()  # 2 رقم
                
                vehicle_type = request.POST.get('vehicle_type', '').strip()
                loading_type = request.POST.get('loading_type', '').strip()
                
                # اعتبارسنجی داده‌های اجباری
                if not driver_national_id:
                    messages.error(request, 'شماره ملی راننده الزامی است.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی شماره ملی (10 رقم)
                if not re.match(r'^\d{10}$', driver_national_id):
                    messages.error(request, 'شماره ملی باید 10 رقم باشد.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                if not driver_name:
                    messages.error(request, 'نام راننده الزامی است.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                if not driver_mobile:
                    messages.error(request, 'شماره همراه راننده الزامی است.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی شماره همراه (09XXXXXXXXX)
                if not re.match(r'^09\d{9}$', driver_mobile):
                    messages.error(request, 'شماره همراه باید با فرمت 09XXXXXXXXX باشد.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی پلاک
                if not plate_part1 or not plate_part2 or not plate_part3 or not plate_part4:
                    messages.error(request, 'تمام بخش‌های پلاک الزامی است.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی فرمت بخش اول (2 رقم)
                if not re.match(r'^\d{2}$', plate_part1):
                    messages.error(request, 'بخش اول پلاک باید 2 رقم باشد.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی فرمت بخش دوم (3 رقم)
                if not re.match(r'^\d{3}$', plate_part2):
                    messages.error(request, 'بخش دوم پلاک باید 3 رقم باشد.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی فرمت بخش سوم (1 حرف فارسی)
                if not re.match(r'^[ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]$', plate_part3):
                    messages.error(request, 'بخش سوم پلاک باید یک حرف فارسی باشد.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # اعتبارسنجی فرمت بخش چهارم (2 رقم)
                if not re.match(r'^\d{2}$', plate_part4):
                    messages.error(request, 'بخش چهارم پلاک باید 2 رقم باشد.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # ساخت پلاک کامل با فرمت: 11|345ح12
                # حرف در وسط: 3 رقم + حرف + 2 رقم
                plate_middle = f"{plate_part2}{plate_part3}{plate_part4}"  # 345ح12
                
                plate_number = f"{plate_part1}|{plate_middle}"
                
                # ایجاد یا به‌روزرسانی Person برای راننده (قبل از بررسی کارت ملی)
                driver_person, created = Person.objects.get_or_create(
                    national_id=driver_national_id,
                    defaults={
                        'name': driver_name,
                        'type': 'driver',
                        'description': driver_description or None,
                    }
                )
                
                # اعتبارسنجی فایل کارت ملی
                national_card_file = request.FILES.get('national_card_file')
                use_previous_card = request.POST.get('use_previous_national_card') == 'true'
                previous_card_attachment = None
                
                # اگر از کارت ملی قبلی استفاده می‌شود، بررسی کن که آیا کارت ملی قبلی وجود دارد
                if use_previous_card:
                    # بررسی attachment های Person که ممکن است کارت ملی باشد
                    previous_card_attachment = Attachment.objects.filter(
                        person=driver_person
                    ).filter(
                        models.Q(description__icontains='کارت ملی') | 
                        models.Q(description__icontains='national card') |
                        models.Q(doc_type='other')
                    ).first()
                    
                    # اگر پیدا نشد، همه attachment ها را بررسی کن
                    if not previous_card_attachment:
                        previous_card_attachment = Attachment.objects.filter(
                            person=driver_person,
                            file__isnull=False
                        ).exclude(file='').first()
                    
                    if not previous_card_attachment or not previous_card_attachment.file:
                        messages.error(request, 'کارت ملی قبلی یافت نشد. لطفاً فایل جدیدی آپلود کنید.')
                        return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                elif not national_card_file:
                    messages.error(request, 'آپلود کارت ملی الزامی است.')
                    return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
                # بررسی فرمت فایل (فقط اگر فایل جدید آپلود شده)
                if national_card_file:
                    allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf']
                    file_name = national_card_file.name.lower()
                    if '.' in file_name:
                        file_extension = '.' + file_name.split('.')[-1]
                    else:
                        file_extension = ''
                    if file_extension not in allowed_extensions:
                        messages.error(request, 'فرمت فایل کارت ملی باید JPG، PNG یا PDF باشد.')
                        return redirect('distribution:register_vehicle_entry', waybill_number=waybill_number)
                
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
                
                # ایجاد یا به‌روزرسانی TruckInfo
                existing_truck_for_transport = TruckInfo.objects.filter(transport=transport).first()
                
                if existing_truck_for_transport:
                    # به‌روزرسانی اطلاعات موجود
                    existing_truck_for_transport.plate_number = plate_number
                    if vehicle_type:
                        existing_truck_for_transport.vehicle_type = vehicle_type
                    if loading_type:
                        existing_truck_for_transport.loading_type = loading_type
                    existing_truck_for_transport.save()
                    truck_info = existing_truck_for_transport
                else:
                    # ایجاد TruckInfo جدید
                    truck_info = TruckInfo.objects.create(
                        plate_number=plate_number,
                        transport=transport,
                        vehicle_type=vehicle_type or None,
                        loading_type=loading_type or None,
                    )
                
                # آپلود کارت ملی
                if use_previous_card and previous_card_attachment:
                    # استفاده از کارت ملی قبلی (کپی کردن فایل)
                    TransportAttachment.objects.create(
                        transport=transport,
                        attachment_type='national_card',
                        file=previous_card_attachment.file
                    )
                    # ذخیره کارت ملی در Attachment مربوط به Person
                    person_national_card, created = Attachment.objects.get_or_create(
                        person=driver_person,
                        description='کارت ملی',
                        defaults={
                            'file': previous_card_attachment.file,
                            'doc_type': 'other'
                        }
                    )
                    if not created:
                        # اگر از قبل وجود داشت، فایل را به‌روزرسانی کن
                        person_national_card.file = previous_card_attachment.file
                        person_national_card.save()
                elif national_card_file:
                    # آپلود فایل جدید
                    TransportAttachment.objects.create(
                        transport=transport,
                        attachment_type='national_card',
                        file=national_card_file
                    )
                    # ذخیره کارت ملی در Attachment مربوط به Person
                    person_national_card, created = Attachment.objects.get_or_create(
                        person=driver_person,
                        description='کارت ملی',
                        defaults={
                            'file': national_card_file,
                            'doc_type': 'other'
                        }
                    )
                    if not created:
                        # اگر از قبل وجود داشت، فایل را به‌روزرسانی کن
                        person_national_card.file = national_card_file
                        person_national_card.save()
                
                # تغییر وضعیت حمل به loading (در حال بارگیری)
                transport.status = 'loading'
                transport.save()
                
                # ثبت زمان ورود خودرو
                schedule_info, created = LoadingScheduleInfo.objects.get_or_create(
                    transport=transport
                )
                schedule_info.vehicle_entry_time = timezone.now()
                schedule_info.save(update_fields=['vehicle_entry_time'])
                
                # توجه: وضعیت تخصیص در این مرحله تغییر نمی‌کند
                # وضعیت تخصیص فقط در مراحل خاص تغییر می‌کند:
                # 1. هنگام اعلام بار: pending_shipping -> pending_vehicle_recruitment
                # 2. وقتی همه حمل‌ها به pending_waybill رفتند: pending_vehicle_recruitment -> pending_loading_completion
                # 3. وقتی همه حمل‌ها به completed یا loaded رفتند: pending_loading_completion -> delivered
                
                bug_logger.info(f"ورود خودرو برای حمل {waybill_number} ثبت شد")
                messages.success(request, f'ورود خودرو برای حمل {waybill_number} با موفقیت ثبت شد.')
                audit_logger.activity(f"ورود خودرو برای حمل {waybill_number} ثبت شد توسط کاربر {request.user.username}")
                
                return redirect('distribution:vehicle_entry_list')
                
        except Exception as e:
            import traceback
            messages.error(request, f'خطا در ثبت ورود خودرو: {traceback.format_exc()}')
            bug_logger.error(f"خطا در ثبت ورود خودرو: {traceback.format_exc()}")

            return redirect('distribution:vehicle_entry_list')
    
    # برای GET request معمولی (صفحه کامل)، فرم را نمایش می‌دهیم
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        # آماده‌سازی context برای رندر صفحه کامل (مثل تامین)
        driver_name = None
        driver_national_id = None
        driver_mobile = None
        driver_description = None
        plate_part1 = None
        plate_part2 = None
        plate_part3 = None
        plate_part4 = None
        vehicle_type = None
        loading_type = None
        allocation_number = None
        
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
        
        if transport.allocation:
            allocation_number = transport.allocation.allocation_number
        
        truck_info = transport.truck_infos.first()
        if truck_info:
            plate_parts = (truck_info.plate_number or '').split('|')
            if len(plate_parts) == 2:
                plate_part1 = plate_parts[0]
                plate_middle = plate_parts[1]
                plate_middle_match = re.match(r'^(\d{3})([ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])(\d{2})$', plate_middle)
                if plate_middle_match:
                    plate_part2 = plate_middle_match.group(1)
                    plate_part3 = plate_middle_match.group(2)
                    plate_part4 = plate_middle_match.group(3)
            vehicle_type = truck_info.vehicle_type
            loading_type = truck_info.loading_type
        
        context = {
            'transport': transport,
            'allocation_number': allocation_number,
            'driver_name': driver_name,
            'driver_national_id': driver_national_id,
            'driver_mobile': driver_mobile,
            'driver_description': driver_description,
            'plate_part1': plate_part1,
            'plate_part2': plate_part2,
            'plate_part3': plate_part3,
            'plate_part4': plate_part4,
            'vehicle_type': vehicle_type,
            'loading_type': loading_type,
        }
        return render(request, 'distribution/vehicle_entry_register.html', context)
    
    # برای GET request با هدر AJAX (سازگاری با کد قدیمی)، JSON برمی‌گردانیم
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        driver_name = None
        driver_national_id = None
        driver_mobile = None
        driver_description = None
        plate_part1 = None
        plate_part2 = None
        plate_part3 = None
        plate_part4 = None
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
            # فرمت ذخیره شده: 11|345ح12
            plate_parts = truck_info.plate_number.split('|')
            if len(plate_parts) == 2:
                plate_part1 = plate_parts[0]  # 11
                plate_middle = plate_parts[1]  # 345ح12
                
                # استخراج حرف و اعداد از وسط: 345ح12 -> 12345 و ح
                # فرمت: 3 رقم + حرف + 2 رقم
                plate_middle_match = re.match(r'^(\d{3})([ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])(\d{2})$', plate_middle)
                if plate_middle_match:
                    plate_part2 = plate_middle_match.group(1)  # 345
                    plate_part3 = plate_middle_match.group(2)  # ح
                    plate_part4 = plate_middle_match.group(3)   # 12
                else:
                    # فرمت قدیمی (fallback) - برای سازگاری با داده‌های قدیمی
                    plate_part2 = None
                    plate_part3 = None
                    plate_part4 = None
            vehicle_type = truck_info.vehicle_type
            loading_type = truck_info.loading_type
        
        # بررسی دسترسی فیلدها
        accessible_person_fields = get_accessible_person_fields(request.user)
        
        # دریافت allocation_number
        allocation_number = None
        if transport.allocation:
            allocation_number = transport.allocation.allocation_number
            bug_logger.debug(f"Transport {transport.waybill_number} has allocation: {allocation_number}")
        else:
            bug_logger.debug(f"Transport {transport.waybill_number} has no allocation")
        
        response_data = {
            'waybill_number': transport.waybill_number or str(transport.pk),  # اگر waybill_number نبود، از pk استفاده کن
            'allocation_id': allocation_number,
            'allocation_number': allocation_number,  # برای سازگاری
            'plate_part1': plate_part1,
            'plate_part2': plate_part2,
            'plate_part3': plate_part3,
            'plate_part4': plate_part4,
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


@login_required
def get_driver_info_by_national_id_view(request):
    """
    دریافت اطلاعات راننده بر اساس شماره ملی (برای AJAX)
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    national_id = request.GET.get('national_id', '').strip()
    
    if not national_id:
        return JsonResponse({'error': 'شماره ملی الزامی است'}, status=400)
    
    # بررسی فرمت شماره ملی (10 رقم)
    if not re.match(r'^\d{10}$', national_id):
        return JsonResponse({'error': 'شماره ملی باید 10 رقم باشد'}, status=400)
    
    try:
        # جستجوی راننده
        driver = Person.objects.filter(national_id=national_id, type='driver').first()
        
        if not driver:
            return JsonResponse({'found': False})
        
        # دریافت شماره همراه
        person_content_type = ContentType.objects.get_for_model(Person)
        mobile_phone = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=driver.national_id,
            phone_type='mobile'
        ).first()
        
        # بررسی دسترسی فیلدها
        accessible_person_fields = get_accessible_person_fields(request.user)
        
        response_data = {
            'found': True,
        }
        
        # فقط فیلدهایی که کاربر دسترسی دارد را اضافه کن
        if accessible_person_fields.get('name'):
            response_data['driver_name'] = driver.name or ''
        if accessible_person_fields.get('national_id'):
            response_data['driver_national_id'] = driver.national_id or ''
        if accessible_person_fields.get('description'):
            response_data['driver_description'] = driver.description or ''
        
        # شماره همراه را همیشه نشان بده
        response_data['driver_mobile'] = mobile_phone.number if mobile_phone else ''
        
        # جستجوی کارت ملی در پیوست‌های شخص
        # بررسی attachment های Person که ممکن است کارت ملی باشد
        # معمولاً در description یا doc_type='other' ذخیره می‌شود
        national_card_attachment = Attachment.objects.filter(
            person=driver
        ).filter(
            models.Q(description__icontains='کارت ملی') | 
            models.Q(description__icontains='national card') |
            models.Q(doc_type='other')
        ).first()
        
        # اگر پیدا نشد، همه attachment ها را بررسی کن
        if not national_card_attachment:
            national_card_attachment = Attachment.objects.filter(
                person=driver,
                file__isnull=False
            ).exclude(file='').first()
        
        if national_card_attachment and national_card_attachment.file:
            response_data['national_card_url'] = national_card_attachment.file.url
        
        # دریافت پلاک‌های قبلی این راننده
        previous_plates = []
        # پیدا کردن Transportهای مربوط به این راننده
        transports = Transport.objects.filter(
            driver=driver
        ).prefetch_related('truck_infos')
        
        # جمع‌آوری پلاک‌های منحصر به فرد
        seen_plates = set()
        for transport in transports:
            for truck_info in transport.truck_infos.all():
                if truck_info.plate_number and truck_info.plate_number not in seen_plates:
                    seen_plates.add(truck_info.plate_number)
                    # تجزیه پلاک برای نمایش
                    plate_parts = truck_info.plate_number.split('|')
                    if len(plate_parts) == 2:
                        plate_part1 = plate_parts[0]
                        plate_middle = plate_parts[1]
                        # استخراج حرف و اعداد از وسط
                        plate_middle_match = re.match(r'^(\d{3})([ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])(\d{2})$', plate_middle)
                        if plate_middle_match:
                            previous_plates.append({
                                'plate_number': truck_info.plate_number,
                                'plate_part1': plate_part1,
                                'plate_part2': plate_middle_match.group(1),
                                'plate_part3': plate_middle_match.group(2),
                                'plate_part4': plate_middle_match.group(3),
                                'vehicle_type': truck_info.vehicle_type,
                                'loading_type': truck_info.loading_type,
                                'display': truck_info.plate_number.replace('|', ' ')
                            })
        
        response_data['previous_plates'] = previous_plates
        
        return JsonResponse(response_data)
        
    except Exception as e:
        bug_logger.error(f"خطا در دریافت اطلاعات راننده: {str(e)}")
        return JsonResponse({'error': 'خطا در دریافت اطلاعات'}, status=500)

