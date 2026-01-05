from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, Count, Case, When, DecimalField, F, OuterRef, Subquery
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.forms import inlineformset_factory
from django.views.decorators.http import require_http_methods
import logging
import json
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig
from core.ProductFolder.ProductModel import Product
from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from sales.forms.allocation_create_form import CreateAllocationForm, AllocationProductInfoFormSet
from sales.forms.customer_create_form import DeliveryAddressForm
from sales.tables.tables_allocation import AllocationTable
from core.ProductFolder.ProductModel import Product

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_delivery_address_info(postal_code):
    """
    دریافت اطلاعات آدرس تحویل بر اساس کد پستی
    """
    try:
        delivery_address = DeliveryAddress.objects.get(postal_code=postal_code)
        
        # دریافت شماره تلفن‌های مربوط به آدرس تحویل (نه مشتری)
        # توجه: object_id در PhoneNumber یک PositiveIntegerField است، اما postal_code یک string است
        # پس باید postal_code را به integer تبدیل کنیم (اگر فقط اعداد باشد)
        delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
        try:
            # تلاش برای تبدیل postal_code به integer
            postal_code_int = int(postal_code) if postal_code.isdigit() else None
            if postal_code_int:
                phone_numbers = PhoneNumber.objects.filter(
                    content_type=delivery_content_type,
                    object_id=postal_code_int
                ).order_by('-is_primary', 'phone_type')
            else:
                phone_numbers = PhoneNumber.objects.none()
        except (ValueError, TypeError):
            phone_numbers = PhoneNumber.objects.none()
        
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


def calculate_order_product_quantities(order):
    """
    محاسبه مقدار هر محصول در سفارش (کیلوگرم)
    خروجی: دیکشنری {product_id: quantity}
    """
    product_quantities = {}
    for item in order.order_items.all():
        if not item.product_id:
            continue
            
        quantity = 0
        if item.weight_unit == 'kg':
            quantity = float(item.quantity or 0)
        elif item.weight_unit == 'ton':
            quantity = float(item.quantity or 0) * 1000
        elif item.weight_unit == 'bag' and item.bag_weight:
            quantity = float(item.quantity or 0) * float(item.bag_weight)
        elif item.weight_unit == 'piece':
            quantity = float(item.quantity or 0)
            
        product_id = item.product_id
        if product_id in product_quantities:
            product_quantities[product_id] += quantity
        else:
            product_quantities[product_id] = quantity
            
    return product_quantities


def calculate_existing_allocation_product_quantities(order, exclude_allocation_id=None, exclude_allocation_number=None):
    """
    محاسبه مقدار تخصیص یافته فعلی هر محصول (کیلوگرم)
    خروجی: دیکشنری {product_id: quantity}
    """
    product_quantities = {}
    allocations = Allocation.objects.filter(order=order)
    
    if exclude_allocation_id:
        allocations = allocations.exclude(pk=exclude_allocation_id)
    elif exclude_allocation_number:
        allocations = allocations.exclude(allocation_number=exclude_allocation_number)
        
    for allocation in allocations:
        for product_info in allocation.product_infos.all():
            if not product_info.product_id:
                continue
                
            quantity = float(product_info.quantity or 0)
            unit = product_info.unit
            
            # تبدیل به کیلوگرم
            kg_quantity = 0
            if unit == 'kg':
                kg_quantity = quantity
            elif unit == 'ton':
                kg_quantity = quantity * 1000
            elif unit == 'gr':
                kg_quantity = quantity / 1000
            else:
                kg_quantity = quantity
                
            product_id = product_info.product_id
            if product_id in product_quantities:
                product_quantities[product_id] += kg_quantity
            else:
                product_quantities[product_id] = kg_quantity
                
    return product_quantities


def calculate_formset_product_quantities(formset):
    """
    محاسبه مقدار هر محصول از formset (کیلوگرم)
    خروجی: دیکشنری {product_id: quantity}
    """
    product_quantities = {}
    
    for form in formset.forms:
        # بررسی اینکه فرم حذف نشده باشد و cleaned_data داشته باشد
        if hasattr(form, 'cleaned_data') and form.cleaned_data and not form.cleaned_data.get('DELETE', False):
            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity', 0) or 0
            unit = form.cleaned_data.get('unit', '')
            
            if product and quantity and unit:
                try:
                    quantity = float(quantity)
                    
                    # تبدیل به کیلوگرم
                    kg_quantity = 0
                    if unit == 'kg':
                        kg_quantity = quantity
                    elif unit == 'ton':
                        kg_quantity = quantity * 1000
                    elif unit == 'gr':
                        kg_quantity = quantity / 1000
                    # برای سایر واحدها (m3, ltr, cc)، همان مقدار را اضافه می‌کنیم
                    else:
                        kg_quantity = quantity
                        
                    product_id = product.id
                    if product_id in product_quantities:
                        product_quantities[product_id] += kg_quantity
                    else:
                        product_quantities[product_id] = kg_quantity
                except (ValueError, TypeError):
                    pass
                    
    return product_quantities



@login_required
def allocation_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تخصیص»
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار تخصیص")
    
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity("تلاش برای دسترسی به لیست تخصیص بدون دسترسی")
        messages.error(request, 'شما دسترسی به تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_allocation').select_related('customer', 'registered_by')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    # افزودن annotate برای فیلدهای محاسبه شده
    # مهم: ابتدا مقدار سفارش را با استفاده از Subquery محاسبه می‌کنیم
    # تا از تکرار مقادیر به دلیل join های متعدد جلوگیری شود
    
    # محاسبه مقدار سفارش با استفاده از Subquery
    # این کار باعث می‌شود که join های allocations روی محاسبه تأثیر نگذارند
    order_total_subquery = OrderItem.objects.filter(
        order=OuterRef('pk')
    ).values('order').annotate(
        total=Sum(
            Case(
                When(weight_unit='kg', then=F('quantity')),
                When(weight_unit='ton', then=F('quantity') * 1000),
                When(
                    Q(weight_unit='bag') & Q(bag_weight__isnull=False),
                    then=F('quantity') * F('bag_weight')
                ),
                When(weight_unit='piece', then=F('quantity')),
                default=0,
                output_field=DecimalField(max_digits=15, decimal_places=3)
            )
        )
    ).values('total')[:1]
    
    orders_qs = orders_qs.annotate(
        order_total_quantity_kg=Subquery(order_total_subquery, output_field=DecimalField(max_digits=15, decimal_places=3))
    )
    
    # تعداد تخصیص‌ها
    orders_qs = orders_qs.annotate(
        allocations_count=Count('allocations', distinct=True)
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
    
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای ایجاد تخصیص سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # superadmin می‌تواند در هر وضعیتی تخصیص اضافه کند
    if not request.user.is_superuser and order.status != 'pending_allocation':
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
            
            # اعتبارسنجی وزنی به تفکیک محصول
            ordered_products = calculate_order_product_quantities(order)
            existing_allocated_products = calculate_existing_allocation_product_quantities(order)
            new_allocated_products = calculate_formset_product_quantities(formset)
            
            validation_error = None
            
            for product_id, new_quantity in new_allocated_products.items():
                ordered_quantity = ordered_products.get(product_id, 0)
                existing_quantity = existing_allocated_products.get(product_id, 0)
                
                total_product_allocation = existing_quantity + new_quantity
                
                if total_product_allocation > ordered_quantity + 0.001:  # مقایسه با خطای کوچک
                    product_name = Product.objects.get(pk=product_id).name
                    excess = total_product_allocation - ordered_quantity
                    validation_error = (
                        f"مقدار تخصیص محصول '{product_name}' ({total_product_allocation:.2f} کیلوگرم) "
                        f"بیشتر از مقدار سفارش ({ordered_quantity:.2f} کیلوگرم) است. "
                        f"مقدار اضافی: {excess:.2f} کیلوگرم"
                    )
                    break
            
            if validation_error:
                bug_logger.warning(f"خطای اعتبارسنجی وزنی در ایجاد تخصیص سفارش {order_number}: {validation_error}")
                messages.error(request, validation_error)
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
                            # تغییر status همه allocation های این order به 'pending_approval'
                            Allocation.objects.filter(order=order).update(allocation_status='pending_approval')
                            
                            order.status = 'pending_allocation_approval'
                            order.save(update_fields=['status'])
                            bug_logger.info(f"تخصیص {allocation.allocation_number} ایجاد شد و وضعیت سفارش {order_number} به pending_allocation_approval تغییر کرد. همه تخصیص‌ها به 'در انتظار تأیید' تغییر کردند.")
                            messages.success(request, 'تخصیص با موفقیت ایجاد شد و وضعیت سفارش به "در انتظار تأیید تخصیص" تغییر کرد. همه تخصیص‌ها به "در انتظار تأیید" تغییر کردند.')
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

    # محاسبه وضعیت هر محصول برای نمایش در جدول
    product_status_list = []
    ordered_products = calculate_order_product_quantities(order)
    existing_allocated_products = calculate_existing_allocation_product_quantities(order)
    
    for item in order.order_items.all():
        if not item.product_id:
            continue
            
        product_id = item.product_id
        ordered_qty = ordered_products.get(product_id, 0)
        allocated_qty = existing_allocated_products.get(product_id, 0)
        remaining_qty = ordered_qty - allocated_qty
        
        # جلوگیری از تکرار محصول (چون ممکنه چند آیتم با یک محصول داشته باشیم اما گروه‌بندی کردیم)
        # در اینجا فرض بر این است که calculate_order_product_quantities تجمیع کرده است
        # اما ما می‌خواهیم لیست محصولات را بسازیم. بهتر است از دیکشنری استفاده کنیم
        pass

    # ساخت لیست نهایی از دیکشنری‌ها
    unique_product_ids = set(ordered_products.keys()) | set(existing_allocated_products.keys())
    for p_id in unique_product_ids:
        try:
            product = Product.objects.get(pk=p_id)
            ordered_qty = ordered_products.get(p_id, 0)
            allocated_qty = existing_allocated_products.get(p_id, 0)
            remaining_qty = ordered_qty - allocated_qty
            
            product_status_list.append({
                'product_name': product.name,
                'ordered_quantity': ordered_qty,
                'allocated_quantity': allocated_qty,
                'remaining_quantity': remaining_qty,
                'unit': 'kg'  # همه محاسبات به کیلوگرم تبدیل شده‌اند
            })
        except Product.DoesNotExist:
            continue

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
        'product_status_list': product_status_list,  # لیست وضعیت محصولات
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
    
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای ویرایش تخصیص {allocation_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به تخصیص را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)
    allocation = get_object_or_404(Allocation, allocation_number=allocation_number, order=order)
    
    # ذخیره allocation_number فعلی برای استفاده در محاسبات
    original_allocation_number = allocation.allocation_number

    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # بررسی وضعیت allocation - فقط superadmin می‌تواند allocation هایی با status غیر از 'planned' یا رد شده را ویرایش کند
    if not request.user.is_superuser:
        if allocation.is_rejected:
            audit_logger.activity(f"تلاش برای ویرایش تخصیص {allocation_number} رد شده")
            messages.error(request, 'این تخصیص رد شده است و قابل ویرایش نیست.')
            return HttpResponseForbidden('این تخصیص قابل ویرایش نیست.')
        if allocation.allocation_status != 'planned':
            audit_logger.activity(f"تلاش برای ویرایش تخصیص {allocation_number} با وضعیت {allocation.allocation_status}")
            messages.error(request, 'این تخصیص قابل ویرایش نیست. فقط تخصیص‌های در وضعیت "برنامه‌ریزی شده" قابل ویرایش هستند.')
            return HttpResponseForbidden('این تخصیص قابل ویرایش نیست.')

    # محاسبه مقادیر
    order_total = calculate_order_total_quantity(order)
    # محاسبه بدون تخصیص فعلی (با استفاده از allocation_number)
    other_allocations_total = 0
    other_allocations = Allocation.objects.filter(order=order).exclude(allocation_number=original_allocation_number)
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
            
            # اعتبارسنجی وزنی به تفکیک محصول
            ordered_products = calculate_order_product_quantities(order)
            # محاسبه تخصیص‌های دیگر (به جز تخصیص فعلی - با استفاده از allocation_number)
            other_allocated_products = calculate_existing_allocation_product_quantities(order, exclude_allocation_number=original_allocation_number)
            new_allocated_products = calculate_formset_product_quantities(formset)
            
            validation_error = None
            
            for product_id, new_quantity in new_allocated_products.items():
                ordered_quantity = ordered_products.get(product_id, 0)
                other_quantity = other_allocated_products.get(product_id, 0)
                
                total_product_allocation = other_quantity + new_quantity
                
                if total_product_allocation > ordered_quantity + 0.001:  # مقایسه با خطای کوچک
                    product_name = Product.objects.get(pk=product_id).name
                    excess = total_product_allocation - ordered_quantity
                    validation_error = (
                        f"مقدار تخصیص محصول '{product_name}' ({total_product_allocation:.2f} کیلوگرم) "
                        f"بیشتر از مقدار سفارش ({ordered_quantity:.2f} کیلوگرم) است. "
                        f"مقدار اضافی: {excess:.2f} کیلوگرم"
                    )
                    break
            
            if validation_error:
                bug_logger.warning(f"خطای اعتبارسنجی وزنی در ویرایش تخصیص {allocation_number} سفارش {order_number}: {validation_error}")
                messages.error(request, validation_error)
            else:
                try:
                    with transaction.atomic():
                        # بررسی اینکه آیا allocation_number تغییر کرده است
                        new_allocation_number = form.cleaned_data.get('allocation_number')
                        allocation_number_changed = (new_allocation_number != original_allocation_number)
                        
                        if allocation_number_changed:
                            # اگر allocation_number تغییر کرده، باید رکورد قدیمی را حذف و رکورد جدید ایجاد کنیم
                            # ابتدا product_infos را از formset استخراج می‌کنیم
                            product_infos_data = []
                            for form_item in formset.forms:
                                if hasattr(form_item, 'cleaned_data') and form_item.cleaned_data and not form_item.cleaned_data.get('DELETE', False):
                                    product_infos_data.append({
                                        'product': form_item.cleaned_data.get('product'),
                                        'unit': form_item.cleaned_data.get('unit'),
                                        'quantity': form_item.cleaned_data.get('quantity'),
                                    })
                            
                            # حذف رکورد قدیمی (product_infos به صورت خودکار حذف می‌شوند به دلیل CASCADE)
                            allocation.delete()
                            
                            # ایجاد رکورد جدید با allocation_number جدید
                            allocation = form.save(commit=False)
                            allocation.allocation_number = new_allocation_number
                            allocation.save()
                            
                            # ایجاد product_infos جدید برای allocation جدید
                            from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
                            for product_info_data in product_infos_data:
                                if product_info_data['product']:  # فقط اگر محصول انتخاب شده باشد
                                    AllocationProductInfo.objects.create(
                                        allocation=allocation,
                                        product=product_info_data['product'],
                                        unit=product_info_data['unit'],
                                        quantity=product_info_data['quantity'],
                                    )
                        else:
                            # اگر allocation_number تغییر نکرده، همانطور که قبلاً بود save می‌کنیم
                            allocation = form.save()
                            formset.save()
                        
                        # بررسی برابری مقادیر
                        new_allocation_total = calculate_allocation_total_quantity(order)
                        # استفاده از allocation_number جدید (یا قدیمی اگر تغییر نکرده باشد)
                        final_allocation_number = allocation.allocation_number
                        if abs(order_total - new_allocation_total) < 0.001:  # مقایسه با خطای کوچک
                            # تغییر status همه allocation های این order به 'pending_approval'
                            Allocation.objects.filter(order=order).update(allocation_status='pending_approval')
                            
                            if order.status == 'pending_allocation':
                                order.status = 'pending_allocation_approval'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"تخصیص {final_allocation_number} ویرایش شد و وضعیت سفارش {order_number} به pending_allocation_approval تغییر کرد. همه تخصیص‌ها به 'در انتظار تأیید' تغییر کردند.")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد و وضعیت سفارش به "در انتظار تأیید تخصیص" تغییر کرد. همه تخصیص‌ها به "در انتظار تأیید" تغییر کردند.')
                            else:
                                bug_logger.info(f"تخصیص {final_allocation_number} برای سفارش {order_number} ویرایش شد. همه تخصیص‌ها به 'در انتظار تأیید' تغییر کردند.")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد. همه تخصیص‌ها به "در انتظار تأیید" تغییر کردند.')
                        else:
                            # اگر قبلاً در pending_allocation_approval بود و حالا برابر نیست، برگردان به pending_allocation
                            if order.status == 'pending_allocation_approval':
                                order.status = 'pending_allocation'
                                order.save(update_fields=['status'])
                                bug_logger.info(f"تخصیص {final_allocation_number} ویرایش شد و وضعیت سفارش {order_number} به pending_allocation برگشت (مقدار باقیمانده: {order_total - new_allocation_total:.2f} کیلوگرم)")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد. وضعیت سفارش به "در انتظار تخصیص" برگشت.')
                            else:
                                bug_logger.info(f"تخصیص {final_allocation_number} برای سفارش {order_number} ویرایش شد (مقدار باقیمانده: {order_total - new_allocation_total:.2f} کیلوگرم)")
                                messages.success(request, 'تخصیص با موفقیت ویرایش شد.')
                        
                        audit_logger.activity(f"تخصیص {final_allocation_number} برای سفارش {order_number} ویرایش شد")
                        return redirect('sales:allocation_list')
                except Exception as e:
                    bug_logger.error(f"خطا در ویرایش تخصیص {original_allocation_number} برای سفارش {order_number}: {str(e)}", exc_info=True)
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

    # محاسبه وضعیت هر محصول برای نمایش در جدول
    product_status_list = []
    ordered_products = calculate_order_product_quantities(order)
    existing_allocated_products = calculate_existing_allocation_product_quantities(order)
    
    # ساخت لیست نهایی از دیکشنری‌ها
    unique_product_ids = set(ordered_products.keys()) | set(existing_allocated_products.keys())
    for p_id in unique_product_ids:
        try:
            product = Product.objects.get(pk=p_id)
            ordered_qty = ordered_products.get(p_id, 0)
            allocated_qty = existing_allocated_products.get(p_id, 0)
            remaining_qty = ordered_qty - allocated_qty
            
            product_status_list.append({
                'product_name': product.name,
                'ordered_quantity': ordered_qty,
                'allocated_quantity': allocated_qty,
                'remaining_quantity': remaining_qty,
                'unit': 'kg'
            })
        except Product.DoesNotExist:
            continue

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
        'product_status_list': product_status_list,  # لیست وضعیت محصولات
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
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به API اطلاعات آدرس تحویل بدون دسترسی - کد پستی: {postal_code}")
        return JsonResponse({'error': 'شما دسترسی به این بخش ندارید'}, status=403)
    
    delivery_info = get_delivery_address_info(postal_code)
    if delivery_info:
        bug_logger.debug(f"اطلاعات آدرس تحویل برای کد پستی {postal_code} با موفقیت برگردانده شد")
        return JsonResponse(delivery_info)
    else:
        bug_logger.warning(f"آدرس تحویل برای کد پستی {postal_code} یافت نشد")
        return JsonResponse({'error': 'آدرس تحویل یافت نشد'}, status=404)


@login_required
@require_http_methods(["GET"])
def get_delivery_info_rendered_api(request, order_number, postal_code):
    """
    API endpoint برای دریافت اطلاعات آدرس تحویل و رندر HTML
    این endpoint اطلاعات آدرس را بر اساس کد پستی دریافت می‌کند و HTML رندر شده برمی‌گرداند
    با بررسی دسترسی TaskPermission و صاحبیت سفارش
    """
    audit_logger.info(f"درخواست دریافت اطلاعات آدرس تحویل و HTML برای سفارش {order_number} - کد پستی: {postal_code}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به API دریافت اطلاعات آدرس تحویل بدون دسترسی - سفارش: {order_number}")
        return JsonResponse({'error': 'شما دسترسی به این بخش ندارید'}, status=403)
    
    # دریافت سفارش
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        audit_logger.warning(f"سفارش {order_number} برای دریافت اطلاعات آدرس تحویل یافت نشد")
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    
    # بررسی دسترسی به سفارش (کاربر باید مالک سفارش باشد یا superuser)
    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به API دریافت اطلاعات آدرس تحویل سفارش {order_number} متعلق به کاربر دیگر")
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)
    
    # دریافت اطلاعات آدرس تحویل
    delivery_info = get_delivery_address_info(postal_code)
    if not delivery_info:
        bug_logger.warning(f"آدرس تحویل برای کد پستی {postal_code} یافت نشد")
        return JsonResponse({'error': 'آدرس تحویل یافت نشد'}, status=404)
    
    # ساخت HTML برای اطلاعات تحویل
    html_content = f"""
    <div class="info-row">
        <span class="info-label">نام تحویل گیرنده:</span>
        <span class="info-value">{delivery_info.get('recipient_name', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">کد ملی تحویل گیرنده:</span>
        <span class="info-value">{delivery_info.get('recipient_national_id', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">شناسه یکتا تحویل:</span>
        <span class="info-value">{delivery_info.get('unique_delivery_id', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">استان:</span>
        <span class="info-value">{delivery_info.get('province', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">شهر:</span>
        <span class="info-value">{delivery_info.get('city', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">آدرس پستی:</span>
        <span class="info-value">{delivery_info.get('address', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">شماره ثابت هماهنگی تحویل:</span>
        <span class="info-value">{delivery_info.get('landline_phone', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">شماره همراه هماهنگی تحویل:</span>
        <span class="info-value">{delivery_info.get('mobile_phone', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">محدودیت تحویل:</span>
        <span class="info-value">{delivery_info.get('delivery_limit', '-')}</span>
    </div>
    <div class="info-row">
        <span class="info-label">نوع تحویل گیرنده:</span>
        <span class="info-value">{delivery_info.get('recipient_type', '-')}</span>
    </div>
    """
    
    bug_logger.debug(f"اطلاعات آدرس تحویل برای کد پستی {postal_code} به صورت HTML رندر شد")
    return JsonResponse({
        'success': True,
        'html': html_content.strip()
    })


@login_required
@require_http_methods(["GET"])
def postal_code_search_api(request, order_number):
    """
    API endpoint برای جستجوی کد پستی‌های تحویل
    فقط کد پستی‌های متعلق به مشتری سفارش
    """
    audit_logger.info(f"درخواست جستجوی کد پستی برای سفارش {order_number}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به API جستجوی کد پستی بدون دسترسی - سفارش: {order_number}")
        return JsonResponse({'error': 'شما دسترسی به این بخش ندارید'}, status=403)
    
    query = request.GET.get('q', '').strip()
    
    # دریافت سفارش
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        audit_logger.warning(f"سفارش {order_number} برای جستجوی کد پستی یافت نشد")
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    
    # بررسی دسترسی به سفارش (کاربر باید مالک سفارش باشد یا superuser)
    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به API جستجوی کد پستی سفارش {order_number} متعلق به کاربر دیگر")
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)
    
    # فیلتر کردن کد پستی‌ها بر اساس مشتری سفارش
    if order.customer:
        if query:
            # اگر query وجود دارد، جستجو کن
            postal_codes = DeliveryAddress.objects.filter(
                person=order.customer,
                postal_code__icontains=query
            ).order_by('postal_code')[:20]
        else:
            # اگر query خالی است، همه کدهای پستی را برگردان
            postal_codes = DeliveryAddress.objects.filter(
                person=order.customer
            ).order_by('postal_code')[:20]
    else:
        postal_codes = DeliveryAddress.objects.none()
    
    results = []
    for addr in postal_codes:
        # ساخت متن نمایشی با اطلاعات اضافی
        display_text = f"{addr.postal_code}"
        if addr.city or addr.province:
            location_parts = []
            if addr.city:
                location_parts.append(addr.city)
            if addr.province:
                location_parts.append(addr.province)
            if location_parts:
                display_text += f" - {', '.join(location_parts)}"
        if addr.recipient_name:
            display_text += f" ({addr.recipient_name})"
        
        results.append({
            'id': addr.postal_code,
            'text': display_text,
            'postal_code': addr.postal_code,
            'city': addr.city or '',
            'province': addr.province or '',
            'recipient_name': addr.recipient_name or '',
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["POST"])
def create_delivery_address_api(request, order_number):
    """
    API endpoint برای ایجاد آدرس تحویل جدید برای مشتری سفارش
    """
    audit_logger.info(f"درخواست ایجاد آدرس تحویل برای سفارش {order_number}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ALLOCATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به API ایجاد آدرس تحویل بدون دسترسی - سفارش: {order_number}")
        return JsonResponse({'error': 'شما دسترسی به این بخش ندارید'}, status=403)
    
    # دریافت سفارش
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        audit_logger.warning(f"سفارش {order_number} برای ایجاد آدرس تحویل یافت نشد")
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    
    # بررسی دسترسی به سفارش (کاربر باید مالک سفارش باشد یا superuser)
    if not request.user.is_superuser and order.registered_by != request.user:
        audit_logger.activity(f"تلاش برای دسترسی به API ایجاد آدرس تحویل سفارش {order_number} متعلق به کاربر دیگر")
        return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)
    
    # بررسی وجود مشتری
    if not order.customer:
        audit_logger.warning(f"سفارش {order_number} مشتری ندارد")
        return JsonResponse({'error': 'سفارش مشتری ندارد'}, status=400)
    
    # دریافت داده‌های JSON
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        audit_logger.warning(f"داده‌های JSON نامعتبر برای ایجاد آدرس تحویل سفارش {order_number}")
        return JsonResponse({'error': 'داده‌های نامعتبر'}, status=400)
    
    # تبدیل داده‌های JSON به فرمت مناسب برای فرم
    form_data = {
        'postal_code': data.get('postal_code', '').strip(),
        'recipient_name': data.get('recipient_name', '').strip(),
        'recipient_national_id': data.get('recipient_national_id', '').strip(),
        'unique_delivery_id': data.get('unique_delivery_id', '').strip(),
        'province': data.get('province', '').strip(),
        'city': data.get('city', '').strip(),
        'address': data.get('address', '').strip(),
        'delivery_limit': data.get('delivery_limit', '').strip(),
        'recipient_type': data.get('recipient_type', '').strip(),
        'delivery_landline': data.get('landline_phone', '').strip(),
        'delivery_mobile': data.get('mobile_phone', '').strip(),
    }
    
    # استفاده از DeliveryAddressForm برای اعتبارسنجی
    form = DeliveryAddressForm(form_data)
    
    if not form.is_valid():
        # جمع‌آوری خطاهای فرم
        errors = {}
        for field, field_errors in form.errors.items():
            errors[field] = field_errors[0] if field_errors else 'مقدار نامعتبر'
        bug_logger.warning(f"فرم ایجاد آدرس تحویل نامعتبر است: {errors}")
        return JsonResponse({'error': 'داده‌های نامعتبر', 'errors': errors}, status=400)
    
    # بررسی فیلدهای الزامی (بر اساس مدل)
    postal_code = form.cleaned_data.get('postal_code', '').strip()
    recipient_name = form.cleaned_data.get('recipient_name', '').strip()
    province = form.cleaned_data.get('province', '').strip()
    city = form.cleaned_data.get('city', '').strip()
    address = form.cleaned_data.get('address', '').strip()
    
    if not postal_code:
        return JsonResponse({'error': 'کد پستی الزامی است'}, status=400)
    if not recipient_name:
        return JsonResponse({'error': 'نام تحویل گیرنده الزامی است'}, status=400)
    if not province:
        return JsonResponse({'error': 'استان الزامی است'}, status=400)
    if not city:
        return JsonResponse({'error': 'شهر الزامی است'}, status=400)
    if not address:
        return JsonResponse({'error': 'آدرس پستی الزامی است'}, status=400)
    
    # اعتبارسنجی کد پستی: باید دقیقاً 10 رقم باشد
    if not postal_code.isdigit() or len(postal_code) != 10:
        return JsonResponse({'error': 'کد پستی باید دقیقاً 10 رقم باشد'}, status=400)
    
    # اعتبارسنجی کد ملی (در صورت وجود)
    recipient_national_id = form.cleaned_data.get('recipient_national_id', '').strip()
    if recipient_national_id:
        if not recipient_national_id.isdigit() or len(recipient_national_id) != 10:
            return JsonResponse({'error': 'کد ملی تحویل گیرنده باید دقیقاً 10 رقم باشد'}, status=400)
    
    # اعتبارسنجی شماره همراه (در صورت وجود)
    delivery_mobile = form.cleaned_data.get('delivery_mobile', '').strip()
    if delivery_mobile:
        if not delivery_mobile.isdigit() or len(delivery_mobile) != 11 or not delivery_mobile.startswith('09'):
            return JsonResponse({'error': 'شماره همراه باید با 09 شروع شود و 11 رقم باشد'}, status=400)
    
    # اعتبارسنجی شماره ثابت (در صورت وجود)
    delivery_landline = form.cleaned_data.get('delivery_landline', '').strip()
    if delivery_landline:
        if not delivery_landline.isdigit() or len(delivery_landline) != 11 or not delivery_landline.startswith('0'):
            return JsonResponse({'error': 'شماره ثابت باید با 0 شروع شود و 11 رقم باشد'}, status=400)
    
    # بررسی اینکه آیا آدرس با این کد پستی قبلاً وجود دارد
    if DeliveryAddress.objects.filter(postal_code=postal_code).exists():
        audit_logger.warning(f"آدرس تحویل با کد پستی {postal_code} قبلاً وجود دارد")
        return JsonResponse({'error': 'آدرس تحویل با این کد پستی قبلاً وجود دارد'}, status=400)
    
    try:
        with transaction.atomic():
            # ایجاد آدرس تحویل با استفاده از داده‌های validated شده از فرم
            delivery_address = DeliveryAddress.objects.create(
                person=order.customer,
                postal_code=postal_code,
                recipient_name=recipient_name,
                recipient_national_id=recipient_national_id or None,
                unique_delivery_id=form.cleaned_data.get('unique_delivery_id', '').strip() or None,
                province=province,
                city=city,
                address=address,
                delivery_limit=form.cleaned_data.get('delivery_limit', '').strip() or None,
                recipient_type=form.cleaned_data.get('recipient_type', '').strip() or None
            )
            
            # ایجاد شماره تلفن‌ها
            delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
            
            if delivery_mobile:
                PhoneNumber.objects.create(
                    content_type=delivery_content_type,
                    object_id=delivery_address.postal_code,
                    phone_type='mobile',
                    number=delivery_mobile,
                    is_primary=True
                )
            
            if delivery_landline:
                PhoneNumber.objects.create(
                    content_type=delivery_content_type,
                    object_id=delivery_address.postal_code,
                    phone_type='landline',
                    number=delivery_landline,
                    is_primary=False
                )
            
            bug_logger.info(f"آدرس تحویل با کد پستی {postal_code} برای مشتری {order.customer.name} ایجاد شد")
            audit_logger.activity(f"آدرس تحویل با کد پستی {postal_code} برای سفارش {order_number} ایجاد شد")
            
            return JsonResponse({
                'success': True,
                'postal_code': delivery_address.postal_code,
                'message': 'آدرس تحویل با موفقیت ایجاد شد'
            })
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد آدرس تحویل برای سفارش {order_number}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'خطا در ایجاد آدرس تحویل: {str(e)}'}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_delivery_address_api(request, postal_code):
    """
    API endpoint برای حذف آدرس تحویل
    """
    audit_logger.info(f"درخواست حذف آدرس تحویل - کد پستی: {postal_code}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CUSTOMER.value):
        audit_logger.activity(f"تلاش برای دسترسی به API حذف آدرس تحویل بدون دسترسی - کد پستی: {postal_code}")
        return JsonResponse({'error': 'شما دسترسی به این بخش ندارید'}, status=403)
    
    try:
        delivery_address = DeliveryAddress.objects.get(postal_code=postal_code)
        
        # بررسی دسترسی - کاربر باید مالک مشتری باشد یا superuser
        if not request.user.is_superuser and delivery_address.person.registered_by != request.user:
            audit_logger.activity(f"تلاش برای حذف آدرس تحویل متعلق به کاربر دیگر - کد پستی: {postal_code}")
            return JsonResponse({'error': 'دسترسی غیرمجاز'}, status=403)
        
        # حذف شماره‌های تماس مرتبط
        delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
        PhoneNumber.objects.filter(
            content_type=delivery_content_type,
            object_id=postal_code
        ).delete()
        
        # حذف آدرس
        delivery_address.delete()
        
        bug_logger.info(f"آدرس تحویل با کد پستی {postal_code} حذف شد")
        audit_logger.activity(f"آدرس تحویل با کد پستی {postal_code} حذف شد")
        
        return JsonResponse({
            'success': True,
            'message': 'آدرس تحویل با موفقیت حذف شد'
        })
        
    except DeliveryAddress.DoesNotExist:
        bug_logger.warning(f"آدرس تحویل با کد پستی {postal_code} یافت نشد")
        return JsonResponse({'error': 'آدرس تحویل یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در حذف آدرس تحویل - کد پستی {postal_code}: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'خطا در حذف آدرس: {str(e)}'}, status=500)