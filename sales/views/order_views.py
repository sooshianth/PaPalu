from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.db import transaction
from django.db.models import Sum, Case, When, F, DecimalField, Value, Q
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_http_methods
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")
from sales.forms.order_create_form import (
    CreateOrderForm,
    EditOrderForm,
    build_order_item_formset,
    get_accessible_order_fields,
)
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.PersonFolder.PersonModel import Person
from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo
from core.helpers import check_field_access_prefer_edit
from sales.tables import OrderTable
import jdatetime
from decimal import Decimal


@login_required
def create_order_view(request):
    """
    ویو ایجاد سفارش
    - کنترل دسترسی TaskPermission: SALES_CREATE_ORDER
    - کنترل دسترسی‌ فیلدها با FieldAccessRule مشابه ایجاد مشتری
    - استفاده از فرم اقلام به صورت فرم‌ست
    """
    audit_logger.info("درخواست ایجاد سفارش جدید")
    
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_ORDER.value):
        audit_logger.activity("تلاش برای ایجاد سفارش بدون دسترسی")
        messages.error(request, 'شما دسترسی به ایجاد سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if request.method == 'POST':
        # Build temporary instances to compute field-access
        temp_order_form = CreateOrderForm()
        temp_item_form = None
        # Compute access maps
        access_main, access_item = get_accessible_order_fields(
            request.user,
            temp_order_form,
            temp_item_form or build_order_item_formset().form()
        )
        order_form = CreateOrderForm(request.POST, user=request.user, accessible_fields=access_main)
        item_formset = build_order_item_formset(request.POST, accessible_fields=access_item)

        if order_form.is_valid() and item_formset.is_valid():
            try:
                with transaction.atomic():
                    order: Order = order_form.save(commit=False)
                    order.registered_by = request.user
                    # تنظیم وضعیت به "در انتظار صدور پیش فاکتور"
                    order.status = 'pending_proforma_issue'
                    order.save()

                    # Save items
                    items_saved = 0
                    skipped_items = []
                    for idx, form in enumerate(item_formset):
                        if not getattr(form, 'cleaned_data', None):
                            skipped_items.append(f"فرم {idx+1}: بدون cleaned_data")
                            continue
                        # اگر فرم برای حذف علامت خورده باشد، آن را نادیده بگیر
                        if form.cleaned_data.get('DELETE', False):
                            skipped_items.append(f"فرم {idx+1}: علامت حذف")
                            continue
                        product = form.cleaned_data.get('product')
                        weight_unit = form.cleaned_data.get('weight_unit')
                        quantity = form.cleaned_data.get('quantity')
                        unit_price = form.cleaned_data.get('unit_price')
                        
                        # حداقل محصول، واحد، مقدار و قیمت باید وجود داشته باشد
                        if not (product and weight_unit and quantity is not None and unit_price is not None):
                            missing = []
                            if not product: missing.append('محصول')
                            if not weight_unit: missing.append('واحد')
                            if quantity is None: missing.append('مقدار')
                            if unit_price is None: missing.append('قیمت')
                            skipped_items.append(f"فرم {idx+1}: فیلدهای ناقص ({', '.join(missing)})")
                            continue
                        
                        item = form.to_instance(order)
                        item.save()
                        items_saved += 1

                if items_saved == 0:
                    warning_msg = 'سفارش ایجاد شد اما هیچ قلمی ذخیره نشد! لطفاً اطمینان حاصل کنید که اطلاعات اقلام (محصول، واحد، مقدار، قیمت) را کامل وارد کرده‌اید.'
                    if skipped_items:
                        warning_msg += f' اقلام رد شده: {"; ".join(skipped_items)}'
                    bug_logger.warning(f"سفارش ایجاد شد اما هیچ قلمی ذخیره نشد. اقلام رد شده: {len(skipped_items)}")
                    messages.warning(request, warning_msg)
                else:
                    success_msg = f'سفارش با موفقیت ایجاد شد و {items_saved} قلم ثبت شد. تسک بعد: صدور پیش فاکتور.'
                    if skipped_items:
                        success_msg += f' ({len(skipped_items)} قلم رد شد)'
                    bug_logger.info(f"سفارش جدید با {items_saved} قلم ایجاد شد")
                    messages.success(request, success_msg)
                
                # Redirect to order list (proforma functionality will be added later)
                return redirect('sales:order_list')
            except Exception as e:
                bug_logger.error(f"خطا در ایجاد سفارش: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ایجاد سفارش: {str(e)}')
        else:
            bug_logger.warning("فرم ایجاد سفارش معتبر نیست")
            if order_form.errors:
                bug_logger.warning(f"خطاهای فرم: {order_form.errors}")
            if item_formset.errors:
                bug_logger.warning(f"خطاهای فرمست: {item_formset.errors}")
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_order_form = CreateOrderForm()
        temp_item_form = build_order_item_formset().form()
        access_main, access_item = get_accessible_order_fields(request.user, temp_order_form, temp_item_form)
        order_form = CreateOrderForm(user=request.user, accessible_fields=access_main, initial={
            'order_type': 'sale',
            'registration_source': 'expert',
        })
        item_formset = build_order_item_formset(accessible_fields=access_item)

    # Ensure access maps exist in context
    if 'access_main' not in locals() or 'access_item' not in locals():
        access_main, access_item = get_accessible_order_fields(
            request.user,
            order_form if 'order_form' in locals() else CreateOrderForm(),
            build_order_item_formset().form()
        )

    context = {
        'form': order_form,
        'item_formset': item_formset,
        'accessible_fields_main': access_main,
        'accessible_fields_item': access_item,
        'page_title': 'ایجاد سفارش جدید',
        'next_task_label': 'صدور پیش فاکتور',
        'next_task_code': TaskChoices.SALES_ISSUE_PROFORMA.value,
    }
    return render(request, 'order/create_order.html', context)


def get_accessible_order_list_fields(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش سفارش
    """
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {
            'status': True,
            'total_purchase_cost': True,
            'total_order_weight': True,
        }

    # مدل‌ها
    from core.OrderFolder.OrderModel import Order as OrderModel
    from core.OrderFolder.OrderItemModel import OrderItem as OrderItemModel

    mapping = {
        'status': (OrderModel, 'status'),
        'total_purchase_cost': (OrderItemModel, 'total_purchase_cost'),
        'total_order_weight': None,  # محاسبه شده، همیشه نمایش داده می‌شود
    }

    accessible = {}
    for display_name, mapping_value in mapping.items():
        if mapping_value is None:
            # فیلدهایی که نیازی به بررسی دسترسی ندارند
            accessible[display_name] = True
        else:
            model_class, model_field_name = mapping_value
            accessible[display_name] = check_field_access_prefer_edit(
                user,
                model_class,
                model_field_name,
            )

    return accessible


@login_required
def order_list_view(request):
    """
    لیست سفارش‌ها با کنترل دسترسی و نمایش فیلدهای قابل مشاهده
    با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌ها")
    
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_ORDER_LIST.value):
        audit_logger.activity("تلاش برای مشاهده لیست سفارش‌ها بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست سفارش‌ها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if request.user.is_superuser:
        orders_qs = Order.objects.all().select_related('customer', 'registered_by').prefetch_related('order_items').order_by('-created_at')
    else:
        orders_qs = Order.objects.filter(registered_by=request.user).select_related('customer', 'registered_by').prefetch_related('order_items').order_by('-created_at')

    # اعمال جستجو
    if search_query:
        # جستجو در شماره سفارش، نام مشتری و نام کاربری ثبت‌کننده
        orders_qs = orders_qs.filter(
            Q(order_number__icontains=search_query) |
            Q(customer__name__icontains=search_query) |
            Q(registered_by__username__icontains=search_query)
        )
    
    # اعمال فیلتر وضعیت
    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)

    # محاسبه مجموع بهای تمام شده خرید و وزن کل برای هر سفارش با annotate
    # منطق تبدیل واحد: kg = quantity, ton = quantity * 1000, bag = quantity * bag_weight, piece = quantity
    orders_qs = orders_qs.annotate(
        total_purchase_cost=Sum('order_items__total_purchase_cost'),
        total_order_weight=Sum(
            Case(
                When(order_items__weight_unit='kg', then=F('order_items__quantity')),
                When(order_items__weight_unit='ton', then=F('order_items__quantity') * 1000),
                When(order_items__weight_unit='bag', then=Coalesce(F('order_items__quantity') * F('order_items__bag_weight'), Value(0))),
                When(order_items__weight_unit='piece', then=F('order_items__quantity')),
                default=Value(0),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        )
    )

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش برای نمایش لود شد")  

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = get_accessible_order_list_fields(request.user)
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    table = OrderTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 25}).configure(table)

    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست سفارش‌ها',
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'order/order_list.html', context)


@login_required
@require_http_methods(["GET"])
def customer_search_api(request):
    """
    API endpoint برای جستجوی مشتری‌ها
    فقط مشتری‌های کارشناس فروش فعلی (یا همه برای superuser)
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    # فیلتر کردن مشتری‌ها
    if request.user.is_superuser:
        customers = Person.objects.filter(
            type='customer',
            name__icontains=query
        ).order_by('name')[:20]
    else:
        customers = Person.objects.filter(
            type='customer',
            sales_expert=request.user,
            name__icontains=query
        ).order_by('name')[:20]
    
    results = []
    for customer in customers:
        results.append({
            'id': customer.national_id,
            'text': f"{customer.name} ({customer.national_id})"
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def product_info_api(request, product_id):
    """
    API endpoint برای دریافت اطلاعات محصول شامل واحد و همه قیمت‌های معتبر
    """
    if not product_id:
        audit_logger.alert("درخواست API اطلاعات محصول بدون product_id")
        return JsonResponse({'error': 'شناسه محصول الزامی است'}, status=400)
    
    bug_logger.debug(f"درخواست API اطلاعات محصول {product_id}")
    
    try:
        product = Product.objects.get(id=product_id)
        
        # دریافت همه قیمت‌های معتبر (deadline >= today)
        today = jdatetime.date.today()
        valid_prices = ProductFinancialInfo.objects.filter(
            product=product,
            deadline__gte=today
        ).order_by('-created_at')
        
        # تبدیل main_unit به weight_unit
        # mapping: kg -> kg, ton -> ton, bag -> bag, piece -> piece
        # یا اگر main_unit با وزن واحدها match نمی‌کند، سعی می‌کنیم تطبیق دهیم
        main_unit = product.main_unit or 'kg'
        main_unit_lower = main_unit.lower().strip()
        
        # تبدیل واحد محصول به واحد وزن سفارش
        weight_unit_mapping = {
            'kg': 'kg',
            'کیلوگرم': 'kg',
            'kilogram': 'kg',
            'ton': 'ton',
            'تن': 'ton',
            'bag': 'bag',
            'کیسه': 'bag',
            'piece': 'piece',
            'عدد': 'piece',
            'تعداد': 'piece',
        }
        
        weight_unit = weight_unit_mapping.get(main_unit_lower, 'kg')  # پیش‌فرض kg
        
        # ساخت لیست قیمت‌ها
        prices_list = []
        for price_info in valid_prices:
            # ساخت متن نمایشی برای هر قیمت
            price_value = float(price_info.price)
            price_display = f"{price_value:,.0f} ریال"
            if price_info.condition:
                condition_short = price_info.condition[:50] + ('...' if len(price_info.condition) > 50 else '')
                price_display += f" - {condition_short}"
            if price_info.deadline:
                price_display += f" (اعتبار تا {price_info.deadline.strftime('%Y/%m/%d')})"
            
            prices_list.append({
                'id': price_info.id,
                'price': str(price_info.price),
                'display': price_display,
                'deadline': price_info.deadline.strftime('%Y/%m/%d') if price_info.deadline else '',
                'condition': price_info.condition[:100] if price_info.condition else '',
            })
        
        # اطلاعات پاسخ
        data = {
            'main_unit': product.main_unit or '',
            'weight_unit': weight_unit,
            'prices': prices_list,
            'prices_count': len(prices_list),
            'has_price': len(prices_list) > 0,
        }
        
        # برای سازگاری با کد قدیمی، آخرین قیمت را هم اضافه می‌کنیم
        if prices_list:
            latest_price = valid_prices.first()
            data['unit_price'] = str(latest_price.price)
        
        return JsonResponse(data)
    except Product.DoesNotExist:
        bug_logger.warning(f"محصول {product_id} یافت نشد")
        return JsonResponse({'error': 'محصول یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در دریافت اطلاعات محصول {product_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def order_detail_view(request, order_number):
    """
    ویو نمایش جزئیات سفارش
    - کنترل دسترسی TaskPermission: SALES_VIEW_ORDER_DETAIL
    - نمایش اطلاعات سفارش و اقلام آن
    """
    audit_logger.info(f"درخواست مشاهده جزئیات سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_ORDER_DETAIL.value):
        audit_logger.activity("تلاش برای مشاهده جزئیات سفارش بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده جزئیات سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت سفارش
    try:
        if request.user.is_superuser:
            order = Order.objects.select_related('customer', 'registered_by').prefetch_related('order_items__product').get(order_number=order_number)
        else:
            order = Order.objects.select_related('customer', 'registered_by').prefetch_related('order_items__product').get(
                order_number=order_number,
                registered_by=request.user
            )
    except Order.DoesNotExist:
        messages.error(request, 'سفارش مورد نظر یافت نشد.')
        return redirect('sales:order_list')
    
    # محاسبه مجموع بهای تمام شده خرید و وزن کل
    from django.db.models import Sum, Case, When, F, DecimalField, Value
    from django.db.models.functions import Coalesce
    
    order_items = order.order_items.all()
    total_purchase_cost = order_items.aggregate(
        total=Sum('total_purchase_cost')
    )['total'] or 0
    
    # محاسبه وزن کل
    total_weight = 0
    for item in order_items:
        total_weight += item.get_weight_in_kg()
    
    # محاسبه وزن به تن برای نمایش
    total_weight_ton = total_weight / 1000 if total_weight >= 1000 else None
    
    # بررسی دسترسی ویرایش
    can_edit = user_has_task(request.user, TaskChoices.SALES_EDIT_ORDER.value)
    
    context = {
        'order': order,
        'order_items': order_items,
        'total_purchase_cost': total_purchase_cost,
        'total_weight': total_weight,
        'total_weight_ton': total_weight_ton,
        'can_edit': can_edit,
        'page_title': f'جزئیات سفارش {order_number}',
    }
    return render(request, 'order/order_detail.html', context)


@login_required
def edit_order_view(request, order_number):
    """
    ویو ویرایش سفارش
    - کنترل دسترسی TaskPermission: SALES_EDIT_ORDER
    - کنترل دسترسی فیلدها با FieldAccessRule
    - امکان ویرایش سفارش و اقلام آن
    """
    audit_logger.info(f"درخواست ویرایش سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_EDIT_ORDER.value):
        audit_logger.activity("تلاش برای ویرایش سفارش بدون دسترسی")
        messages.error(request, 'شما دسترسی به ویرایش سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت سفارش
    try:
        if request.user.is_superuser:
            order = Order.objects.select_related('customer', 'registered_by').prefetch_related('order_items__product').get(order_number=order_number)
        else:
            order = Order.objects.select_related('customer', 'registered_by').prefetch_related('order_items__product').get(
                order_number=order_number,
                registered_by=request.user
            )
    except Order.DoesNotExist:
        messages.error(request, 'سفارش مورد نظر یافت نشد.')
        return redirect('sales:order_list')
    
    if request.method == 'POST':
        # Build temporary instances to compute field-access
        temp_order_form = EditOrderForm(instance=order)
        temp_item_form = None
        # Compute access maps
        access_main, access_item = get_accessible_order_fields(
            request.user,
            temp_order_form,
            temp_item_form or build_order_item_formset().form()
        )
        order_form = EditOrderForm(request.POST, instance=order, user=request.user, accessible_fields=access_main)
        item_formset = build_order_item_formset(request.POST, accessible_fields=access_item)

        if order_form.is_valid() and item_formset.is_valid():
            try:
                with transaction.atomic():
                    # ذخیره سفارش
                    order = order_form.save(commit=False)
                    order.save()

                    # حذف اقلامی که برای حذف علامت خورده‌اند
                    existing_item_ids = set()
                    for form in item_formset:
                        if not getattr(form, 'cleaned_data', None):
                            continue
                        if form.cleaned_data.get('DELETE', False):
                            # اگر فرم برای حذف علامت خورده، قلم را حذف کن
                            item_id = form.cleaned_data.get('id')
                            if item_id:
                                try:
                                    item = OrderItem.objects.get(id=item_id, order=order)
                                    item.delete()
                                except OrderItem.DoesNotExist:
                                    pass
                            continue
                        
                        item_id = form.cleaned_data.get('id')
                        if item_id:
                            existing_item_ids.add(item_id)
                    
                    # حذف اقلامی که در فرم نیستند (فقط اگر existing_item_ids خالی نباشد)
                    if existing_item_ids:
                        OrderItem.objects.filter(order=order).exclude(id__in=existing_item_ids).delete()
                    
                    # ذخیره یا به‌روزرسانی اقلام
                    items_saved = 0
                    skipped_items = []
                    for idx, form in enumerate(item_formset):
                        if not getattr(form, 'cleaned_data', None):
                            skipped_items.append(f"فرم {idx+1}: بدون cleaned_data")
                            continue
                        # اگر فرم برای حذف علامت خورده باشد، آن را نادیده بگیر
                        if form.cleaned_data.get('DELETE', False):
                            skipped_items.append(f"فرم {idx+1}: علامت حذف")
                            continue
                        
                        product = form.cleaned_data.get('product')
                        weight_unit = form.cleaned_data.get('weight_unit')
                        quantity = form.cleaned_data.get('quantity')
                        unit_price = form.cleaned_data.get('unit_price')
                        
                        # حداقل محصول، واحد، مقدار و قیمت باید وجود داشته باشد
                        if not (product and weight_unit and quantity is not None and unit_price is not None):
                            missing = []
                            if not product: missing.append('محصول')
                            if not weight_unit: missing.append('واحد')
                            if quantity is None: missing.append('مقدار')
                            if unit_price is None: missing.append('قیمت')
                            skipped_items.append(f"فرم {idx+1}: فیلدهای ناقص ({', '.join(missing)})")
                            continue
                        
                        # بررسی اینکه آیا قلم موجود است یا جدید
                        item_id = form.cleaned_data.get('id')
                        if item_id:
                            try:
                                item = OrderItem.objects.get(id=item_id, order=order)
                                # به‌روزرسانی قلم موجود
                                item.product = product
                                item.weight_unit = weight_unit
                                item.bag_weight = form.cleaned_data.get('bag_weight')
                                item.requested_unit = form.cleaned_data.get('requested_unit') or weight_unit
                                item.quantity = quantity
                                item.unit_price = unit_price
                                item.discount = form.cleaned_data.get('discount') or Decimal('0')
                                item.additional_charges = form.cleaned_data.get('additional_charges') or Decimal('0')
                                item.vat_percent = form.cleaned_data.get('vat_percent') or Decimal('0')
                                item.save()
                                items_saved += 1
                            except OrderItem.DoesNotExist:
                                # اگر قلم پیدا نشد، یک قلم جدید ایجاد کن
                                item = form.to_instance(order)
                                item.save()
                                items_saved += 1
                        else:
                            # ایجاد قلم جدید
                            item = form.to_instance(order)
                            item.save()
                            items_saved += 1

                if items_saved == 0:
                    warning_msg = 'سفارش به‌روزرسانی شد اما هیچ قلمی ذخیره نشد!'
                    if skipped_items:
                        warning_msg += f' اقلام رد شده: {"; ".join(skipped_items)}'
                    bug_logger.warning(f"سفارش به‌روزرسانی شد اما هیچ قلمی ذخیره نشد. اقلام رد شده: {len(skipped_items)}")
                    messages.warning(request, warning_msg)
                else:
                    success_msg = f'سفارش با موفقیت به‌روزرسانی شد و {items_saved} قلم ثبت شد.'
                    if skipped_items:
                        success_msg += f' ({len(skipped_items)} قلم رد شد)'
                    bug_logger.info(f"سفارش {order_number} با {items_saved} قلم به‌روزرسانی شد")
                    messages.success(request, success_msg)
                
                return redirect('sales:order_detail', order_number=order.order_number)
            except Exception as e:
                bug_logger.error(f"خطا در ویرایش سفارش: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ویرایش سفارش: {str(e)}')
        else:
            bug_logger.warning("فرم ویرایش سفارش معتبر نیست")
            if order_form.errors:
                bug_logger.warning(f"خطاهای فرم: {order_form.errors}")
            if item_formset.errors:
                bug_logger.warning(f"خطاهای فرمست: {item_formset.errors}")
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        # ایجاد فرم‌ها با داده‌های موجود
        temp_order_form = EditOrderForm(instance=order)
        temp_item_form = build_order_item_formset().form()
        access_main, access_item = get_accessible_order_fields(request.user, temp_order_form, temp_item_form)
        
        order_form = EditOrderForm(instance=order, user=request.user, accessible_fields=access_main)
        
        # ایجاد formset با اقلام موجود - استفاده از prefix برای جلوگیری از تداخل
        from django.forms import formset_factory
        from sales.forms.order_create_form import OrderItemForm, RequiredOrderItemFormSet
        
        ItemFormSet = formset_factory(
            form=OrderItemForm,
            formset=RequiredOrderItemFormSet,
            extra=0,  # برای ویرایش، فرم اضافی نمی‌خواهیم
            can_delete=True
        )
        
        # ساخت data dictionary برای formset
        formset_data = {}
        items = list(order.order_items.all())
        formset_data['form-TOTAL_FORMS'] = len(items)  # فقط اقلام موجود
        formset_data['form-INITIAL_FORMS'] = len(items)
        formset_data['form-MIN_NUM_FORMS'] = 0
        formset_data['form-MAX_NUM_FORMS'] = 1000
        
        for idx, item in enumerate(items):
            prefix = f'form-{idx}'
            formset_data[f'{prefix}-id'] = item.id
            formset_data[f'{prefix}-product'] = item.product.id if item.product else ''
            formset_data[f'{prefix}-weight_unit'] = item.weight_unit or 'kg'
            formset_data[f'{prefix}-bag_weight'] = item.bag_weight or ''
            formset_data[f'{prefix}-requested_unit'] = item.requested_unit or item.weight_unit or 'kg'
            formset_data[f'{prefix}-quantity'] = item.quantity or ''
            formset_data[f'{prefix}-unit_price'] = item.unit_price or ''
            formset_data[f'{prefix}-discount'] = item.discount or '0'
            formset_data[f'{prefix}-additional_charges'] = item.additional_charges or '0'
            formset_data[f'{prefix}-vat_percent'] = item.vat_percent or '0'
            formset_data[f'{prefix}-DELETE'] = False
        
        item_formset = ItemFormSet(formset_data, form_kwargs={'accessible_fields': access_item})

    # Ensure access maps exist in context
    if 'access_main' not in locals() or 'access_item' not in locals():
        access_main, access_item = get_accessible_order_fields(
            request.user,
            order_form if 'order_form' in locals() else EditOrderForm(instance=order),
            build_order_item_formset().form()
        )

    context = {
        'form': order_form,
        'item_formset': item_formset,
        'order': order,
        'accessible_fields_main': access_main,
        'accessible_fields_item': access_item,
        'page_title': f'ویرایش سفارش {order_number}',
    }
    return render(request, 'order/order_edit.html', context)


