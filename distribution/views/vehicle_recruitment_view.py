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
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.OrderFolder.OrderModel import Order
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.PersonModel import Person
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.TransportAttachmentModel import TransportAttachment
from core.TransportFolder.LoadingScheduleInfoModel import LoadingScheduleInfo
from core.TransportFolder.ProductInfoModel import ProductInfo
from core.TransportFolder.TruckInfoModel import TruckInfo
from django.contrib.contenttypes.models import ContentType
from sales.views.allocation_list_view import get_delivery_address_info
from core.helpers import check_field_access_prefer_edit
from decimal import Decimal

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


def get_accessible_delivery_address_fields(user):
    """بررسی دسترسی کاربر به فیلدهای DeliveryAddress"""
    if user.is_superuser:
        return {
            'recipient_name': True,
            'recipient_national_id': True,
            'unique_delivery_id': True,
            'address': True,
            'province': True,
            'city': True,
            'postal_code': True
        }
    
    accessible_fields = {}
    accessible_fields['recipient_name'] = check_field_access_prefer_edit(user, DeliveryAddress, 'recipient_name')
    accessible_fields['recipient_national_id'] = check_field_access_prefer_edit(user, DeliveryAddress, 'recipient_national_id')
    accessible_fields['unique_delivery_id'] = check_field_access_prefer_edit(user, DeliveryAddress, 'unique_delivery_id')
    accessible_fields['address'] = check_field_access_prefer_edit(user, DeliveryAddress, 'address')
    accessible_fields['province'] = check_field_access_prefer_edit(user, DeliveryAddress, 'province')
    accessible_fields['city'] = check_field_access_prefer_edit(user, DeliveryAddress, 'city')
    accessible_fields['postal_code'] = check_field_access_prefer_edit(user, DeliveryAddress, 'postal_code')
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


@login_required
def vehicle_recruitment_list_view(request):
    """
    لیست تخصیص‌های در انتظار جذب خودرو
    """
    audit_logger.info("درخواست مشاهده لیست تخصیص‌های در انتظار جذب خودرو")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_VIEW_VEHICLE_RECRUITMENT_LIST.value):
        audit_logger.activity("تلاش برای دسترسی به لیست جذب خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست جذب خودرو را ندارید.')
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
            allocation=allocation
        ).count()
        
        allocations_with_info.append({
            'allocation': allocation,
            'order_number': allocation.order.order_number if allocation.order else '-',
            'delivery_info': delivery_info,
            'transports_count': transports_count,
            'shipping_method': allocation.get_shipping_announcement_method_display() if allocation.shipping_announcement_method else '-',
        })
    
    # بررسی دسترسی فیلدها
    accessible_person_fields = get_accessible_person_fields(request.user)
    accessible_delivery_fields = get_accessible_delivery_address_fields(request.user)
    accessible_allocation_fields = get_accessible_allocation_fields(request.user)
    accessible_order_fields = get_accessible_order_fields(request.user)
    
    bug_logger.debug(f"تعداد {len(allocations_with_info)} تخصیص در انتظار جذب خودرو لود شد")
    
    context = {
        'allocations_with_info': allocations_with_info,
        'accessible_person_fields': accessible_person_fields,
        'accessible_delivery_fields': accessible_delivery_fields,
        'accessible_allocation_fields': accessible_allocation_fields,
        'accessible_order_fields': accessible_order_fields,
        'page_title': 'لیست تخصیص‌های در انتظار جذب خودرو',
    }
    return render(request, 'distribution/vehicle_recruitment_list.html', context)


@login_required
def create_transport_view(request, allocation_number):
    """
    ایجاد حمل جدید برای یک تخصیص
    """
    audit_logger.info(f"درخواست ایجاد حمل برای تخصیص {allocation_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_CREATE_TRANSPORT.value):
        audit_logger.activity("تلاش برای ایجاد حمل بدون دسترسی")
        messages.error(request, 'شما دسترسی به ایجاد حمل را ندارید.')
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
                
                # دریافت محصولات انتخاب شده و وزن‌های آن‌ها
                allocation_product_infos = AllocationProductInfo.objects.filter(
                    allocation=allocation
                ).select_related('product')
                
                selected_products = []
                for product_info in allocation_product_infos:
                    product_id = str(product_info.product.pk) if product_info.product else None
                    if product_id:
                        weight_key = f'product_weight_{product_id}'
                        weight_value = request.POST.get(weight_key)
                        if weight_value:
                            try:
                                weight = Decimal(weight_value)
                                selected_products.append({
                                    'product': product_info.product,
                                    'weight': weight,
                                    'allocation_product_info': product_info
                                })
                            except (ValueError, TypeError):
                                pass
                
                # بررسی اینکه حداقل یک محصول انتخاب شده باشد
                if not selected_products:
                    messages.error(request, 'حداقل باید یک محصول انتخاب شود.')
                    return redirect('distribution:vehicle_recruitment_list')
                
                # محاسبه جمع وزن محصولات انتخاب شده
                total_products_weight = sum(p['weight'] for p in selected_products)
                
                # محاسبه جمع وزن کل محصولات تخصیص (با تبدیل واحدها به کیلوگرم)
                # برای ساده‌سازی، فرض می‌کنیم که واحدها یکسان هستند
                total_allocation_weight = Decimal('0')
                for api in allocation_product_infos:
                    if api.quantity:
                        quantity = Decimal(str(api.quantity))
                        # تبدیل واحد به کیلوگرم (اگر نیاز باشد)
                        if api.unit == 'ton':
                            quantity = quantity * Decimal('1000')  # تن به کیلوگرم
                        elif api.unit == 'gr':
                            quantity = quantity / Decimal('1000')  # گرم به کیلوگرم
                        total_allocation_weight += quantity
                
                # بررسی جمع وزن‌های حمل‌های قبلی این تخصیص
                existing_transports = Transport.objects.filter(
                    allocation=allocation
                )
                total_existing_weight = Decimal('0')
                for transport in existing_transports:
                    # جمع وزن محصولات حمل‌های قبلی
                    transport_products = ProductInfo.objects.filter(transport=transport)
                    for tp in transport_products:
                        if tp.weight:
                            total_existing_weight += tp.weight
                
                # بررسی اینکه جمع وزن‌های حمل‌ها از جمع وزن محصولات تخصیص بیشتر نشود
                new_total_weight = total_existing_weight + total_products_weight
                if new_total_weight > total_allocation_weight + Decimal('0.001'):
                    messages.error(request, f'جمع وزن‌های حمل‌ها ({new_total_weight}) نمی‌تواند از جمع وزن محصولات تخصیص ({total_allocation_weight}) بیشتر باشد.')
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
                # وضعیت حمل تا قبل از تکمیل جذب خودرو، pending_recruitment_completion است
                transport = Transport.objects.create(
                    waybill_number=waybill_number,
                    allocation=allocation,
                    delivery_postal_code=allocation.delivery_postal_code,
                    direction='outbound',
                    carrier_recruitment=carrier_recruitment,
                    vehicle_type_official=vehicle_type_official,
                    driver=driver_person,
                    status='pending_recruitment_completion',
                )
                
                # ایجاد ProductInfo برای هر محصول انتخاب شده
                for product_data in selected_products:
                    ProductInfo.objects.create(
                        transport=transport,
                        product=product_data['product'],
                        weight=product_data['weight'],
                        item_type='product',
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
                
                bug_logger.info(f"حمل {transport.pk} برای تخصیص {allocation_number} ایجاد شد")
                messages.success(request, f'حمل با موفقیت ایجاد شد.')
                audit_logger.activity(f"حمل {transport.pk} برای تخصیص {allocation_number} ایجاد شد توسط کاربر {request.user.username}")
                
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
        
        # دریافت محصولات تخصیص
        allocation_product_infos = AllocationProductInfo.objects.filter(
            allocation=allocation
        ).select_related('product')
        
        products_data = []
        for api in allocation_product_infos:
            if api.product:
                products_data.append({
                    'id': api.product.pk,
                    'name': api.product.name,
                    'quantity': float(api.quantity) if api.quantity else 0,
                    'unit': api.unit or '',
                })
        
        # محاسبه وزن کل تخصیص (تبدیل به کیلوگرم)
        total_allocation_weight = Decimal('0')
        for api in allocation_product_infos:
            if api.quantity:
                quantity = Decimal(str(api.quantity))
                # تبدیل واحد به کیلوگرم
                if api.unit == 'ton':
                    quantity = quantity * Decimal('1000')
                elif api.unit == 'gr':
                    quantity = quantity / Decimal('1000')
                total_allocation_weight += quantity
        
        # محاسبه وزن حمل‌های موجود
        existing_transports = Transport.objects.filter(allocation=allocation)
        total_transports_weight = Decimal('0')
        for transport in existing_transports:
            transport_products = ProductInfo.objects.filter(transport=transport)
            for tp in transport_products:
                if tp.weight:
                    total_transports_weight += tp.weight
        
        # محاسبه وزن باقیمانده
        remaining_weight = total_allocation_weight - total_transports_weight
        
        return JsonResponse({
            'allocation_number': allocation.allocation_number,
            'order_number': allocation.order.order_number if allocation.order else '-',
            'delivery_info': delivery_info,
            'products': products_data,
            'weight_info': {
                'total_allocation_weight': float(total_allocation_weight),
                'total_transports_weight': float(total_transports_weight),
                'remaining_weight': float(remaining_weight),
            }
        })
    
    # در غیر این صورت به لیست برگرد
    return redirect('distribution:vehicle_recruitment_list')


@login_required
def complete_vehicle_recruitment_view(request, allocation_number):
    """
    تکمیل جذب خودرو برای یک تخصیص
    """
    audit_logger.info(f"درخواست تکمیل جذب خودرو برای تخصیص {allocation_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_COMPLETE_VEHICLE_RECRUITMENT.value):
        audit_logger.activity("تلاش برای تکمیل جذب خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به تکمیل جذب خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number)
    
    if allocation.allocation_status != 'pending_vehicle_recruitment':
        messages.error(request, 'این تخصیص در وضعیت مناسب برای تکمیل جذب خودرو نیست.')
        return redirect('distribution:vehicle_recruitment_list')
    
    # بررسی اینکه حداقل یک حمل وجود دارد
    transports = Transport.objects.filter(allocation=allocation)
    if not transports.exists():
        messages.error(request, 'برای تکمیل جذب خودرو، حداقل باید یک حمل ایجاد شده باشد.')
        return redirect('distribution:vehicle_recruitment_list')
    
    # محاسبه جمع وزن محصولات تخصیص
    allocation_product_infos = AllocationProductInfo.objects.filter(
        allocation=allocation
    ).select_related('product')
    
    total_allocation_weight = Decimal('0')
    for api in allocation_product_infos:
        if api.quantity:
            quantity = Decimal(str(api.quantity))
            # تبدیل واحد به کیلوگرم (اگر نیاز باشد)
            if api.unit == 'ton':
                quantity = quantity * Decimal('1000')  # تن به کیلوگرم
            elif api.unit == 'gr':
                quantity = quantity / Decimal('1000')  # گرم به کیلوگرم
            total_allocation_weight += quantity
    
    # محاسبه جمع وزن همه حمل‌های این تخصیص
    total_transports_weight = Decimal('0')
    for transport in transports:
        # جمع وزن محصولات هر حمل
        transport_products = ProductInfo.objects.filter(transport=transport)
        for tp in transport_products:
            if tp.weight:
                total_transports_weight += tp.weight
    
    # بررسی اینکه جمع وزن‌های حمل‌ها باید با جمع وزن محصولات تخصیص برابر باشد
    weight_difference = abs(total_allocation_weight - total_transports_weight)
    if weight_difference > Decimal('0.001'):  # تحمل خطای 0.001 کیلوگرم
        messages.error(
            request, 
            f'جمع وزن‌های حمل‌ها ({total_transports_weight} کیلوگرم) باید با جمع وزن محصولات تخصیص ({total_allocation_weight} کیلوگرم) برابر باشد. '
            f'تفاوت: {weight_difference} کیلوگرم'
        )
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
            
            # تغییر وضعیت تخصیص به pending_vehicle_entry (در انتظار ورود خودرو به کارخانه)
            allocation.allocation_status = 'pending_vehicle_entry'
            allocation.save(update_fields=['allocation_status'])
            
            # وضعیت تخصیص در مراحل مختلف:
            # 1. هنگام اعلام بار: pending_shipping -> pending_vehicle_recruitment
            # 2. بعد از تکمیل جذب خودرو: pending_vehicle_recruitment -> pending_vehicle_entry
            # 3. وقتی همه حمل‌ها به pending_waybill رفتند: pending_vehicle_entry -> pending_loading_completion
            # 4. وقتی همه حمل‌ها به completed یا loaded رفتند: pending_loading_completion -> delivered
            
            bug_logger.info(f"جذب خودرو برای تخصیص {allocation_number} تکمیل شد و وضعیت به pending_vehicle_entry تغییر کرد")
            messages.success(request, f'جذب خودرو برای تخصیص {allocation_number} با موفقیت تکمیل شد و وضعیت به "در انتظار ورود خودرو به کارخانه" تغییر کرد.')
            audit_logger.activity(f"جذب خودرو برای تخصیص {allocation_number} تکمیل شد و وضعیت به pending_vehicle_entry تغییر کرد توسط کاربر {request.user.username}")
            
            return redirect('distribution:vehicle_recruitment_list')
            
    except Exception as e:
        bug_logger.error(f"خطا در تکمیل جذب خودرو: {str(e)}")
        messages.error(request, f'خطا در تکمیل جذب خودرو: {str(e)}')
        return redirect('distribution:vehicle_recruitment_list')

