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
from sales.tables.tables import OrderTable
import jdatetime
from decimal import Decimal


def can_edit_order(order):
    """
    بررسی اینکه آیا سفارش قابل ویرایش است یا نه
    فقط در دو وضعیت 'pending_proforma_issue' و 'pending_customer_proforma_upload' قابل ویرایش است
    """
    if not order or not order.status:
        return False  # اگر وضعیت ندارد، قابل ویرایش نیست
    
    # فقط برای سفارش‌های فروش این محدودیت اعمال می‌شود
    if order.order_type != 'sale':
        # برای سفارش‌های خرید، منطق قبلی را حفظ می‌کنیم
        non_editable_statuses = [
            'pending_accounting_approval',
            'pending_allocation',
            'pending_allocation_approval',
            'pending_factory',
            'pending_unloading_approval',
            'pending_settlement',
            'pending_settlement_approval',
            'cancelled',
            'archived',
        ]
        return order.status not in non_editable_statuses
    
    # برای سفارش‌های فروش: فقط در دو وضعیت قابل ویرایش
    editable_statuses = [
        'pending_proforma_issue',
        'pending_customer_proforma_upload',
    ]
    
    return order.status in editable_statuses


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

    # استفاده از select_related به جای prefetch_related برای جلوگیری از خطای Decimal
    # prefetch_related ممکن است با مقادیر Decimal نامعتبر مشکل داشته باشد
    if request.user.is_superuser:
        orders_qs = Order.objects.filter(order_type='sale').select_related('customer', 'registered_by').order_by('-created_at') 
    else:
        orders_qs = Order.objects.filter(registered_by=request.user, order_type='sale').select_related('customer', 'registered_by').order_by('-created_at')

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
    # استفاده از try-except برای handle کردن مقادیر Decimal نامعتبر
    try:
        from core.OrderFolder.OrderModel import OrderChangeLog
        from django.db.models import Exists, OuterRef
        
        orders_qs = orders_qs.annotate(
            total_purchase_cost=Sum('order_items__total_purchase_cost'),
            total_order_weight=Sum(
                Case(
                    When(order_items__weight_unit='kg', then=F('order_items__quantity')),
                    When(order_items__weight_unit='ton', then=F('order_items__quantity') * 1000),
                    When(order_items__weight_unit='bag', then=Coalesce(F('order_items__quantity') * F('order_items__bag_weight'), Value(0))),
                    When(order_items__weight_unit='piece', then=F('order_items__quantity')),
                    default=Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=0)
                )
            ),
            # بررسی وجود تاریخچه تغییرات
            has_change_history=Exists(
                OrderChangeLog.objects.filter(order=OuterRef('pk'))
            )
        )
        bug_logger.debug(f"تعداد {orders_qs.count()} سفارش برای نمایش لود شد")
    except Exception as e:
        bug_logger.error(f"خطا در annotate سفارش‌ها: {e}")
        # در صورت خطا، annotate را بدون محاسبه انجام می‌دهیم
        orders_qs = orders_qs.annotate(
            total_purchase_cost=Value(0, output_field=DecimalField(max_digits=15, decimal_places=0)),
            total_order_weight=Value(0, output_field=DecimalField(max_digits=15, decimal_places=0))
        )  

    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = get_accessible_order_list_fields(request.user)
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    # استفاده از try-except برای handle کردن خطاهای Decimal در هنگام render جدول
    try:
        table = OrderTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
        RequestConfig(request, paginate={'per_page': 25}).configure(table)
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد جدول سفارش‌ها: {e}")
        # در صورت خطا، یک queryset خالی برمی‌گردانیم
        from django.db.models import Q
        orders_qs = Order.objects.none()
        table = OrderTable(orders_qs, user=request.user, accessible_fields=accessible_fields)
        RequestConfig(request, paginate={'per_page': 25}).configure(table)
        messages.error(request, 'خطا در بارگذاری لیست سفارش‌ها. لطفاً داده‌ها را بررسی کنید.')

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
        # اگر کوئری خالی است، 20 مشتری اخیر را برگردان
        if request.user.is_superuser:
            customers = Person.objects.filter(
                type='customer'
            ).order_by('name')[:20]
        else:
            customers = Person.objects.filter(
                type='customer',
                sales_expert=request.user
            ).order_by('name')[:20]
    else:
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
        
        # دریافت همه قیمت‌های معتبر (deadline >= now)
        # استفاده از datetime.now() به جای date.today() چون deadline یک jDateTimeField است
        now = jdatetime.datetime.now()
        valid_prices = ProductFinancialInfo.objects.filter(
            product=product,
            deadline__gte=now
        ).order_by('-created_at')
        
        # تبدیل main_unit و secondary_unit به weight_unit
        # واحدهای معتبر در OrderItem برای محصول: kg, gr, ton, bag, piece (مثل مواد اولیه؛ فروش بر حسب فرعی/اصلی)
        weight_unit_mapping = {
            'kg': 'kg',
            'کیلوگرم': 'kg',
            'kilogram': 'kg',
            'ton': 'ton',
            'تن': 'ton',
            'gr': 'gr',
            'گرم': 'gr',
            'gram': 'gr',
            'bag': 'bag',
            'کیسه': 'bag',
            'piece': 'piece',
            'عدد': 'piece',
            'تعداد': 'piece',
        }
        
        # لیست واحدهای معتبر در OrderItem (شامل gr برای سفارش با واحد فرعی)
        valid_weight_units = {'kg', 'gr', 'ton', 'bag', 'piece'}
        
        # ساخت لیست واحدهای قابل استفاده (اصلی و فرعی)
        available_units = []
        unit_display_names = {
            'kg': 'کیلوگرم',
            'gr': 'گرم',
            'ton': 'تن',
            'bag': 'کیسه',
            'piece': 'عدد',
        }
        
        # واحد اصلی - فقط اگر معتبر باشد اضافه می‌شود
        if product.main_unit:
            main_unit_lower = product.main_unit.lower().strip()
            mapped_main_unit = weight_unit_mapping.get(main_unit_lower)
            # بررسی معتبر بودن واحد: باید در valid_weight_units باشد
            if mapped_main_unit and mapped_main_unit in valid_weight_units:
                if mapped_main_unit not in [u['value'] for u in available_units]:
                    available_units.append({
                        'value': mapped_main_unit,
                        'display': unit_display_names.get(mapped_main_unit, mapped_main_unit),
                        'is_main': True
                    })
        
        # واحد فرعی - فقط اگر معتبر باشد اضافه می‌شود
        if product.secondary_unit:
            secondary_unit_lower = product.secondary_unit.lower().strip()
            mapped_secondary_unit = weight_unit_mapping.get(secondary_unit_lower)
            # بررسی معتبر بودن واحد: باید در valid_weight_units باشد
            if mapped_secondary_unit and mapped_secondary_unit in valid_weight_units:
                if mapped_secondary_unit not in [u['value'] for u in available_units]:
                    available_units.append({
                        'value': mapped_secondary_unit,
                        'display': unit_display_names.get(mapped_secondary_unit, mapped_secondary_unit),
                        'is_main': False
                    })
        
        # اگر هیچ واحدی معتبر پیدا نشد، پیش‌فرض kg
        if not available_units:
            available_units.append({
                'value': 'kg',
                'display': 'کیلوگرم',
                'is_main': True
            })
        
        # برای سازگاری با کد قدیمی، weight_unit را هم برمی‌گردانیم (واحد اصلی)
        # فقط اگر واحد اصلی معتبر باشد، در غیر این صورت از اولین واحد معتبر استفاده می‌کنیم
        main_unit = product.main_unit or 'kg'
        main_unit_lower = main_unit.lower().strip()
        mapped_weight_unit = weight_unit_mapping.get(main_unit_lower, 'kg')
        # بررسی معتبر بودن: باید در valid_weight_units باشد
        if mapped_weight_unit in valid_weight_units:
            weight_unit = mapped_weight_unit
        else:
            # اگر واحد اصلی معتبر نیست، از اولین واحد معتبر در available_units استفاده می‌کنیم
            if available_units:
                weight_unit = available_units[0]['value']
            else:
                weight_unit = 'kg'  # پیش‌فرض
        
        # ساخت لیست قیمت‌ها
        prices_list = []
        for price_info in valid_prices:
            # ساخت متن نمایشی برای هر قیمت
            price_value = Decimal(str(price_info.price))
            price_display = f"{price_value.quantize(Decimal('1')):,.0f} ریال"
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
        
        # دریافت درصد مالیات - اول از Product.tax_percentage، سپس از ProductSales.price_with_tax
        tax_percentage = '0'
        try:
            # اولویت اول: tax_percentage از مدل Product
            if product.tax_percentage is not None:
                tax_percentage = str(product.tax_percentage)
            # اولویت دوم: price_with_tax از ProductSales
            elif hasattr(product, 'sales_info') and product.sales_info and product.sales_info.price_with_tax:
                tax_percentage = str(product.sales_info.price_with_tax)
        except:
            pass
        
        # اطلاعات پاسخ
        data = {
            'main_unit': product.main_unit or '',
            'secondary_unit': product.secondary_unit or '',
            'weight_unit': weight_unit,  # برای سازگاری با کد قدیمی
            'available_units': available_units,  # لیست واحدهای قابل استفاده
            'prices': prices_list,
            'prices_count': len(prices_list),
            'has_price': len(prices_list) > 0,
            'tax_percentage': tax_percentage,
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
    ویو نمایش جزئیات سفارش (popup)
    - کنترل دسترسی TaskPermission: SALES_VIEW_ORDER_DETAIL
    - نمایش اطلاعات سفارش و اقلام آن در popup
    - پشتیبانی از AJAX
    """
    audit_logger.info(f"درخواست مشاهده جزئیات سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_ORDER_DETAIL.value):
        audit_logger.activity("تلاش برای مشاهده جزئیات سفارش بدون دسترسی")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'شما دسترسی به این بخش ندارید.'}, status=403)
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
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'سفارش مورد نظر یافت نشد.'}, status=404)
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
    
    # بررسی دسترسی ویرایش (هم دسترسی کاربر و هم وضعیت سفارش)
    has_permission = user_has_task(request.user, TaskChoices.SALES_EDIT_ORDER.value)
    can_edit = has_permission and can_edit_order(order)
    
    context = {
        'order': order,
        'order_items': order_items,
        'total_purchase_cost': total_purchase_cost,
        'total_weight': total_weight,
        'total_weight_ton': total_weight_ton,
        'can_edit': can_edit,
        'page_title': f'جزئیات سفارش {order_number}',
    }
    return render(request, 'order/order_detail_popup.html', context)


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
    
    # بررسی اینکه آیا سفارش قابل ویرایش است یا نه
    if not can_edit_order(order):
        audit_logger.activity(f"تلاش برای ویرایش سفارش {order_number} که در وضعیت {order.status} است و قابل ویرایش نیست")
        messages.error(request, 'این سفارش در وضعیت فعلی قابل ویرایش نیست.')
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
                    # دریافت نسخه قبلی سفارش برای مقایسه (قبل از هر تغییری)
                    # استفاده از refresh_from_db برای اطمینان از دریافت آخرین نسخه
                    order.refresh_from_db()
                    old_order = Order.objects.select_related('customer').get(pk=order.pk)
                    
                    # ذخیره سفارش
                    order = order_form.save(commit=False)
                    order.save()
                    
                    # ثبت تغییرات فیلدها
                    from core.OrderFolder.OrderModel import OrderChangeLog
                    
                    # فیلدهای قابل ردیابی
                    trackable_fields = {
                        'customer': 'مشتری',
                        'order_type': 'نوع سفارش',
                        'registration_source': 'منبع ثبت',
                        'status': 'وضعیت',
                        'freight_payment_type': 'نوع پرداخت کرایه',
                    }
                    
                    # بررسی تغییرات فیلدها
                    for field_name, field_label in trackable_fields.items():
                        old_val = getattr(old_order, field_name, None)
                        new_val = getattr(order, field_name, None)
                        
                        # تبدیل مقادیر به رشته برای مقایسه
                        # برای ForeignKey، از id استفاده می‌کنیم
                        if field_name == 'customer':
                            old_val_id = old_val.pk if old_val else None
                            new_val_id = new_val.pk if new_val else None
                            if old_val_id != new_val_id:
                                old_val_str = old_val.name if old_val and hasattr(old_val, 'name') else (str(old_val) if old_val else '—')
                                new_val_str = new_val.name if new_val and hasattr(new_val, 'name') else (str(new_val) if new_val else '—')
                            else:
                                continue
                        else:
                            # برای سایر فیلدها، مقایسه مستقیم
                            old_val_str = str(old_val) if old_val is not None else ''
                            new_val_str = str(new_val) if new_val is not None else ''
                            
                            # اگر مقدار تغییر نکرده، ادامه بده
                            if old_val_str == new_val_str:
                                continue
                            
                            # برای فیلدهای choice، نمایش فارسی را بگیر
                            if hasattr(order, f'get_{field_name}_display'):
                                if old_val:
                                    try:
                                        old_order_temp = Order()
                                        old_order_temp.status = old_val if field_name == 'status' else None
                                        old_order_temp.order_type = old_val if field_name == 'order_type' else None
                                        old_order_temp.registration_source = old_val if field_name == 'registration_source' else None
                                        old_order_temp.freight_payment_type = old_val if field_name == 'freight_payment_type' else None
                                        old_val_str = getattr(old_order_temp, f'get_{field_name}_display')() if old_val else '—'
                                    except:
                                        old_val_str = str(old_val) if old_val else '—'
                                else:
                                    old_val_str = '—'
                                    
                                if new_val:
                                    new_val_str = getattr(order, f'get_{field_name}_display')()
                                else:
                                    new_val_str = '—'
                            
                            # اگر مقدار تغییر نکرده (بعد از تبدیل به نمایش فارسی)، ادامه بده
                            if old_val_str == new_val_str:
                                continue
                        
                        # ثبت تغییر
                        try:
                            OrderChangeLog.objects.create(
                                order=order,
                                field_name=field_name,
                                field_label=field_label,
                                old_value=old_val_str,
                                new_value=new_val_str,
                                changed_by=request.user,
                                note=f'ویرایش سفارش توسط {request.user.username}'
                            )
                            bug_logger.debug(f"تغییر فیلد {field_name} ثبت شد: {old_val_str} -> {new_val_str}")
                        except Exception as e:
                            bug_logger.error(f"خطا در ثبت تغییر فیلد {field_name}: {e}", exc_info=True)

                    # دریافت اقلام قبلی برای مقایسه
                    from core.OrderFolder.OrderItemModel import OrderItem
                    old_items = {item.id: item for item in OrderItem.objects.filter(order=order).select_related('product')}
                    
                    # حذف اقلامی که برای حذف علامت خورده‌اند
                    existing_item_ids = set()
                    deleted_items = []
                    for form in item_formset:
                        if not getattr(form, 'cleaned_data', None):
                            continue
                        if form.cleaned_data.get('DELETE', False):
                            # اگر فرم برای حذف علامت خورده، قلم را حذف کن
                            item_id = form.cleaned_data.get('id')
                            if item_id:
                                try:
                                    item = OrderItem.objects.get(id=item_id, order=order)
                                    deleted_items.append(item)
                                    item.delete()
                                except OrderItem.DoesNotExist:
                                    pass
                            continue
                        
                        item_id = form.cleaned_data.get('id')
                        if item_id:
                            existing_item_ids.add(item_id)
                    
                    # ثبت حذف اقلام در تاریخچه
                    for deleted_item in deleted_items:
                        try:
                            OrderChangeLog.objects.create(
                                order=order,
                                field_name='order_item',
                                field_label='قلم سفارش',
                                old_value=f"محصول: {deleted_item.product.name if deleted_item.product else '—'}, مقدار: {deleted_item.quantity}, فی: {deleted_item.unit_price}",
                                new_value='حذف شده',
                                changed_by=request.user,
                                note=f'حذف قلم سفارش توسط {request.user.username}'
                            )
                        except Exception as e:
                            bug_logger.error(f"خطا در ثبت حذف قلم: {e}", exc_info=True)
                    
                    # حذف اقلامی که در فرم نیستند (فقط اگر existing_item_ids خالی نباشد)
                    if existing_item_ids:
                        items_to_delete = OrderItem.objects.filter(order=order).exclude(id__in=existing_item_ids)
                        for item in items_to_delete:
                            try:
                                OrderChangeLog.objects.create(
                                    order=order,
                                    field_name='order_item',
                                    field_label='قلم سفارش',
                                    old_value=f"محصول: {item.product.name if item.product else '—'}, مقدار: {item.quantity}, فی: {item.unit_price}",
                                    new_value='حذف شده',
                                    changed_by=request.user,
                                    note=f'حذف قلم سفارش توسط {request.user.username}'
                                )
                            except Exception as e:
                                bug_logger.error(f"خطا در ثبت حذف قلم: {e}", exc_info=True)
                        items_to_delete.delete()
                    
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
                        discount = form.cleaned_data.get('discount') or Decimal('0')
                        additional_charges = form.cleaned_data.get('additional_charges') or Decimal('0')
                        
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
                        # اطمینان از اینکه item_id معتبر است (نه None و نه رشته خالی)
                        if item_id and str(item_id).strip():
                            try:
                                item = OrderItem.objects.get(id=item_id, order=order)
                                old_item = old_items.get(item_id)
                                
                                # ثبت تغییرات قلم
                                changes_detected = False
                                change_parts = []
                                
                                # بررسی تغییر محصول
                                if old_item and old_item.product_id != product.id:
                                    changes_detected = True
                                    change_parts.append(f"محصول: {old_item.product.name if old_item.product else '—'} → {product.name}")
                                
                                # بررسی تغییر مقدار/وزن
                                if old_item:
                                    old_qty = old_item.quantity
                                    # دریافت نمایش فارسی واحد وزن قبلی
                                    old_unit_display_map = {
                                        'kg': 'کیلوگرم',
                                        'ton': 'تن',
                                        'bag': 'کیسه',
                                        'piece': 'عدد',
                                    }
                                    old_unit = old_unit_display_map.get(old_item.weight_unit, str(old_item.weight_unit))
                                    
                                    # دریافت نمایش فارسی واحد وزن جدید
                                    new_unit_display_map = {
                                        'kg': 'کیلوگرم',
                                        'ton': 'تن',
                                        'bag': 'کیسه',
                                        'piece': 'عدد',
                                    }
                                    new_unit_display = new_unit_display_map.get(weight_unit, str(weight_unit))
                                    
                                    if old_qty != quantity or old_item.weight_unit != weight_unit:
                                        changes_detected = True
                                        change_parts.append(f"مقدار/وزن: {old_qty} {old_unit} → {quantity} {new_unit_display}")
                                
                                # بررسی تغییر فی (قیمت واحد)
                                if old_item and old_item.unit_price != unit_price:
                                    changes_detected = True
                                    change_parts.append(f"فی: {old_item.unit_price:,.0f} → {unit_price:,.0f} ریال")
                                
                                # بررسی تغییر تخفیف
                                if old_item and old_item.discount != discount:
                                    changes_detected = True
                                    change_parts.append(f"تخفیف: {old_item.discount:,.0f} → {discount:,.0f} ریال")
                                
                                # بررسی تغییر اضافات
                                if old_item and old_item.additional_charges != additional_charges:
                                    changes_detected = True
                                    change_parts.append(f"اضافات: {old_item.additional_charges:,.0f} → {additional_charges:,.0f} ریال")
                                
                                # اگر تغییری رخ داده، ثبت کن
                                if changes_detected and change_parts:
                                    try:
                                        OrderChangeLog.objects.create(
                                            order=order,
                                            field_name='order_item',
                                            field_label=f'قلم سفارش (محصول: {product.name})',
                                            old_value=' | '.join([part.split(' → ')[0] for part in change_parts]),
                                            new_value=' | '.join([part.split(' → ')[1] if ' → ' in part else part for part in change_parts]),
                                            changed_by=request.user,
                                            note=f'ویرایش قلم سفارش توسط {request.user.username}'
                                        )
                                        bug_logger.debug(f"تغییرات قلم {item_id} ثبت شد: {change_parts}")
                                    except Exception as e:
                                        bug_logger.error(f"خطا در ثبت تغییرات قلم {item_id}: {e}", exc_info=True)
                                
                                # به‌روزرسانی قلم موجود
                                item.product = product
                                item.weight_unit = weight_unit
                                item.bag_weight = form.cleaned_data.get('bag_weight')
                                item.requested_unit = form.cleaned_data.get('requested_unit') or weight_unit
                                item.quantity = quantity
                                item.unit_price = unit_price
                                item.discount = discount
                                item.additional_charges = additional_charges
                                item.vat_percent = form.cleaned_data.get('vat_percent') or Decimal('0')
                                item.save()
                                items_saved += 1
                            except OrderItem.DoesNotExist:
                                # اگر قلم پیدا نشد، یک قلم جدید ایجاد کن
                                item = form.to_instance(order)
                                item.save()
                                # ثبت اضافه شدن قلم جدید
                                try:
                                    OrderChangeLog.objects.create(
                                        order=order,
                                        field_name='order_item',
                                        field_label='قلم سفارش',
                                        old_value='—',
                                        new_value=f"محصول: {product.name}, مقدار: {quantity}, فی: {unit_price:,.0f} ریال",
                                        changed_by=request.user,
                                        note=f'افزودن قلم جدید به سفارش توسط {request.user.username}'
                                    )
                                except Exception as e:
                                    bug_logger.error(f"خطا در ثبت قلم جدید: {e}", exc_info=True)
                                items_saved += 1
                        else:
                            # ایجاد قلم جدید
                            item = form.to_instance(order)
                            item.save()
                            # ثبت اضافه شدن قلم جدید
                            try:
                                OrderChangeLog.objects.create(
                                    order=order,
                                    field_name='order_item',
                                    field_label='قلم سفارش',
                                    old_value='—',
                                    new_value=f"محصول: {product.name}, مقدار: {quantity}, فی: {unit_price:,.0f} ریال",
                                    changed_by=request.user,
                                    note=f'افزودن قلم جدید به سفارش توسط {request.user.username}'
                                )
                            except Exception as e:
                                bug_logger.error(f"خطا در ثبت قلم جدید: {e}", exc_info=True)
                            items_saved += 1
                    
                    # برای سفارش‌های فروش: تغییر وضعیت به pending_proforma_issue و نامعتبر کردن پیش فاکتور قبلی
                    if order.order_type == 'sale':
                        old_status_before_change = order.status
                        order.status = 'pending_proforma_issue'
                        order.save()
                        
                        # ثبت تغییر وضعیت در تاریخچه (اگر تغییر کرده باشد)
                        if old_status_before_change != 'pending_proforma_issue':
                            try:
                                OrderChangeLog.objects.create(
                                    order=order,
                                    field_name='status',
                                    field_label='وضعیت',
                                    old_value=old_order.get_status_display() if hasattr(old_order, 'get_status_display') else str(old_status_before_change),
                                    new_value=order.get_status_display(),
                                    changed_by=request.user,
                                    note=f'تغییر وضعیت به دلیل ویرایش سفارش توسط {request.user.username}'
                                )
                                bug_logger.debug(f"تغییر وضعیت ثبت شد: {old_status_before_change} -> pending_proforma_issue")
                            except Exception as e:
                                bug_logger.error(f"خطا در ثبت تغییر وضعیت: {e}", exc_info=True)
                        
                        # نامعتبر کردن پیش فاکتورهای قبلی این سفارش
                        from core.OrderFolder.ProformaModel import Proforma
                        previous_proformas = Proforma.objects.filter(
                            order=order,
                            is_invalidated=False
                        )
                        if previous_proformas.exists():
                            previous_proformas.update(is_invalidated=True)
                            bug_logger.info(f"پیش فاکتورهای قبلی سفارش {order_number} نامعتبر شدند")

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
                
                return redirect('sales:order_list')
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


@login_required
def order_change_history_view(request, order_number):
    """
    نمایش تاریخچه تغییرات سفارش
    """
    audit_logger.info(f"درخواست مشاهده تاریخچه تغییرات سفارش {order_number}")
    
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_ORDER_DETAIL.value):
        audit_logger.activity("تلاش برای مشاهده تاریخچه تغییرات سفارش بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده تاریخچه تغییرات ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت سفارش
    try:
        if request.user.is_superuser:
            order = Order.objects.get(order_number=order_number)
        else:
            order = Order.objects.get(
                order_number=order_number,
                registered_by=request.user
            )
    except Order.DoesNotExist:
        messages.error(request, 'سفارش مورد نظر یافت نشد.')
        return redirect('sales:order_list')
    
    # دریافت تاریخچه تغییرات
    from core.OrderFolder.OrderModel import OrderChangeLog
    change_logs = OrderChangeLog.objects.filter(order=order).select_related('changed_by').order_by('-changed_at')
    
    context = {
        'order': order,
        'change_logs': change_logs,
        'page_title': f'تاریخچه تغییرات سفارش {order_number}',
    }
    
    # اگر درخواست AJAX است، فقط محتوای تاریخچه را برگردان
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'order/order_change_history_popup.html', context)
    
    return render(request, 'order/order_change_history.html', context)


