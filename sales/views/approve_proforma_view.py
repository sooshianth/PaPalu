from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.OrderDocumentModel import OrderDocument


@login_required
def approve_proforma_list_view(request):
    """
    لیست سفارش‌های با وضعیت "در انتظار تأیید پیش فاکتور توسط مشتری"
    """
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):
        messages.error(request, 'شما دسترسی به مشاهده لیست تأیید پیش فاکتورها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های با وضعیت "در انتظار آپلود پیش فاکتور مشتری"
    orders = Order.objects.filter(
        status='pending_customer_proforma_upload'
    ).select_related('registered_by').prefetch_related('proformas', 'order_documents').order_by('-created_at')

    # اگر کاربر superuser نیست، فقط سفارش‌های خودش را ببیند
    if not request.user.is_superuser:
        orders = orders.filter(registered_by=request.user)

    # برای هر سفارش، پیش فاکتور مرتبط را پیدا می‌کنیم
    orders_with_proformas = []
    for order in orders:
        proforma = order.proformas.first() if order.proformas.exists() else None
        order_doc = order.order_documents.first() if order.order_documents.exists() else None
        
        orders_with_proformas.append({
            'order': order,
            'proforma': proforma,
            'order_document': order_doc,
            'has_confirmation_file': order_doc and order_doc.proforma_confirmation_attachment
        })

    context = {
        'orders_with_proformas': orders_with_proformas,
        'page_title': 'لیست سفارش‌های در انتظار آپلود پیش فاکتور مشتری',
    }
    return render(request, 'sales/approve_proforma_list.html', context)


@login_required
def approve_proforma_upload_view(request, order_number):
    """
    آپلود فایل تأیید پیش فاکتور برای یک سفارش
    """
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):
        messages.error(request, 'شما دسترسی به آپلود فایل تأیید پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش
    order = get_object_or_404(Order, order_number=order_number)

    # بررسی دسترسی - کاربر باید بتواند سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if order.registered_by != request.user:
            messages.error(request, 'شما دسترسی به این سفارش ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # بررسی وضعیت سفارش
    if order.status != 'pending_customer_proforma_upload':
        messages.error(request, 'این سفارش در وضعیت مناسب برای آپلود فایل تأیید پیش فاکتور نیست.')
        return redirect('sales:approve_proforma_list')

    if request.method == 'POST':
        try:
            # بررسی اینکه آیا فایل ارسال شده است
            if 'confirmation_file' not in request.FILES:
                messages.error(request, 'لطفاً فایل تأیید پیش فاکتور را انتخاب کنید.')
                return redirect('sales:approve_proforma_upload', order_number=order_number)

            confirmation_file = request.FILES['confirmation_file']

            with transaction.atomic():
                # دریافت یا ایجاد OrderDocument
                order_document, created = OrderDocument.objects.get_or_create(
                    order=order,
                    defaults={}
                )

                # ذخیره فایل
                order_document.proforma_confirmation_attachment = confirmation_file
                order_document.save()

                # تغییر وضعیت سفارش به "در انتظار بارگذاری رسید تراکنش"
                order.status = 'pending_transaction_receipt_upload'
                order.save()

            messages.success(
                request,
                'فایل تأیید پیش فاکتور با موفقیت آپلود شد و وضعیت سفارش به "در انتظار بارگذاری رسید تراکنش" تغییر یافت.'
            )
            return redirect('sales:approve_proforma_list')

        except Exception as e:
            messages.error(request, f'خطا در آپلود فایل: {str(e)}')
            return redirect('sales:approve_proforma_upload', order_number=order_number)

    # دریافت پیش فاکتور مرتبط
    proforma = order.proformas.first() if order.proformas.exists() else None
    order_document = order.order_documents.first() if order.order_documents.exists() else None

    context = {
        'order': order,
        'proforma': proforma,
        'order_document': order_document,
        'page_title': f'آپلود فایل تأیید پیش فاکتور - سفارش {order.order_number}',
    }
    return render(request, 'sales/approve_proforma_upload.html', context)

