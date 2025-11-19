from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from django.db.models import Sum
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")
from sales.forms.create_order_form import (
    CreateOrderForm,
    build_order_item_formset,
    get_accessible_order_fields,
)
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from access.helpers import check_field_access_prefer_edit


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
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_order_form = CreateOrderForm()
        temp_item_form = build_order_item_formset().form()
        access_main, access_item = get_accessible_order_fields(request.user, temp_order_form, temp_item_form)
        order_form = CreateOrderForm(user=request.user, accessible_fields=access_main, initial={
            'order_type': 'sale',
            'registration_source': 'expert',
            'status': 'pending_proforma_issue',
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
            'customer': True,
            'status': True,
            'total_purchase_cost': True,
        }

    # مدل‌ها
    from core.OrderFolder.OrderModel import Order as OrderModel
    from core.OrderFolder.OrderItemModel import OrderItem as OrderItemModel

    mapping = {
        'customer': (OrderModel, 'customer'),
        'status': (OrderModel, 'status'),
        'total_purchase_cost': (OrderItemModel, 'total_purchase_cost'),
    }

    accessible = {}
    for display_name, (model_class, model_field_name) in mapping.items():
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
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌ها")
    
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_ORDER_LIST.value):
        audit_logger.activity("تلاش برای مشاهده لیست سفارش‌ها بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست سفارش‌ها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if request.user.is_superuser:
        orders_qs = Order.objects.all().select_related('customer').order_by('-created_at')
    else:
        orders_qs = Order.objects.filter(registered_by=request.user).select_related('customer').order_by('-created_at')

    # محاسبه مجموع بهای تمام شده خرید برای هر سفارش با annotate
    orders_qs = orders_qs.annotate(total_purchase_cost=Sum('order_items__total_purchase_cost'))

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش برای نمایش لود شد")

    accessible_fields = get_accessible_order_list_fields(request.user)

    context = {
        'orders': orders_qs,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست سفارش‌ها',
    }
    return render(request, 'order/order_list.html', context)


