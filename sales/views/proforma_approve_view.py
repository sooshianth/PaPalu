from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig
from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.OrderDocumentModel import OrderDocument
from sales.tables.tables_proforma import ApproveProformaTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@login_required
def approve_proforma_list_view(request):
    """
    لیست سفارش‌های با وضعیت "در انتظار تأیید پیش فاکتور توسط مشتری"
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار آپلود پیش فاکتور مشتری")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):
        audit_logger.activity("تلاش برای دسترسی به لیست تأیید پیش فاکتورها بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست تأیید پیش فاکتورها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های با وضعیت "در انتظار آپلود پیش فاکتور مشتری"
    orders = Order.objects.filter(
        status='pending_customer_proforma_upload'
    ).select_related('registered_by', 'customer').prefetch_related(
        'proformas__customer', 'order_documents',
        'order_items__product', 'order_items__raw_material'
    ).order_by('-created_at')

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

    bug_logger.debug(f"تعداد {len(orders_with_proformas)} سفارش برای نمایش لود شد")
    
    # ایجاد جدول با django-tables2
    table = ApproveProformaTable(orders_with_proformas)
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'page_title': 'لیست سفارش‌های در انتظار آپلود پیش فاکتور مشتری',
    }
    return render(request, 'proforma/approve_proforma_list.html', context)


@login_required
def approve_proforma_upload_view(request, order_number):
    """
    آپلود فایل تأیید پیش فاکتور برای یک سفارش
    """
    audit_logger.info(f"درخواست آپلود فایل تأیید پیش فاکتور برای سفارش {order_number}")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):
        audit_logger.activity(f"تلاش برای آپلود فایل تأیید پیش فاکتور سفارش {order_number} بدون دسترسی")
        messages.error(request, 'شما دسترسی به آپلود فایل تأیید پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش همراه با اقلام
    order = get_object_or_404(
        Order.objects.prefetch_related(
            'order_items__product', 'order_items__raw_material'
        ),
        order_number=order_number
    )

    # بررسی دسترسی - کاربر باید بتواند سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if order.registered_by != request.user:
            audit_logger.activity(f"تلاش برای دسترسی به سفارش {order_number} متعلق به کاربر دیگر")
            messages.error(request, 'شما دسترسی به این سفارش ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # بررسی وضعیت سفارش
    if order.status != 'pending_customer_proforma_upload':
        bug_logger.warning(f"سفارش {order_number} در وضعیت {order.status} است، در حالی که انتظار pending_customer_proforma_upload می‌رود")
        messages.error(request, 'این سفارش در وضعیت مناسب برای آپلود فایل تأیید پیش فاکتور نیست.')
        return redirect('sales:approve_proforma_list')

    if request.method == 'POST':
        try:
            # بررسی اینکه آیا فایل ارسال شده است
            if 'confirmation_file' not in request.FILES:
                bug_logger.warning(f"درخواست POST برای آپلود فایل تأیید پیش فاکتور سفارش {order_number} بدون فایل")
                messages.error(request, 'لطفاً فایل تأیید پیش فاکتور را انتخاب کنید.')
                return redirect('sales:approve_proforma_upload', order_number=order_number)

            confirmation_file = request.FILES['confirmation_file']
            bug_logger.debug(f"فایل تأیید پیش فاکتور با نام {confirmation_file.name} و حجم {confirmation_file.size} دریافت شد")

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

            bug_logger.info(f"فایل تأیید پیش فاکتور سفارش {order_number} با موفقیت آپلود شد")
            messages.success(
                request,
                'فایل تأیید پیش فاکتور با موفقیت آپلود شد و وضعیت سفارش به "در انتظار بارگذاری رسید تراکنش" تغییر یافت.'
            )
            return redirect('sales:approve_proforma_list')

        except Exception as e:
            bug_logger.error(f"خطا در آپلود فایل تأیید پیش فاکتور سفارش {order_number}: {str(e)}", exc_info=True)
            messages.error(request, f'خطا در آپلود فایل: {str(e)}')
            return redirect('sales:approve_proforma_upload', order_number=order_number)

    # دریافت پیش فاکتور مرتبط
    proforma = order.proformas.first() if order.proformas.exists() else None
    order_document = order.order_documents.first() if order.order_documents.exists() else None

    bug_logger.debug(f"نمایش صفحه آپلود فایل تأیید پیش فاکتور برای سفارش {order_number}")

    context = {
        'order': order,
        'proforma': proforma,
        'order_document': order_document,
        'page_title': f'آپلود فایل تأیید پیش فاکتور - سفارش {order.order_number}',
    }
    return render(request, 'proforma/approve_proforma_upload.html', context)

