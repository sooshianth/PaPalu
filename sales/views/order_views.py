from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from django.db.models import Sum
from core.RBACModel import user_has_task, TaskChoices
from sales.forms.create_order_form import (
    CreateOrderForm,
    build_order_item_formset,
    get_accessible_order_fields,
)
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from access.models.FieldAccessUserModel import FieldAccessRule
from django.contrib.contenttypes.models import ContentType


@login_required
def create_order_view(request):
    """
    ویو ایجاد سفارش
    - کنترل دسترسی TaskPermission: SALES_CREATE_ORDER
    - کنترل دسترسی‌ فیلدها با FieldAccessRule مشابه ایجاد مشتری
    - استفاده از فرم اقلام به صورت فرم‌ست
    """
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_ORDER.value):
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
                    # Defaults are set in form.save(); ensure again before save
                    if not order.status:
                        order.status = 'pending'
                    order.save()

                    total_weight = None
                    # Save items
                    for form in item_formset:
                        if not getattr(form, 'cleaned_data', None):
                            continue
                        # اگر فرم برای حذف علامت خورده باشد، آن را نادیده بگیر
                        if form.cleaned_data.get('DELETE', False):
                            continue
                        product = form.cleaned_data.get('product')
                        requested_unit = form.cleaned_data.get('requested_unit')
                        quantity = form.cleaned_data.get('quantity')
                        unit_price = form.cleaned_data.get('unit_price')
                        if not (product and requested_unit and quantity is not None and unit_price is not None):
                            continue
                        item = form.to_instance(order)
                        item.save()

                    # Optionally compute total order weight if applicable (kept None if not provided)
                    if total_weight is not None:
                        order.total_order_weight = total_weight
                        order.save(update_fields=['total_order_weight'])

                messages.success(request, 'سفارش با موفقیت ایجاد شد. تسک بعد: صدور پیش فاکتور.')
                # Redirect to order list (proforma functionality will be added later)
                return redirect('sales:order_list')
            except Exception as e:
                messages.error(request, f'خطا در ایجاد سفارش: {str(e)}')
        else:
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_order_form = CreateOrderForm()
        temp_item_form = build_order_item_formset().form()
        access_main, access_item = get_accessible_order_fields(request.user, temp_order_form, temp_item_form)
        order_form = CreateOrderForm(user=request.user, accessible_fields=access_main, initial={
            'order_type': 'sale',
            'registration_source': 'expert',
            'status': 'pending',
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
    return render(request, 'sales/create_order.html', context)


def get_accessible_order_list_fields(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش سفارش
    """
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
        'total_order_weight': (OrderModel, 'total_order_weight'),
        'total_purchase_cost': (OrderItemModel, 'total_purchase_cost'),
    }

    accessible = {}
    for display_name, (model_class, model_field_name) in mapping.items():
        content_type = ContentType.objects.get_for_model(model_class)
        rule = FieldAccessRule.objects.filter(
            user=user,
            content_type=content_type,
            field_name=model_field_name,
            access_type='view'
        ).first()
        accessible[display_name] = True if rule is None else rule.allowed
    return accessible


@login_required
def order_list_view(request):
    """
    لیست سفارش‌ها با کنترل دسترسی و نمایش فیلدهای قابل مشاهده
    """
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_ORDER_LIST.value):
        messages.error(request, 'شما دسترسی به مشاهده لیست سفارش‌ها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if request.user.is_superuser:
        orders_qs = Order.objects.all().order_by('-created_at')
    else:
        orders_qs = Order.objects.filter(registered_by=request.user).order_by('-created_at')

    # محاسبه مجموع بهای تمام شده خرید برای هر سفارش با annotate
    orders_qs = orders_qs.annotate(total_purchase_cost=Sum('order_items__total_purchase_cost'))

    accessible_fields = get_accessible_order_list_fields(request.user)

    context = {
        'orders': orders_qs,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست سفارش‌ها',
    }
    return render(request, 'sales/order_list.html', context)


