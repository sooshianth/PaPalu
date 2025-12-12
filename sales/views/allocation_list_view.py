from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, Count, Case, When, DecimalField, F
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.forms import inlineformset_factory
import logging
import json
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from sales.forms.allocation_create_form import CreateAllocationForm, AllocationProductInfoFormSet
from sales.tables.tables_allocation import AllocationTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_delivery_address_info(postal_code):
    """
    دریافت اطلاعات آدرس تحویل بر اساس کد پستی
    """
    try:
        delivery_address = DeliveryAddress.objects.get(postal_code=postal_code)
        person = delivery_address.person
        
        # دریافت شماره تلفن‌ها
        person_content_type = ContentType.objects.get_for_model(person)
        phone_numbers = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=person.national_id
        ).order_by('-is_primary', 'phone_type')
        
        landline_phone = phone_numbers.filter(phone_type='landline').first()
        mobile_phone = phone_numbers.filter(phone_type='mobile').first()
        
        bug_logger.debug(f"اطلاعات آدرس تحویل برای کد پستی {postal_code} لود شد")
        
        return {
            'recipient_name': delivery_address.recipient_name or '-',
            'recipient_national_id': delivery_address.recipient_national_id or '-',
            'unique_delivery_id': delivery_address.unique_delivery_id or '-',
            'province': delivery_address.province or '-',
            'city': delivery_address.city or '-',
            'address': delivery_address.address or '-',
            'landline_phone': landline_phone.number if landline_phone else '-',
            'mobile_phone': mobile_phone.number if mobile_phone else '-',
            'delivery_limit': delivery_address.delivery_limit or '-',
            'recipient_type': delivery_address.get_recipient_type_display() if delivery_address.recipient_type else '-',
        }
    except DeliveryAddress.DoesNotExist:
        bug_logger.debug(f"آدرس تحویل برای کد پستی {postal_code} یافت نشد")
        return None


def calculate_order_total_quantity(order):
    """
    محاسبه مجموع مقدار محصولات سفارش (تبدیل به کیلوگرم)
    """
    total_quantity = 0
    for item in order.order_items.all():
        if item.weight_unit == 'kg':
            total_quantity += float(item.quantity or 0)
        elif item.weight_unit == 'ton':
            total_quantity += float(item.quantity or 0) * 1000
        elif item.weight_unit == 'bag' and item.bag_weight:
            total_quantity += float(item.quantity or 0) * float(item.bag_weight)
        elif item.weight_unit == 'piece':
            total_quantity += float(item.quantity or 0)
    bug_logger.debug(f"مقدار کل سفارش {order.order_number} محاسبه شد: {total_quantity} کیلوگرم")
    return total_quantity


def calculate_allocation_total_quantity(order):
    """
    محاسبه مجموع مقدار محصولات همه تخصیص‌های یک سفارش (تبدیل به کیلوگرم)
    """
    total_quantity = 0
    allocations = Allocation.objects.filter(order=order)
    
    for allocation in allocations:
        for product_info in allocation.product_infos.all():
            quantity = float(product_info.quantity or 0)
            unit = product_info.unit
            
            # تبدیل به کیلوگرم
            if unit == 'kg':
                total_quantity += quantity
            elif unit == 'ton':
                total_quantity += quantity * 1000
            elif unit == 'gr':
                total_quantity += quantity / 1000
            # برای سایر واحدها، همان مقدار را اضافه می‌کنیم
    
    bug_logger.debug(f"مقدار کل تخصیص‌های سفارش {order.order_number} محاسبه شد: {total_quantity} کیلوگرم")
    return total_quantity


def calculate_formset_total_quantity(formset):
    """
    محاسبه مجموع مقدار محصولات از formset (تبدیل به کیلوگرم)
    برای validation قبل از ذخیره
    این تابع باید بعد از formset.is_valid() صدا زده شود
    """
    total_quantity = 0
    
    for form in formset.forms:
        # بررسی اینکه فرم حذف نشده باشد و cleaned_data داشته باشد
        if hasattr(form, 'cleaned_data') and form.cleaned_data and not form.cleaned_data.get('DELETE', False):
            quantity = form.cleaned_data.get('quantity', 0) or 0
            unit = form.cleaned_data.get('unit', '')
            
            if quantity and unit:
                try:
                    quantity = float(quantity)
                    
                    # تبدیل به کیلوگرم
                    if unit == 'kg':
                        total_quantity += quantity
                    elif unit == 'ton':
                        total_quantity += quantity * 1000
                    elif unit == 'gr':
                        total_quantity += quantity / 1000
                    # برای سایر واحدها (m3, ltr, cc)، همان مقدار را اضافه می‌کنیم
                    else:
                        total_quantity += quantity
                except (ValueError, TypeError):
                    # در صورت خطا در تبدیل، مقدار را نادیده می‌گیریم
                    pass
    
    return total_quantity


@login_required
def allocation_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تخصیص»
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تخصیص")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity("تلاش برای دسترسی به لیست تخصیص بدون دسترسی")
        messages.error(request, 'شما دسترسی به تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_allocation').select_related('customer', 'registered_by')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    # افزودن annotate برای فیلدهای محاسبه شده
    
    # تعداد تخصیص‌ها
    orders_qs = orders_qs.annotate(
        allocations_count=Count('allocations', distinct=True)
    )
    
    # محاسبه مقدار سفارش (کیلوگرم) - استفاده از Sum با Case/When برای تبدیل واحدها
    orders_qs = orders_qs.annotate(
        order_total_quantity_kg=Sum(
            Case(
                When(order_items__weight_unit='kg', then=F('order_items__quantity')),
                When(order_items__weight_unit='ton', then=F('order_items__quantity') * 1000),
                When(
                    Q(order_items__weight_unit='bag') & Q(order_items__bag_weight__isnull=False),
                    then=F('order_items__quantity') * F('order_items__bag_weight')
                ),
                When(order_items__weight_unit='piece', then=F('order_items__quantity')),
                default=0,
                output_field=DecimalField(max_digits=15, decimal_places=3)
            )
        )
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
    
    # مرتب‌سازی پیش‌فرض
    orders_qs = orders_qs.order_by('-created_at')

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار تخصیص لود شد")
    
    # محاسبه فیلدهای قابل دسترسی (در صورت نیاز)
    # برای حال حاضر، همه فیلدها قابل دسترسی هستند
    accessible_fields = None
    
    # ایجاد جدول با django-tables2
    table = AllocationTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    if orders_qs.count() > 0:
        bug_logger.info("لیست سفارش‌های در انتظار تخصیص با موفقیت نمایش داده شد")

    context = {
        'table': table,
        'page_title': 'سفارش‌های در انتظار تخصیص',
    }
    return render(request, 'allocation/allocation_list.html', context)


@login_required
def allocation_create_view(request, order_number):
    """
    ایجاد تخصیص جدید برای یک سفارش
    """
    audit_logger.info(f"درخواست ایجاد تخصیص برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity(f"تلاش برای ایجاد تخصیص سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_allocation':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_allocation می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای تخصیص نیست.')
        return redirect('sales:allocation_list')

    # محاسبه مقادیر
    order_total = calculate_order_total_quantity(order)
    allocation_total = calculate_allocation_total_quantity(order)
    remaining = order_total - allocation_total
    
    bug_logger.debug(f"مقدار باقیمانده برای تخصیص سفارش {order_number}: {remaining} کیلوگرم")

    if request.method == 'POST':
        form = CreateAllocationForm(request.POST, order=order)
        formset = AllocationProductInfoFormSet(request.POST, instance=None, order=order)
        
        if form.is_valid() and formset.is_valid():
            # محاسبه مقدار تخصیص جدید از formset
            new_allocation_quantity = calculate_formset_total_quantity(formset)
            
            # محاسبه مجموع تخصیص‌های موجود
            existing_allocation_total = calculate_allocation_total_quantity(order)
            
            # بررسی اینکه مجموع تخصیص‌ها از مقدار کل سفارش بیشتر نشود
            total_after_allocation = existing_allocation_total + new_allocation_quantity
            
            if total_after_allocation > order_total + 0.001:  # مقایسه با خطای کوچک
                excess = total_after_allocation - order_total
                bug_logger.warning(f"تلاش برای ایجاد تخصیص بیشتر از مقدار کل سفارش {order_number}. مقدار اضافی: {excess:.2f} کیلوگرم")
                messages.error(
                    request, 
                    f'مجموع تخصیص‌ها نمی‌تواند بیشتر از مقدار کل سفارش باشد. '
                    f'مقدار کل سفارش: {order_total:.2f} کیلوگرم، '
                    f'تخصیص‌های موجود: {existing_allocation_total:.2f} کیلوگرم، '
                    f'تخصیص جدید: {new_allocation_quantity:.2f} کیلوگرم. '
                    f'مقدار اضافی: {excess:.2f} کیلوگرم'
                )
            else:
                try:
                    with transaction.atomic():
                        allocation = form.save(commit=False)
                        allocation.order = order
                        allocation.allocation_status = 'planned'
                        allocation.save()
                        
                        # ذخیره اقلام محصول - تنظیم instance و ذخیره
                        formset.instance = allocation
                        # برای formset، باید instance را به صورت صحیح تنظیم کنیم
                        for form in formset.forms:
                            form.instance.allocation = allocation
                        formset.save()
                        
                        # بررسی برابری مقادیر
                        new_allocation_total = calculate_allocation_total_quantity(order)
                        if abs(order_total - new_allocation_total) < 0.001:  # مقایسه با خطای کوچک
                            order.status = 'pending_allocation_approval'
                            order.save(update_fields=['status'])
                            bug_logger.info(f"تخصیص {allocation.allocation_number} ایجاد شد و وضعیت سفارش {order_number} به pending_allocation_approval تغییر کرد")
                            messages.success(request, 'تخصیص با موفقیت ایجاد شد و وضعیت سفارش به "در انتظار تأیید تخصیص" تغییر کرد.')
                        else:
                            bug_logger.info(f"تخصیص {allocation.allocation_number} برای سفارش {order_number} ایجاد شد (مقدار باقیمانده: {order_total - new_allocation_total:.2f} کیلوگرم)")
                            messages.success(request, 'تخصیص با موفقیت ایجاد شد.')
                        
                        audit_logger.activity(f"تخصیص {allocation.allocation_number} برای سفارش {order_number} ایجاد شد")
                        return redirect('sales:allocation_list')
                except Exception as e:
                    bug_logger.error(f"خطا در ایجاد تخصیص برای سفارش {order_number}: {str(e)}")
                    messages.error(request, f'خطا در ایجاد تخصیص: {str(e)}')
        else:
            bug_logger.warning(f"فرم ایجاد تخصیص برای سفارش {order_number} نامعتبر است")
    else:
        form = CreateAllocationForm(order=order)
        formset = AllocationProductInfoFormSet(instance=None, order=order)

    # دریافت اطلاعات آدرس تحویل در صورت وجود
    delivery_info = None
    if request.method == 'POST' and form.is_valid() and 'delivery_postal_code' in form.cleaned_data:
        delivery_info = get_delivery_address_info(form.cleaned_data['delivery_postal_code'])
    
    # دریافت لیست آدرس‌های تحویل برای نمایش در تمپلیت
    delivery_addresses = []
    if order and order.customer:
        delivery_addresses = DeliveryAddress.objects.filter(person=order.customer)
    
    # ایجاد mapping واحدها برای هر محصول در سفارش
    # این mapping برای JavaScript استفاده می‌شود تا واحد را به صورت خودکار تنظیم کند
    product_unit_mapping = {}
    if order:
        for order_item in order.order_items.all():
            if order_item.product_id:
                # تبدیل واحد OrderItem به واحد AllocationProductInfo
                unit_mapping = {
                    'kg': 'kg',
                    'ton': 'ton',
                    'bag': 'kg',  # کیسه به کیلوگرم تبدیل می‌شود
                    'piece': 'kg',  # عدد به کیلوگرم تبدیل می‌شود
                }
                default_unit = unit_mapping.get(order_item.weight_unit, 'kg')
                # اگر محصول قبلاً در mapping وجود دارد، از اولین واحد استفاده می‌کنیم
                # کلید را به string تبدیل می‌کنیم برای سازگاری با JavaScript
                product_id_str = str(order_item.product_id)
                if product_id_str not in product_unit_mapping:
                    product_unit_mapping[product_id_str] = default_unit
    
    # تبدیل به JSON برای استفاده در JavaScript
    product_unit_mapping_json = json.dumps(product_unit_mapping)

    context = {
        'form': form,
        'formset': formset,
        'order': order,
        'order_total': order_total,
        'allocation_total': allocation_total,
        'remaining': remaining,
        'delivery_info': delivery_info,
        'delivery_addresses': delivery_addresses,
        'product_unit_mapping': product_unit_mapping_json,
        'page_title': f'ایجاد تخصیص برای سفارش {order_number}',
    }
    return render(request, 'allocation/allocation_create.html', context)


@login_required
def allocation_edit_view(request, order_number, allocation_number):
    """
    ویرایش تخصیص موجود
    """
    audit_logger.info(f"درخواست ویرایش تخصیص {allocation_number} برای سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        audit_logger.activity(f"تلاش برای ویرایش تخصیص {allocation_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number, order=order)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # محاسبه مقادیر
    order_total = calculate_order_total_quantity(order)
    # محاسبه بدون تخصیص فعلی
    other_allocations_total = 0
    other_allocations = Allocation.objects.filter(order=order).exclude(pk=allocation.pk)
    for other_allocation in other_allocations:
        for product_info in other_allocation.product_infos.all():
            quantity = float(product_info.quantity or 0)
            unit = product_info.unit
            if unit == 'kg':
                other_allocations_total += quantity
            elif unit == 'ton':
                other_allocations_total += quantity * 1000
            elif unit == 'gr':
                other_allocations_total += quantity / 1000

    if request.method == 'POST':
        form = CreateAllocationForm(request.POST, instance=allocation, order=order)
        formset = AllocationProductInfoFormSet(request.POST, instance=allocation, order=order)
        
        if form.is_valid() and formset.is_valid():
            # محاسبه مقدار تخصیص ویرایش شده از formset
            edited_allocation_quantity = calculate_formset_total_quantity(formset)
            
            # محاسبه مجموع تخصیص‌های دیگر (غیر از تخصیص فعلی)
            # other_allocations_total قبلاً محاسبه شده است
            
            # بررسی اینکه مجموع تخصیص‌ها از مقدار کل سفارش بیشتر نشود
            total_after_edit = other_allocations_total + edited_allocation_quantity
            
            if total_after_edit > order_total + 0.001:  # مقایسه با خطای کوچک
                excess = total_after_edit - order_total
                bug_logger.warning(f"تلاش برای ویرایش تخصیص {allocation_number} که باعث می‌شود مجموع تخصیص‌ها بیشتر از مقدار کل سفارش {order_number} شود. مقدار اضافی: {excess:.2f} کیلوگرم")
                messages.error(
                    request, 
                    f'مجموع تخصیص‌ها نمی‌تواند بیشتر از مقدار کل سفارش باشد. '
                    f'مقدار کل سفارش: {order_total:.2f} کیلوگرم، '
                    f'سایر تخصیص‌ها: {other_allocations_total:.2f} کیلوگرم، '
                    f'تخصیص ویرایش شده: {edited_allocation_quantity:.2f} کیلوگرم. '
                    f'مقدار اضافی: {excess:.2f} کیلوگرم'
                )
            else:
                try:
                    with transaction.atomic():
                        allocation = form.save()
                        formset.save()
                        
                        # بررسی برابری مقادیر
                        new_allocation_total = calculate_allocation_total_quantity(order)
                        if abs(order_total - new_allocation_total) < 0.001:  # مقایسه با خطای کوچک
                            if order.status == 'pending_allocation':
                                order.status = 'pending_allocation_approval'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"تخصیص {allocation_number} ویرایش شد و وضعیت سفارش {order_number} به pending_allocation_approval تغییر کرد")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد و وضعیت سفارش به "در انتظار تأیید تخصیص" تغییر کرد.')
                            else:
                                bug_logger.info(f"تخصیص {allocation_number} برای سفارش {order_number} ویرایش شد")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد.')
                        else:
                            # اگر قبلاً در pending_allocation_approval بود و حالا برابر نیست، برگردان به pending_allocation
                            if order.status == 'pending_allocation_approval':
                                order.status = 'pending_allocation'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"تخصیص {allocation_number} ویرایش شد و وضعیت سفارش {order_number} به pending_allocation برگشت (مقدار باقیمانده: {order_total - new_allocation_total:.2f} کیلوگرم)")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد. وضعیت سفارش به "در انتظار تخصیص" برگشت.')
                            else:
                                bug_logger.info(f"تخصیص {allocation_number} برای سفارش {order_number} ویرایش شد (مقدار باقیمانده: {order_total - new_allocation_total:.2f} کیلوگرم)")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد.')
                        
                        audit_logger.activity(f"تخصیص {allocation_number} برای سفارش {order_number} ویرایش شد")
                        return redirect('sales:allocation_list')
                except Exception as e:
                    bug_logger.error(f"خطا در ویرایش تخصیص {allocation_number} برای سفارش {order_number}: {str(e)}")
                    messages.error(request, f'خطا در ویرایش تخصیص: {str(e)}')
        else:
            bug_logger.warning(f"فرم ویرایش تخصیص {allocation_number} برای سفارش {order_number} نامعتبر است")
    else:
        form = CreateAllocationForm(instance=allocation, order=order)
        formset = AllocationProductInfoFormSet(instance=allocation, order=order)

    # محاسبه مقدار فعلی این تخصیص
    current_allocation_total = 0
    for product_info in allocation.product_infos.all():
        quantity = float(product_info.quantity or 0)
        unit = product_info.unit
        if unit == 'kg':
            current_allocation_total += quantity
        elif unit == 'ton':
            current_allocation_total += quantity * 1000
        elif unit == 'gr':
            current_allocation_total += quantity / 1000

    # دریافت اطلاعات آدرس تحویل
    delivery_info = None
    if allocation.delivery_postal_code:
        delivery_info = get_delivery_address_info(allocation.delivery_postal_code)
    
    # دریافت لیست آدرس‌های تحویل برای نمایش در تمپلیت
    delivery_addresses = []
    if order and order.customer:
        delivery_addresses = DeliveryAddress.objects.filter(person=order.customer)
    
    # ایجاد mapping واحدها برای هر محصول در سفارش
    # این mapping برای JavaScript استفاده می‌شود تا واحد را به صورت خودکار تنظیم کند
    product_unit_mapping = {}
    if order:
        for order_item in order.order_items.all():
            if order_item.product_id:
                # تبدیل واحد OrderItem به واحد AllocationProductInfo
                unit_mapping = {
                    'kg': 'kg',
                    'ton': 'ton',
                    'bag': 'kg',  # کیسه به کیلوگرم تبدیل می‌شود
                    'piece': 'kg',  # عدد به کیلوگرم تبدیل می‌شود
                }
                default_unit = unit_mapping.get(order_item.weight_unit, 'kg')
                # اگر محصول قبلاً در mapping وجود دارد، از اولین واحد استفاده می‌کنیم
                # کلید را به string تبدیل می‌کنیم برای سازگاری با JavaScript
                product_id_str = str(order_item.product_id)
                if product_id_str not in product_unit_mapping:
                    product_unit_mapping[product_id_str] = default_unit
    
    # تبدیل به JSON برای استفاده در JavaScript
    product_unit_mapping_json = json.dumps(product_unit_mapping)

    context = {
        'form': form,
        'formset': formset,
        'order': order,
        'allocation': allocation,
        'order_total': order_total,
        'other_allocations_total': other_allocations_total,
        'current_allocation_total': current_allocation_total,
        'remaining': order_total - other_allocations_total - current_allocation_total,
        'delivery_info': delivery_info,
        'delivery_addresses': delivery_addresses,
        'product_unit_mapping': product_unit_mapping_json,
        'page_title': f'ویرایش تخصیص {allocation_number}',
    }
    return render(request, 'allocation/allocation_edit.html', context)


@login_required
def get_delivery_info_api(request, postal_code):
    """
    API برای دریافت اطلاعات آدرس تحویل بر اساس کد پستی
    """
    audit_logger.info(f"درخواست دریافت اطلاعات آدرس تحویل برای کد پستی {postal_code}")
    
    if not request.user.is_authenticated:
        audit_logger.alert(f"تلاش برای دسترسی به API اطلاعات آدرس تحویل بدون احراز هویت - کد پستی: {postal_code}")
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    delivery_info = get_delivery_address_info(postal_code)
    if delivery_info:
        bug_logger.debug(f"اطلاعات آدرس تحویل برای کد پستی {postal_code} با موفقیت برگردانده شد")
        return JsonResponse(delivery_info)
    else:
        bug_logger.warning(f"آدرس تحویل برای کد پستی {postal_code} یافت نشد")
        return JsonResponse({'error': 'آدرس تحویل یافت نشد'}, status=404)

