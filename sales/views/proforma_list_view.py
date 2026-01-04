from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.db import transaction
from django.db.models import Q
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")
from sales.forms.proforma_create_form import (
    CreateProformaForm,
    get_accessible_proforma_fields,
)
from core.OrderFolder.ProformaModel import Proforma
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from django.contrib.contenttypes.models import ContentType
from core.helpers import check_field_access_prefer_edit
from sales.tables.tables_proforma import ProformaTable
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
    دریافت اطلاعات کامل یک شخص (مشتری)
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
    }


def get_accessible_proforma_fields_for_view(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش پیش فاکتور در لیست
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که باید در لیست نمایش داده شوند
    display_fields = {
        'proforma_number': 'proforma_number',
        'order': 'order',
        'customer': 'customer',
        'validity_date': 'validity_date',
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}

    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            Proforma,
            model_field_name,
        )

    return accessible_fields


@login_required
def proforma_list_view(request):
    """
    لیست سفارش‌های در انتظار صدور پیش فاکتور با استفاده از django-tables2
    و لیست پیش فاکتورهای صادر شده
    """
    audit_logger.info("درخواست مشاهده لیست سفارش‌های در انتظار صدور پیش فاکتور")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_PROFORMA.value):
        audit_logger.activity("تلاش برای مشاهده لیست سفارش‌های در انتظار صدور پیش فاکتور بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست سفارش‌های در انتظار صدور پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # دریافت سفارش‌های در وضعیت "در انتظار صدور پیش فاکتور"
    orders_qs = Order.objects.filter(
        status='pending_proforma_issue',
        order_type='sale'
    ).select_related('customer').order_by('-created_at')
    
    # فیلتر بر اساس کاربر (اگر superuser نیست)
    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    bug_logger.debug(f"تعداد {orders_qs.count()} سفارش در انتظار صدور پیش فاکتور لود شد")

    # ایجاد جدول سفارش‌ها
    from sales.tables.tables_proforma import PendingProformaOrderTable
    table = PendingProformaOrderTable(orders_qs, user=request.user)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)

    # دریافت پیش فاکتورهای صادر شده (پیش فاکتورهایی که order دارند و order.status دیگر 'pending_proforma_issue' نیست)
    # یا پیش فاکتورهای نامعتبر شده (که باید نمایش داده شوند ولی با علامت منسوخ)
    proformas_qs = Proforma.objects.filter(
        order__isnull=False,
        order__order_type='sale'
    ).filter(
        # یا order.status دیگر 'pending_proforma_issue' نیست (پیش فاکتورهای معتبر)
        # یا is_invalidated=True (پیش فاکتورهای نامعتبر که باید نمایش داده شوند)
        ~Q(order__status='pending_proforma_issue') | Q(is_invalidated=True)
    ).select_related('order', 'customer', 'order__customer').order_by('-created_at')
    
    # فیلتر بر اساس کاربر (اگر superuser نیست)
    if not request.user.is_superuser:
        proformas_qs = proformas_qs.filter(order__registered_by=request.user)

    bug_logger.debug(f"تعداد {proformas_qs.count()} پیش فاکتور صادر شده لود شد")

    # ایجاد جدول پیش فاکتورهای صادر شده
    from sales.tables.tables_proforma import ProformaTable
    accessible_fields = get_accessible_proforma_fields_for_view(request.user)
    proformas_table = ProformaTable(proformas_qs, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(proformas_table)

    context = {
        'table': table,
        'proformas_table': proformas_table,
        'page_title': 'سفارش‌های در انتظار صدور پیش فاکتور',
    }
    return render(request, 'proforma/proforma_list.html', context)


@login_required
def proforma_create_view(request):
    """
    ایجاد پیش فاکتور جدید برای یک سفارش
    """
    audit_logger.info("درخواست ایجاد پیش فاکتور جدید")
    
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_PROFORMA.value):
        audit_logger.activity("تلاش برای ایجاد پیش فاکتور بدون دسترسی")
        messages.error(request, 'شما دسترسی به ایجاد پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if request.method == 'POST':
        temp_form = CreateProformaForm()
        access_map = get_accessible_proforma_fields(request.user, temp_form)
        form = CreateProformaForm(request.POST, user=request.user, accessible_fields=access_map)

        if form.is_valid():
            try:
                with transaction.atomic():
                    proforma = form.save(commit=False)
                    # company از طریق Person تنظیم می‌شود (برای سازگاری با کد قدیمی)
                    # اما اطلاعات شرکت از CompanyInfo گرفته می‌شود
                    proforma.save()

                    # تغییر وضعیت سفارش به "در انتظار آپلود پیش فاکتور مشتری"
                    if proforma.order:
                        proforma.order.status = 'pending_customer_proforma_upload'
                        proforma.order.save()

                bug_logger.info(f"پیش فاکتور {proforma.proforma_number or proforma.id} با موفقیت ایجاد شد")
                messages.success(request, 'پیش فاکتور با موفقیت ایجاد شد.')
                return redirect('sales:proforma_list')
            except Exception as e:
                bug_logger.error(f"خطا در ایجاد پیش فاکتور: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ایجاد پیش فاکتور: {str(e)}')
        else:
            bug_logger.warning("فرم ایجاد پیش فاکتور معتبر نیست")
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_form = CreateProformaForm()
        access_map = get_accessible_proforma_fields(request.user, temp_form)
        form = CreateProformaForm(user=request.user, accessible_fields=access_map)
        # company_display از CompanyInfo گرفته می‌شود
        company_info = get_company_info()
        if company_info:
            form.company_display = company_info
        
        # اگر order_number در query string باشد، آن را تنظیم کن
        order_number = request.GET.get('order_number', '').strip()
        if order_number:
            try:
                order = Order.objects.get(order_number=order_number, order_type='sale')
                # بررسی دسترسی
                if not request.user.is_superuser:
                    if order.registered_by != request.user:
                        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
                        return redirect('sales:proforma_list')
                
                # تنظیم مقدار اولیه برای فیلد order
                form.initial['order'] = f"{order.order_number} - {order.customer.name if order.customer else 'بدون مشتری'}"
                form.initial['order_id'] = order.order_number
                
                # تنظیم مقدار اولیه برای فیلد customer
                if order.customer:
                    form.initial['customer'] = f"{order.customer.name} ({order.customer.national_id})"
                    form.initial['customer_id'] = order.customer.national_id
                
                # تولید خودکار شماره پیش فاکتور
                if not form.initial.get('proforma_number'):
                    form.initial['proforma_number'] = form._generate_proforma_number(order_number)
            except Order.DoesNotExist:
                messages.error(request, 'سفارش یافت نشد.')
            except Exception as e:
                bug_logger.error(f"خطا در تنظیم سفارش از query string: {str(e)}", exc_info=True)

    # استخراج اطلاعات مشتری و فیلدهای ناقص از فرم (اگر خطا وجود داشته باشد)
    customer_id_for_edit = None
    missing_fields_list = []
    if hasattr(form, '_customer_id'):
        customer_id_for_edit = form._customer_id
        missing_fields_list = getattr(form, '_missing_fields', [])
    
    context = {
        'form': form,
        'accessible_fields': access_map if 'access_map' in locals() else get_accessible_proforma_fields(request.user, form),
        'page_title': 'ایجاد پیش فاکتور جدید',
        'preselected_order_number': request.GET.get('order_number', '').strip(),
        'customer_id_for_edit': customer_id_for_edit,
        'missing_fields': missing_fields_list,
    }
    return render(request, 'proforma/proforma_create.html', context)


@login_required
def proforma_detail_view(request, proforma_id):
    """
    نمایش جزئیات پیش فاکتور و امکان ویرایش و تکمیل اطلاعات
    """
    audit_logger.info(f"درخواست مشاهده جزئیات پیش فاکتور {proforma_id}")
    
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
        audit_logger.activity(f"تلاش برای مشاهده جزئیات پیش فاکتور {proforma_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده جزئیات پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    proforma = get_object_or_404(Proforma, pk=proforma_id)

    # بررسی دسترسی - کاربر باید بتواند پیش فاکتورهای مرتبط با سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if proforma.order and proforma.order.registered_by != request.user:
            audit_logger.activity(f"تلاش برای دسترسی به پیش فاکتور {proforma_id} متعلق به کاربر دیگر")
            messages.error(request, 'شما دسترسی به این پیش فاکتور ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # بررسی اینکه آیا پیش فاکتور تکمیل شده است (سفارش به مرحله بعد رفته)
    is_done = False
    if proforma.order and proforma.order.status != 'pending_proforma_issue':
        is_done = True
    
    # اگر پیش فاکتور تکمیل شده است، اجازه ویرایش نده
    if request.method == 'POST' and is_done:
        audit_logger.activity(f"تلاش برای ویرایش پیش فاکتور {proforma_id} که تکمیل شده است")
        messages.error(request, 'پیش فاکتور تکمیل شده و قابل ویرایش نیست.')
        return redirect('sales:proforma_detail', proforma_id=proforma_id)

    if request.method == 'POST':
        temp_form = CreateProformaForm(instance=proforma)
        access_map = get_accessible_proforma_fields(request.user, temp_form)
        form = CreateProformaForm(request.POST, instance=proforma, user=request.user, accessible_fields=access_map)

        if form.is_valid():
            try:
                with transaction.atomic():
                    proforma = form.save()
                bug_logger.info(f"پیش فاکتور {proforma_id} با موفقیت به‌روزرسانی شد")
                messages.success(request, 'پیش فاکتور با موفقیت به‌روزرسانی شد.')
                return redirect('sales:proforma_detail', proforma_id=proforma_id)
            except Exception as e:
                bug_logger.error(f"خطا در به‌روزرسانی پیش فاکتور {proforma_id}: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در به‌روزرسانی پیش فاکتور: {str(e)}')
        else:
            bug_logger.warning(f"فرم ویرایش پیش فاکتور {proforma_id} معتبر نیست")
            messages.error(request, 'اطلاعات وارد شده معتبر نیست. لطفاً خطاهای فرم را بررسی کنید.')
    else:
        temp_form = CreateProformaForm(instance=proforma)
        access_map = get_accessible_proforma_fields(request.user, temp_form)
        form = CreateProformaForm(instance=proforma, user=request.user, accessible_fields=access_map)
        # تنظیم company_display برای نمایش در تمپلیت (از CompanyInfo)
        company_info = get_company_info()
        if company_info:
            form.company_display = company_info
        
        # تنظیم مقادیر اولیه برای فیلدهای order و customer از instance
        if proforma.order:
            form.initial['order'] = f"{proforma.order.order_number} - {proforma.order.customer.name if proforma.order.customer else 'بدون مشتری'}"
            form.initial['order_id'] = proforma.order.order_number
        
        if proforma.customer:
            form.initial['customer'] = f"{proforma.customer.name} ({proforma.customer.national_id})"
            form.initial['customer_id'] = proforma.customer.national_id

    # دریافت اطلاعات سفارش
    order = proforma.order
    order_items = []
    if order:
        order_items = OrderItem.objects.filter(order=order).select_related('product')

    # بررسی اینکه آیا همه اطلاعات پر شده است
    is_complete = (
        proforma.order is not None and
        proforma.proforma_number is not None and
        proforma.proforma_number.strip() != '' and
        proforma.validity_date is not None and
        proforma.customer is not None and
        proforma.company is not None
    )

    # بررسی اینکه آیا همه اقلام سفارش دارای قیمت و توضیحات هستند
    items_complete = True
    if order_items:
        for item in order_items:
            if item.unit_price is None or item.unit_price == 0:
                items_complete = False
                break

    # دریافت اطلاعات کامل مشتری و شرکت
    customer_info = get_person_complete_info(proforma.customer) if proforma.customer else None
    company_info = get_company_complete_info()

    context = {
        'proforma': proforma,
        'form': form,
        'accessible_fields': access_map if 'access_map' in locals() else get_accessible_proforma_fields(request.user, form),
        'order': order,
        'order_items': order_items,
        'is_complete': is_complete and items_complete,
        'is_done': is_done,
        'customer_info': customer_info,
        'company_info': company_info,
        'page_title': f'جزئیات پیش فاکتور {proforma.proforma_number or proforma.id}',
    }
    return render(request, 'proforma/proforma_detail.html', context)


@login_required
def order_search_api(request):
    """
    API endpoint برای جستجوی سفارش‌ها
    جستجو بر اساس شماره سفارش و نام مشتری
    """
    query = request.GET.get('q', '').strip()
    
    # ساخت query base برای سفارش‌های فروش
    base_filter = Q(order_type='sale')
    if not request.user.is_superuser:
        base_filter &= Q(registered_by=request.user)

    if not query:
        # اگر کوئری خالی است، 20 سفارش اخیر را برگردان
        all_orders = Order.objects.filter(base_filter).select_related('customer').order_by('-created_at')[:20]
    else:
        # جستجو بر اساس شماره سفارش
        orders_by_number = Order.objects.filter(
            base_filter & Q(order_number__icontains=query)
        ).select_related('customer')
        
        # جستجو بر اساس نام مشتری - اگر مشتری‌ای پیدا شد، همه سفارش‌هایش را برگردان
        orders_by_customer = Order.objects.none()
        matching_customers = Person.objects.filter(
            name__icontains=query
        ).distinct()
        
        if matching_customers.exists():
            # برای هر مشتری که نامش با query مطابقت دارد، همه سفارش‌هایش را بگیر
            customer_filter = base_filter & Q(customer__in=matching_customers)
            orders_by_customer = Order.objects.filter(
                customer_filter
            ).select_related('customer')
        
        # ترکیب نتایج و حذف تکراری‌ها
        all_orders = (orders_by_number | orders_by_customer).distinct().order_by('-created_at')[:20]
    
    results = []
    seen_order_numbers = set()
    for order in all_orders:
        # جلوگیری از تکرار
        if order.order_number in seen_order_numbers:
            continue
        seen_order_numbers.add(order.order_number)
        
        results.append({
            'id': order.order_number,
            'text': f"{order.order_number} - {order.customer.name if order.customer else 'بدون مشتری'}",
            'customer_id': order.customer.national_id if order.customer else None,
            'customer_name': order.customer.name if order.customer else None,
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def get_company_notes_api(request, note_type='proforma'):
    """
    API endpoint برای دریافت ملاحظات شرکت (پیش فاکتور یا فاکتور)
    """
    audit_logger.info(f"درخواست دریافت ملاحظات {note_type}")
    
    try:
        from core.CompanyFolder.CompanyInfoModel import CompanyInfo
        company_info = CompanyInfo.get_company_info()
        
        if note_type == 'proforma':
            notes = company_info.proforma_notes or ''
        elif note_type == 'invoice':
            notes = company_info.invoice_notes or ''
        else:
            notes = ''
        
        return JsonResponse({
            'notes': notes,
            'note_type': note_type
        })
    except Exception as e:
        bug_logger.error(f"خطا در دریافت ملاحظات شرکت: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_order_customer_api(request, order_number):
    """
    API endpoint برای دریافت اطلاعات مشتری یک سفارش
    استفاده می‌شود برای انتخاب خودکار مشتری در فرم پیش‌فاکتور
    """
    if not order_number:
        audit_logger.alert("درخواست API اطلاعات مشتری سفارش بدون order_number")
        return JsonResponse({'error': 'شماره سفارش الزامی است'}, status=400)
    
    bug_logger.debug(f"درخواست API اطلاعات مشتری سفارش {order_number}")
    
    try:
        order = Order.objects.select_related('customer').get(order_number=order_number)
        
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
def get_customer_info_for_edit_api(request, customer_id):
    """
    API endpoint برای دریافت اطلاعات مشتری و فیلدهای ناقص
    """
    if not customer_id:
        return JsonResponse({'error': 'شناسه مشتری الزامی است'}, status=400)
    
    try:
        customer = Person.objects.get(national_id=customer_id, type='customer')
        
        # دریافت اطلاعات مالی بانکی
        financial_info = FinancialBanking.objects.filter(person=customer).first()
        
        # دریافت آدرس تحویل
        delivery_addresses = DeliveryAddress.objects.filter(person=customer)
        primary_delivery_address = delivery_addresses.first() if delivery_addresses.exists() else None
        
        # دریافت شماره تلفن
        person_content_type = ContentType.objects.get_for_model(customer)
        phone_numbers = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=customer.national_id
        ).order_by('-is_primary', 'phone_type')
        primary_phone = phone_numbers.first() if phone_numbers.exists() else None
        
        # ساخت پاسخ
        data = {
            'customer_id': customer.national_id,
            'name': customer.name or '',
            'national_id': customer.national_id or '',
            'registration_number': customer.registration_number or '',
            'nature': customer.nature or '',
            'economic_code': financial_info.economic_code if financial_info else '',
            'tax_address': financial_info.tax_address if financial_info else '',
            'tax_postal_code': financial_info.tax_postal_code if financial_info else '',
            'tax_province': financial_info.tax_province if financial_info else '',
            'tax_city': financial_info.tax_city if financial_info else '',
            'delivery_address': primary_delivery_address.address if primary_delivery_address else '',
            'delivery_postal_code': primary_delivery_address.postal_code if primary_delivery_address else '',
            'delivery_province': primary_delivery_address.province if primary_delivery_address else '',
            'delivery_city': primary_delivery_address.city if primary_delivery_address else '',
            'phone_number': primary_phone.number if primary_phone else '',
            'phone_type': primary_phone.phone_type if primary_phone else 'mobile',
            'has_financial_info': financial_info is not None,
            'has_delivery_address': primary_delivery_address is not None,
            'has_phone': primary_phone is not None,
        }
        
        return JsonResponse(data)
    except Person.DoesNotExist:
        return JsonResponse({'error': 'مشتری یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در دریافت اطلاعات مشتری {customer_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def update_customer_info_api(request, customer_id):
    """
    API endpoint برای ویرایش اطلاعات مشتری
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'فقط POST مجاز است'}, status=405)
    
    if not customer_id:
        return JsonResponse({'error': 'شناسه مشتری الزامی است'}, status=400)
    
    try:
        customer = Person.objects.get(national_id=customer_id, type='customer')
        
        with transaction.atomic():
            # به‌روزرسانی اطلاعات پایه مشتری
            if 'name' in request.POST:
                customer.name = request.POST.get('name', '').strip()
            if 'registration_number' in request.POST:
                customer.registration_number = request.POST.get('registration_number', '').strip()
            customer.save()
            
            # به‌روزرسانی یا ایجاد اطلاعات مالی بانکی
            financial_info, created = FinancialBanking.objects.get_or_create(person=customer)
            if 'economic_code' in request.POST:
                financial_info.economic_code = request.POST.get('economic_code', '').strip()
            if 'tax_address' in request.POST:
                financial_info.tax_address = request.POST.get('tax_address', '').strip()
            if 'tax_postal_code' in request.POST:
                financial_info.tax_postal_code = request.POST.get('tax_postal_code', '').strip()
            if 'tax_province' in request.POST:
                financial_info.tax_province = request.POST.get('tax_province', '').strip()
            if 'tax_city' in request.POST:
                financial_info.tax_city = request.POST.get('tax_city', '').strip()
            financial_info.save()
            
            # به‌روزرسانی یا ایجاد آدرس تحویل (از همان اطلاعات مالیاتی استفاده می‌کنیم)
            # استفاده از آدرس مالیاتی برای ایجاد/به‌روزرسانی آدرس تحویل
            tax_postal_code = financial_info.tax_postal_code or ''
            tax_address = financial_info.tax_address or ''
            tax_province = financial_info.tax_province or ''
            tax_city = financial_info.tax_city or ''
            
            if tax_postal_code and tax_address:
                # اگر آدرس تحویل با این کدپستی وجود دارد، به‌روزرسانی کن
                delivery_addr = DeliveryAddress.objects.filter(person=customer, postal_code=tax_postal_code).first()
                if delivery_addr:
                    delivery_addr.address = tax_address
                    delivery_addr.recipient_name = customer.name or 'تحویل گیرنده'
                    if tax_province:
                        delivery_addr.province = tax_province
                    if tax_city:
                        delivery_addr.city = tax_city
                    delivery_addr.save()
                else:
                    # ایجاد آدرس تحویل جدید از اطلاعات مالیاتی
                    DeliveryAddress.objects.create(
                        person=customer,
                        postal_code=tax_postal_code,
                        address=tax_address,
                        recipient_name=customer.name or 'تحویل گیرنده',
                        province=tax_province,
                        city=tax_city,
                    )
            
            # به‌روزرسانی یا ایجاد شماره تلفن
            phone_number = request.POST.get('phone_number', '').strip()
            phone_type = request.POST.get('phone_type', 'mobile').strip()
            if phone_number:
                person_content_type = ContentType.objects.get_for_model(customer)
                # حذف شماره‌های قبلی (یا می‌توانیم فقط به‌روزرسانی کنیم)
                PhoneNumber.objects.filter(
                    content_type=person_content_type,
                    object_id=customer.national_id,
                    is_primary=True
                ).delete()
                # ایجاد شماره جدید
                PhoneNumber.objects.create(
                    content_type=person_content_type,
                    object_id=customer.national_id,
                    number=phone_number,
                    phone_type=phone_type,
                    is_primary=True
                )
        
        bug_logger.info(f"اطلاعات مشتری {customer_id} با موفقیت به‌روزرسانی شد")
        return JsonResponse({'success': True, 'message': 'اطلاعات مشتری با موفقیت به‌روزرسانی شد'})
    except Person.DoesNotExist:
        return JsonResponse({'error': 'مشتری یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در به‌روزرسانی اطلاعات مشتری {customer_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def proforma_download_pdf(request, proforma_id):
    """
    دانلود پیش فاکتور به صورت PDF
    """
    audit_logger.info(f"درخواست دانلود PDF پیش فاکتور {proforma_id}")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
        audit_logger.activity(f"تلاش برای دانلود PDF پیش فاکتور {proforma_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به دانلود PDF پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        messages.error(request, "خطا: پکیج WeasyPrint به درستی نصب نشده است. لطفاً با مدیر سیستم تماس بگیرید.")
        return redirect('sales:proforma_detail', proforma_id=proforma_id)
    
    proforma = get_object_or_404(Proforma, pk=proforma_id)
    
    # بررسی دسترسی - کاربر باید بتواند پیش فاکتورهای مرتبط با سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if proforma.order and proforma.order.registered_by != request.user:
            audit_logger.activity(f"تلاش برای دانلود PDF پیش فاکتور {proforma_id} متعلق به کاربر دیگر")
            messages.error(request, 'شما دسترسی به این پیش فاکتور ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        bug_logger.debug(f"تولید PDF برای پیش فاکتور {proforma.proforma_number or proforma_id}")
        # دریافت اطلاعات سفارش و اقلام
        order = proforma.order
        order_items = []
        total_amount = 0
        if order:
            order_items = OrderItem.objects.filter(order=order).select_related('product')
            # محاسبه مجموع کل
            for item in order_items:
                if item.total_purchase_cost:
                    total_amount += float(item.total_purchase_cost)
                elif item.quantity and item.unit_price:
                    subtotal = float(item.quantity) * float(item.unit_price)
                    total_amount += subtotal
        
        # دریافت اطلاعات کامل مشتری و شرکت
        customer_info = get_person_complete_info(proforma.customer) if proforma.customer else None
        company_info = get_company_complete_info()
        
        # رندر HTML
        from django.template.loader import render_to_string
        html_string = render_to_string('proforma/proforma_pdf_template.html', {
            'proforma': proforma,
            'order': order,
            'order_items': order_items,
            'customer_info': customer_info,
            'company_info': company_info,
            'total_amount': total_amount,
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
        filename = f"proforma_{proforma.proforma_number or proforma.id}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        bug_logger.info(f"PDF پیش فاکتور {proforma.proforma_number or proforma_id} با موفقیت تولید شد")
        return response
    except Exception as e:
        bug_logger.error(f"خطا در تولید PDF پیش فاکتور {proforma_id}: {str(e)}", exc_info=True)
        messages.error(request, f"خطا در تولید PDF: {str(e)}")
        return redirect('sales:proforma_detail', proforma_id=proforma_id)


@login_required
@require_http_methods(["GET"])
def get_next_proforma_number_api(request):
    """
    API endpoint برای دریافت شماره پیش فاکتور بعدی (افزایشی)
    """
    try:
        # یافتن آخرین شماره پیش فاکتور
        last_proforma = Proforma.objects.filter(
            proforma_number__isnull=False,
            proforma_number__startswith='PF'
        ).exclude(
            proforma_number=''
        ).order_by('-proforma_number').first()
        
        if last_proforma and last_proforma.proforma_number:
            try:
                # استخراج عدد از آخرین شماره (PF را حذف می‌کنیم)
                last_number_str = last_proforma.proforma_number.replace('PF', '').strip()
                last_number = int(last_number_str)
                # افزایش شماره
                next_number = last_number + 1
            except (ValueError, AttributeError):
                # اگر شماره قبلی معتبر نبود، از 1 شروع می‌کنیم
                next_number = 1
        else:
            # اگر پیش فاکتوری وجود نداشت، از 1 شروع می‌کنیم
            next_number = 1
        
        # فرمت نهایی: PF + 6 رقم (با صفرهای پیش‌رو)
        proforma_number = f"PF{next_number:06d}"
        
        return JsonResponse({
            'success': True,
            'proforma_number': proforma_number
        })
    except Exception as e:
        bug_logger.error(f"خطا در تولید شماره پیش فاکتور: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'خطا در تولید شماره پیش فاکتور'
        }, status=500)

