from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.db import transaction
from django.db.models import Q, Sum
from django.template.loader import render_to_string
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")
from sales.forms.invoice_create_form import (
    CreateInvoiceForm,
    get_accessible_invoice_fields,
)
from core.OrderFolder.InvoiceModel import Invoice
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.AllocationFolder.AllocationModel import Allocation
from core.TransportFolder.TransportModel import Transport
from django.contrib.contenttypes.models import ContentType
from core.helpers import check_field_access_prefer_edit
from sales.tables.tables_invoice import InvoiceTable
from decimal import Decimal
import json
import jdatetime


def get_company_info():
    """
    دریافت اطلاعات شرکت از مدل CompanyInfo
    """
    from core.CompanyFolder.CompanyInfoModel import CompanyInfo
    return CompanyInfo.get_company_info()


def get_person_complete_info(person):
    """
    دریافت اطلاعات کامل یک شخص (تامین‌کننده)
    شامل: نام، شماره اقتصادی، شماره ملی، شماره ثبت شرکت، آدرس، کدپستی، شماره تلفن
    """
    if not person:
        return None
    
    # اطلاعات مالی بانکی
    financial_info = FinancialBanking.objects.filter(person=person).first()
    
    # آدرس تحویل
    delivery_addresses = DeliveryAddress.objects.filter(person=person)
    primary_delivery_address = delivery_addresses.first() if delivery_addresses.exists() else None
    
    # شماره تلفن
    person_content_type = ContentType.objects.get_for_model(person)
    phone_numbers = PhoneNumber.objects.filter(
        content_type=person_content_type,
        object_id=person.national_id
    ).order_by('-is_primary', 'phone_type')
    primary_phone = phone_numbers.first() if phone_numbers.exists() else None
    
    # جمع‌آوری اطلاعات
    info = {
        'name': person.name or '-',
        'national_id': person.national_id or '-',
        'registration_number': person.registration_number or '-',
        'economic_code': financial_info.economic_code if financial_info else '-',
        'address': financial_info.tax_address if financial_info and financial_info.tax_address else (
            primary_delivery_address.address if primary_delivery_address else '-'
        ),
        'postal_code': financial_info.tax_postal_code if financial_info and financial_info.tax_postal_code else (
            primary_delivery_address.postal_code if primary_delivery_address else '-'
        ),
        'phone_number': primary_phone.number if primary_phone else '-',
        'phone_type': primary_phone.get_phone_type_display() if primary_phone else '-',
        'tax_province': financial_info.tax_province if financial_info else '-',
        'tax_city': financial_info.tax_city if financial_info else '-',
        'tax_group': financial_info.get_tax_group_display() if financial_info and financial_info.tax_group else '-',
    }
    
    return info


def get_company_complete_info():
    """
    دریافت اطلاعات کامل شرکت از مدل CompanyInfo
    """
    from core.CompanyFolder.CompanyInfoModel import CompanyInfo
    company_info = CompanyInfo.get_company_info()
    
    return {
        'name': company_info.name or '-',
        'national_id': company_info.national_id or '-',
        'registration_number': company_info.registration_number or '-',
        'economic_code': company_info.economic_code or '-',
        'address': company_info.tax_address or company_info.address or '-',
        'postal_code': company_info.tax_postal_code or company_info.postal_code or '-',
        'phone_number': company_info.phone_number or '-',
        'phone_type': 'تلفن',
        'tax_province': company_info.tax_province or '-',
        'tax_city': company_info.tax_city or '-',
        'tax_group': '-',
    }


def get_accessible_invoice_fields_for_view(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش فاکتور در لیست
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که باید در لیست نمایش داده شوند
    display_fields = {
        'tax_invoice_number': 'tax_invoice_number',
        'order': 'order',
        'customer': 'customer',
        'issue_date': 'issue_date',
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}

    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            Invoice,
            model_field_name,
        )

    return accessible_fields


@login_required
def invoice_list_view(request):
    """
    لیست فاکتورها با استفاده از django-tables2
    """
    audit_logger.info("درخواست مشاهده لیست فاکتورها")
    
    # بررسی TaskPermission - باید یک Task مناسب برای فاکتور تعریف شود
    # برای اکنون، از همان Task پیش فاکتور استفاده می‌کنیم
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_INVOICE.value):
        audit_logger.activity("تلاش برای مشاهده لیست فاکتورها بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست فاکتورها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت پارامتر جستجو
    search_query = request.GET.get('search', '').strip()

    # نمایش همه فاکتورها
    if request.user.is_superuser:
        invoices = Invoice.objects.all().select_related('order', 'customer', 'company').order_by('-created_at')
    else:
        invoices = Invoice.objects.filter(
            order__registered_by=request.user
        ).select_related('order', 'customer', 'company').order_by('-created_at')

    # اعمال جستجو (شماره فاکتور، شماره سفارش، نام مشتری)
    if search_query:
        invoices = invoices.filter(
            Q(tax_invoice_number__icontains=search_query) |
            Q(order__order_number__icontains=search_query) |
            Q(customer__name__icontains=search_query)
        )

    # دریافت فیلدهای قابل دسترسی برای نمایش
    accessible_fields = get_accessible_invoice_fields_for_view(request.user)

    bug_logger.debug(f"تعداد {invoices.count()} فاکتور برای نمایش لود شد")

    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    table = InvoiceTable(invoices, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)

    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'search_query': search_query,
        'page_title': 'لیست فاکتورها',
    }
    return render(request, 'invoice/invoice_list.html', context)


@login_required
def invoice_create_view(request):
    """
    ایجاد فاکتور جدید برای یک سفارش خرید
    """
    audit_logger.info("درخواست ایجاد فاکتور جدید")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_INVOICE.value):
        audit_logger.activity("تلاش برای ایجاد فاکتور بدون دسترسی")
        messages.error(request, 'شما دسترسی به ایجاد فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if request.method == 'POST':
        temp_form = CreateInvoiceForm()
        access_map = get_accessible_invoice_fields(request.user, temp_form)
        form = CreateInvoiceForm(request.POST, request.FILES, user=request.user, accessible_fields=access_map)

        if form.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save(commit=False)
                    # company از طریق Person تنظیم می‌شود (برای سازگاری با کد قدیمی)
                    # اما اطلاعات شرکت از CompanyInfo گرفته می‌شود
                    invoice.save()

                bug_logger.info(f"فاکتور {invoice.tax_invoice_number or invoice.id} با موفقیت ایجاد شد")
                messages.success(request, 'فاکتور با موفقیت ایجاد شد.')
                return redirect('sales:invoice_list')
            except Exception as e:
                bug_logger.error(f"خطا در ایجاد فاکتور: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ایجاد فاکتور: {str(e)}')
        else:
            bug_logger.warning("فرم ایجاد فاکتور معتبر نیست")
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_form = CreateInvoiceForm()
        access_map = get_accessible_invoice_fields(request.user, temp_form)
        form = CreateInvoiceForm(user=request.user, accessible_fields=access_map)
        # company_display از CompanyInfo گرفته می‌شود
        company_info = get_company_info()
        if company_info:
            form.company_display = company_info

    context = {
        'form': form,
        'accessible_fields': access_map if 'access_map' in locals() else get_accessible_invoice_fields(request.user, form),
        'page_title': 'ایجاد فاکتور جدید',
    }
    return render(request, 'invoice/invoice_create.html', context)


@login_required
def invoice_detail_view(request, invoice_id):
    """
    نمایش جزئیات فاکتور و امکان ویرایش و تکمیل اطلاعات
    """
    audit_logger.info(f"درخواست مشاهده جزئیات فاکتور {invoice_id}")
    
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_INVOICE.value):
        audit_logger.activity(f"تلاش برای مشاهده جزئیات فاکتور {invoice_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده جزئیات فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    invoice = get_object_or_404(Invoice, pk=invoice_id)

    # بررسی دسترسی - کاربر باید بتواند فاکتورهای مرتبط با سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if invoice.order and invoice.order.registered_by != request.user:
            audit_logger.activity(f"تلاش برای دسترسی به فاکتور {invoice_id} متعلق به کاربر دیگر")
            messages.error(request, 'شما دسترسی به این فاکتور ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if request.method == 'POST':
        temp_form = CreateInvoiceForm(instance=invoice)
        access_map = get_accessible_invoice_fields(request.user, temp_form)
        form = CreateInvoiceForm(request.POST, request.FILES, instance=invoice, user=request.user, accessible_fields=access_map)

        if form.is_valid():
            try:
                with transaction.atomic():
                    invoice = form.save()
                bug_logger.info(f"فاکتور {invoice_id} با موفقیت به‌روزرسانی شد")
                messages.success(request, 'فاکتور با موفقیت به‌روزرسانی شد.')
                return redirect('sales:invoice_detail', invoice_id=invoice_id)
            except Exception as e:
                bug_logger.error(f"خطا در به‌روزرسانی فاکتور {invoice_id}: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در به‌روزرسانی فاکتور: {str(e)}')
        else:
            bug_logger.warning(f"فرم ویرایش فاکتور {invoice_id} معتبر نیست")
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_form = CreateInvoiceForm(instance=invoice)
        access_map = get_accessible_invoice_fields(request.user, temp_form)
        form = CreateInvoiceForm(instance=invoice, user=request.user, accessible_fields=access_map)
        # تنظیم company_display برای نمایش در تمپلیت
        if invoice.company:
            # company_display از CompanyInfo گرفته می‌شود
            company_info = get_company_info()
            if company_info:
                form.company_display = company_info
        else:
            company_info = get_company_info()
            if company_info:
                form.company_display = company_info

    # دریافت اطلاعات سفارش
    order = invoice.order
    order_items = []
    if order:
        order_items = OrderItem.objects.filter(order=order).select_related('product')

    # بررسی اینکه آیا همه اطلاعات پر شده است
    is_complete = (
        invoice.order is not None and
        invoice.tax_invoice_number is not None and
        invoice.tax_invoice_number.strip() != '' and
        invoice.customer_tax_type is not None and
        invoice.issue_date is not None and
        invoice.customer is not None and
        invoice.company is not None
    )

    # دریافت اطلاعات کامل تامین‌کننده و شرکت
    customer_info = get_person_complete_info(invoice.customer) if invoice.customer else None
    company_info = get_company_complete_info()
    
    # بررسی وضعیت تسویه
    settlement_completed = invoice.is_settlement_completed()
    
    # دریافت شماره اقتصادی
    economic_code = invoice.get_customer_economic_code()

    context = {
        'invoice': invoice,
        'form': form,
        'accessible_fields': access_map if 'access_map' in locals() else get_accessible_invoice_fields(request.user, form),
        'order': order,
        'order_items': order_items,
        'is_complete': is_complete,
        'customer_info': customer_info,
        'company_info': company_info,
        'settlement_completed': settlement_completed,
        'economic_code': economic_code,
        'page_title': f'جزئیات فاکتور {invoice.tax_invoice_number or invoice.id}',
    }
    return render(request, 'invoice/invoice_detail.html', context)


@login_required
def order_search_api(request):
    """
    API endpoint برای جستجوی سفارش‌های فروش که پرداختشان انجام شده
    (برای صدور فاکتور)
    """
    query = request.GET.get('q', '').strip()
    
    bug_logger.debug(f"=== جستجوی سفارش برای فاکتور ===")
    bug_logger.debug(f"Query: '{query}'")
    bug_logger.debug(f"کاربر: {request.user.username}")
    bug_logger.debug(f"Superuser: {request.user.is_superuser}")
    
    if not query:
        bug_logger.debug("query خالی است، 20 سفارش اخیر برگردانده می‌شود")
        # ادامه کد برای بازگشت سفارش‌ها (فیلتر icontains روی رشته خالی همه را برمی‌گرداند)
    
    # فیلتر کردن سفارش‌ها - فقط سفارش‌های فروش که پرداخت انجام شده
    # سفارش‌هایی که وضعیت از pending_accounting_approval به بعد دارند
    allowed_statuses = [
        'pending_accounting_approval',
        'pending_allocation',
        'pending_allocation_approval',
        'pending_factory',
        'pending_unloading_approval',
        'pending_settlement',
        'pending_settlement_approval',
        'archived',
    ]
    
    if request.user.is_superuser:
        orders = Order.objects.filter(
            order_type='sale',
            order_number__icontains=query,
            status__in=allowed_statuses
        ).select_related('customer').order_by('-created_at')[:20]
        
        bug_logger.debug(f"کاربر superuser - جستجو در سفارش‌های فروش")
    else:
        orders = Order.objects.filter(
            order_type='sale',
            order_number__icontains=query,
            status__in=allowed_statuses,
            registered_by=request.user
        ).select_related('customer').order_by('-created_at')[:20]
        
        bug_logger.debug(f"کاربر عادی - جستجو در سفارش‌های فروش ثبت شده توسط کاربر")
    
    bug_logger.debug(f"تعداد سفارش‌های پیدا شده: {orders.count()}")
    
    results = []
    for order in orders:
        order_data = {
            'id': order.order_number,
            'text': f"{order.order_number} - {order.customer.name if order.customer else 'بدون مشتری'}",
            'customer_id': order.customer.national_id if order.customer else None,
            'customer_name': order.customer.name if order.customer else None,
        }
        results.append(order_data)
        bug_logger.debug(f"سفارش اضافه شد: {order.order_number} - type: {order.order_type} - وضعیت: {order.status}")
    
    bug_logger.debug(f"نتایج برگردانده شده: {len(results)} سفارش")
    bug_logger.debug(f"=== پایان جستجو ===")
    
    return JsonResponse({'results': results})


@login_required
def get_order_customer_api(request, order_number):
    """
    API endpoint برای دریافت اطلاعات مشتری یک سفارش خرید
    استفاده می‌شود برای انتخاب خودکار مشتری در فرم فاکتور
    """
    if not order_number:
        audit_logger.alert("درخواست API اطلاعات مشتری سفارش بدون order_number")
        return JsonResponse({'error': 'شماره سفارش الزامی است'}, status=400)
    
    bug_logger.debug(f"درخواست API اطلاعات مشتری سفارش {order_number}")
    
    try:
        order = Order.objects.select_related('customer').get(order_number=order_number, order_type='sale')
        
        # بررسی دسترسی
        if not request.user.is_superuser:
            if order.registered_by != request.user:
                audit_logger.activity(f"تلاش برای دسترسی به اطلاعات مشتری سفارش {order_number} متعلق به کاربر دیگر")
                return JsonResponse({'error': 'شما دسترسی به این سفارش ندارید'}, status=403)
        
        # بازگشت اطلاعات مشتری
        data = {
            'customer_id': order.customer.national_id if order.customer else None,
            'customer_name': order.customer.name if order.customer else None,
        }
        
        return JsonResponse(data)
    except Order.DoesNotExist:
        bug_logger.warning(f"سفارش {order_number} یافت نشد")
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در دریافت اطلاعات مشتری سفارش {order_number}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def invoice_download_pdf(request, invoice_id):
    """
    دانلود فاکتور به صورت PDF
    """
    audit_logger.info(f"درخواست دانلود PDF فاکتور {invoice_id}")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_INVOICE.value):
        audit_logger.activity(f"تلاش برای دانلود PDF فاکتور {invoice_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به دانلود PDF فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        messages.error(request, "خطا: پکیج WeasyPrint به درستی نصب نشده است. لطفاً با مدیر سیستم تماس بگیرید.")
        return redirect('sales:invoice_detail', invoice_id=invoice_id)
    
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    
    # بررسی دسترسی - کاربر باید بتواند فاکتورهای مرتبط با سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if invoice.order and invoice.order.registered_by != request.user:
            audit_logger.activity(f"تلاش برای دانلود PDF فاکتور {invoice_id} متعلق به کاربر دیگر")
            messages.error(request, 'شما دسترسی به این فاکتور ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        bug_logger.debug(f"تولید PDF برای فاکتور {invoice.tax_invoice_number or invoice_id}")
        # دریافت اطلاعات سفارش و اقلام
        order = invoice.order
        order_items = []
        total_amount = Decimal('0')
        order_weight = Decimal('0')
        delivered_weight = Decimal('0')
        
        if order:
            order_items = OrderItem.objects.filter(order=order).select_related('product')
            
            # محاسبه وزن سفارش
            for item in order_items:
                weight_kg = item.get_weight_in_kg()
                order_weight += Decimal(str(weight_kg))
                
                # محاسبه مجموع کل
                if item.total_purchase_cost:
                    total_amount += Decimal(str(item.total_purchase_cost))
                elif item.quantity and item.unit_price:
                    subtotal = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                    total_amount += subtotal
            
            # محاسبه وزن تحویلی از Transport
            allocations = Allocation.objects.filter(order=order)
            transports = Transport.objects.filter(allocation__in=allocations)
            
            for transport in transports:
                if transport.net_weight:
                    delivered_weight += Decimal(str(transport.net_weight))
        
        # اگر وزن تحویلی وجود نداشت، از وزن سفارش استفاده کن
        if delivered_weight == 0:
            delivered_weight = order_weight
        
        # محاسبه اختلاف وزن
        weight_difference = delivered_weight - order_weight
        
        # دریافت اطلاعات کامل مشتری و شرکت
        customer_info = get_person_complete_info(invoice.customer) if invoice.customer else None
        company_info = get_company_complete_info()
        
        # رندر HTML
        from django.template.loader import render_to_string
        html_string = render_to_string('invoice/invoice_pdf_template.html', {
            'invoice': invoice,
            'order': order,
            'order_items': order_items,
            'customer_info': customer_info,
            'company_info': company_info,
            'total_amount': total_amount,
            'order_weight': order_weight,
            'delivered_weight': delivered_weight,
            'weight_difference': weight_difference,
        })
        
        # تبدیل به PDF
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        
        # کانفیگ فونت برای فارسی
        font_config = FontConfiguration()
        
        # CSS برای فونت وزیر و تنظیمات landscape
        css = CSS(string='''
            @page {
                size: A4 landscape;
                margin: 15mm;
            }
            @font-face {
                font-family: 'Vazir';
                src: url('https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-Regular.ttf') format('truetype');
                font-weight: normal;
                font-style: normal;
            }
            @font-face {
                font-family: 'Vazir';
                src: url('https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-Bold.ttf') format('truetype');
                font-weight: bold;
                font-style: normal;
            }
            body {
                font-family: 'Vazir', sans-serif;
                direction: rtl;
                text-align: right;
            }
        ''', font_config=font_config)
        
        # تولید PDF
        pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        # ارسال به عنوان پاسخ
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"invoice_{invoice.tax_invoice_number or invoice.id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        bug_logger.info(f"PDF فاکتور {invoice.tax_invoice_number or invoice_id} با موفقیت تولید شد")
        return response
    except Exception as e:
        bug_logger.error(f"خطا در تولید PDF فاکتور {invoice_id}: {str(e)}", exc_info=True)
        messages.error(request, f"خطا در تولید PDF: {str(e)}")
        return redirect('sales:invoice_detail', invoice_id=invoice_id)

