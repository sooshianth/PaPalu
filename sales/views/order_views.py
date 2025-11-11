from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from core.RBACModel import user_has_task, TaskChoices
from sales.forms.create_order_form import (
    CreateOrderForm,
    build_order_item_formset,
    get_accessible_order_fields,
)
from core.OrderFolder.OrderModel import Order


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
                # If user has permission to issue proforma, consider redirecting
                if user_has_task(request.user, TaskChoices.SALES_ISSUE_PROFORMA.value):
                    return redirect('sales:proforma_issue_start')  # Assumes URL name exists
                return redirect('sales:order_list')  # Fallback list URL
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


