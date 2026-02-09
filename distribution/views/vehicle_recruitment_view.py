from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

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
from distribution.tables import VehicleRecruitmentTable

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
    
    # بررسی دسترسی فیلدها
    accessible_delivery_fields = get_accessible_delivery_address_fields(request.user)
    
    # دریافت CSRF token
    from django.middleware.csrf import get_token
    csrf_token = get_token(request)
    
    # آماده‌سازی اطلاعات تخصیص‌ها برای جدول
    # استفاده از یک class ساده که allocation را نگه می‌دارد
    class AllocationRow:
        def __init__(self, allocation):
            self.allocation = allocation
            # محاسبه تعداد حمل‌ها برای امکان مرتب‌سازی
            self.transports_count = Transport.objects.filter(allocation=allocation).count()
        
        def __getattr__(self, name):
            # اگر attribute در self وجود نداشت، از allocation بگیر
            if hasattr(self.allocation, name):
                return getattr(self.allocation, name)
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    allocations_data = [AllocationRow(alloc) for alloc in allocations]
    
    # ایجاد جدول
    table = VehicleRecruitmentTable(
        allocations_data,
        accessible_fields=None,  # table خودش محاسبه می‌کند
        user=request.user
    )
    
    # اضافه کردن accessible_delivery_fields و csrf_token به table
    table.accessible_delivery_fields = accessible_delivery_fields
    table.csrf_token = csrf_token
    
    # تنظیم صفحه‌بندی
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    bug_logger.debug(f"تعداد {len(allocations_data)} تخصیص در انتظار جذب خودرو لود شد")
    
    context = {
        'table': table,
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
                
                # محاسبه وزن هر محصول در این تخصیص (به کیلوگرم)
                allocation_product_weights = {}  # {product_id: weight_in_kg}
                alloc_product_infos = AllocationProductInfo.objects.filter(allocation=allocation, product__isnull=False)
                for api in alloc_product_infos:
                    if api.product_id and api.quantity:
                        quantity = Decimal(str(api.quantity))
                        # تبدیل واحد به کیلوگرم
                        if api.unit == 'ton':
                            quantity = quantity * Decimal('1000')
                        elif api.unit == 'gr':
                            quantity = quantity / Decimal('1000')
                        # elif api.unit == 'kg': quantity بدون تغییر
                        
                        if api.product_id in allocation_product_weights:
                            allocation_product_weights[api.product_id] += quantity
                        else:
                            allocation_product_weights[api.product_id] = quantity
                
                # محاسبه وزن هر محصول در حمل‌های موجود این تخصیص (به کیلوگرم)
                transport_product_weights = {}  # {product_id: weight_in_kg}
                existing_transports = Transport.objects.filter(allocation=allocation)
                for transport in existing_transports:
                    transport_products = ProductInfo.objects.filter(transport=transport, product__isnull=False)
                    for tp in transport_products:
                        if tp.product_id and tp.weight:
                            weight_kg = Decimal(str(tp.weight))
                            if tp.product_id in transport_product_weights:
                                transport_product_weights[tp.product_id] += weight_kg
                            else:
                                transport_product_weights[tp.product_id] = weight_kg
                
                # محاسبه وزن محصولات جدید در این حمل
                new_transport_product_weights = {}  # {product_id: weight_in_kg}
                for product_data in selected_products:
                    product = product_data['product']
                    if product and product.pk:
                        weight_kg = Decimal(str(product_data['weight']))
                        if product.pk in new_transport_product_weights:
                            new_transport_product_weights[product.pk] += weight_kg
                        else:
                            new_transport_product_weights[product.pk] = weight_kg
                
                # بررسی اعتبارسنجی برای هر محصول به صورت جداگانه
                validation_errors = []
                from core.ProductFolder.ProductModel import Product
                
                # بررسی اینکه وزن هر محصول در حمل‌ها (شامل حمل جدید) از این تخصیص بیشتر نشود
                for product_id, new_weight in new_transport_product_weights.items():
                    existing_weight = transport_product_weights.get(product_id, Decimal('0'))
                    total_transport_weight = existing_weight + new_weight
                    allocation_weight = allocation_product_weights.get(product_id, Decimal('0'))
                    
                    if total_transport_weight > allocation_weight + Decimal('0.001'):
                        try:
                            product = Product.objects.get(pk=product_id)
                            remaining = allocation_weight - existing_weight
                            validation_errors.append(
                                f'وزن محصول "{product.name}" در حمل‌ها ({total_transport_weight:.2f} کیلوگرم) از وزن این تخصیص ({allocation_weight:.2f} کیلوگرم) بیشتر است. وزن باقیمانده: {remaining:.2f} کیلوگرم'
                            )
                        except Product.DoesNotExist:
                            pass
                
                if validation_errors:
                    messages.error(request, 'خطاهای اعتبارسنجی:\n' + '\n'.join(validation_errors))
                    return redirect('distribution:vehicle_recruitment_list')
                
                # بررسی مجموع وزن (برای اطمینان بیشتر)
                total_allocation_weight = sum(allocation_product_weights.values())
                total_existing_weight = sum(transport_product_weights.values())
                new_total_weight = total_existing_weight + total_products_weight
                if new_total_weight > total_allocation_weight + Decimal('0.001'):
                    messages.error(request, f'جمع وزن‌های حمل‌ها ({new_total_weight:.2f} کیلوگرم) نمی‌تواند از جمع وزن این تخصیص ({total_allocation_weight:.2f} کیلوگرم) بیشتر باشد. وزن باقیمانده: {total_allocation_weight - total_existing_weight:.2f} کیلوگرم')
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
                # وضعیت حمل مستقیماً به pending_vehicle_entry می‌رود
                transport = Transport.objects.create(
                    waybill_number=waybill_number,
                    allocation=allocation,
                    delivery_postal_code=allocation.delivery_postal_code,
                    direction='outbound',
                    carrier_recruitment=carrier_recruitment,
                    vehicle_type_official=vehicle_type_official,
                    driver=driver_person,
                    status='pending_vehicle_entry',
                )
                
                # ایجاد ProductInfo برای هر محصول انتخاب شده
                for product_data in selected_products:
                    ProductInfo.objects.create(
                        transport=transport,
                        product=product_data['product'],
                        weight=product_data['weight'],
                        item_type='product',
                    )
                
                # ایجاد LoadingScheduleInfo و ثبت زمان جذب خودرو
                now = timezone.now()
                LoadingScheduleInfo.objects.create(
                    transport=transport,
                    vehicle_attraction_time=now
                )
                
                # بررسی اینکه آیا وزن حمل‌ها با وزن این تخصیص برابر شده یا نه
                # محاسبه وزن کل حمل‌های این تخصیص (شامل حمل جدید)
                all_transports = Transport.objects.filter(allocation=allocation)
                total_transports_weight_after = Decimal('0')
                for t in all_transports:
                    transport_products = ProductInfo.objects.filter(transport=t)
                    for tp in transport_products:
                        if tp.weight:
                            total_transports_weight_after += tp.weight
                
                # بررسی اینکه آیا وزن حمل‌ها با وزن این تخصیص برابر شده
                # استفاده از total_allocation_weight که قبلاً محاسبه شده
                weight_difference = abs(total_allocation_weight - total_transports_weight_after)
                
                # بررسی اینکه آیا برای همه محصولات وزن کامل شده
                all_products_complete = True
                for product_id in allocation_product_weights.keys():
                    allocation_weight = allocation_product_weights[product_id]
                    transport_weight = transport_product_weights.get(product_id, Decimal('0'))
                    # اضافه کردن وزن محصولات جدید
                    if product_id in new_transport_product_weights:
                        transport_weight += new_transport_product_weights[product_id]
                    
                    if abs(allocation_weight - transport_weight) > Decimal('0.001'):
                        all_products_complete = False
                        break
                
                # اگر هم مجموع وزن و هم وزن هر محصول کامل شده باشد
                if weight_difference <= Decimal('0.001') and all_products_complete:
                    # تغییر وضعیت این تخصیص به pending_vehicle_entry
                    allocation.allocation_status = 'pending_vehicle_entry'
                    allocation.save()
                    
                    bug_logger.info(f"وضعیت تخصیص {allocation_number} به pending_vehicle_entry تغییر کرد (وزن کامل شد)")
                    messages.success(request, f'حمل با موفقیت ایجاد شد و وضعیت این تخصیص به "در انتظار ورود خودرو به کارخانه" تغییر کرد.')
                else:
                    messages.success(request, f'حمل با موفقیت ایجاد شد.')
                
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
                    'quantity': str(api.quantity) if api.quantity else '0',
                    'unit': api.unit or '',
                })
        
        # محاسبه وزن این تخصیص (تبدیل به کیلوگرم)
        total_allocation_weight = Decimal('0')
        allocation_product_weights = {}  # {product_id: weight_in_kg}
        
        # دریافت محصولات این تخصیص
        alloc_product_infos = AllocationProductInfo.objects.filter(allocation=allocation, product__isnull=False)
        for api in alloc_product_infos:
            if api.product_id and api.quantity:
                quantity = Decimal(str(api.quantity))
                # تبدیل واحد به کیلوگرم
                if api.unit == 'ton':
                    quantity = quantity * Decimal('1000')
                elif api.unit == 'gr':
                    quantity = quantity / Decimal('1000')
                # elif api.unit == 'kg': quantity بدون تغییر
                
                total_allocation_weight += quantity
                
                # محاسبه وزن هر محصول
                if api.product_id in allocation_product_weights:
                    allocation_product_weights[api.product_id] += quantity
                else:
                    allocation_product_weights[api.product_id] = quantity
        
        # محاسبه وزن حمل‌های موجود این تخصیص
        existing_transports = Transport.objects.filter(allocation=allocation)
        total_transports_weight = Decimal('0')
        transport_product_weights = {}  # {product_id: weight_in_kg}
        
        for transport in existing_transports:
            transport_products = ProductInfo.objects.filter(transport=transport, product__isnull=False)
            for tp in transport_products:
                if tp.product_id and tp.weight:
                    weight_kg = Decimal(str(tp.weight))
                    total_transports_weight += weight_kg
                    
                    # محاسبه وزن هر محصول
                    if tp.product_id in transport_product_weights:
                        transport_product_weights[tp.product_id] += weight_kg
                    else:
                        transport_product_weights[tp.product_id] = weight_kg
        
        # محاسبه وزن باقیمانده (هم مجموع و هم به تفکیک محصول)
        remaining_weight = total_allocation_weight - total_transports_weight
        
        # محاسبه وزن باقیمانده برای هر محصول
        remaining_product_weights = {}
        for product_id, allocation_weight in allocation_product_weights.items():
            transport_weight = transport_product_weights.get(product_id, Decimal('0'))
            remaining_product_weights[product_id] = str(allocation_weight - transport_weight)
        return JsonResponse({
            'allocation_number': allocation.allocation_number,
            'order_number': allocation.order.order_number if allocation.order else '-',
            'delivery_info': delivery_info,
            'products': products_data,
            'weight_info': {
                'total_allocation_weight': str(total_allocation_weight),
                'total_transports_weight': str(total_transports_weight),
                'remaining_weight': str(remaining_weight),
                'remaining_product_weights': remaining_product_weights,
            }
        })
    
    # در غیر این صورت به لیست برگرد
    return redirect('distribution:vehicle_recruitment_list')

