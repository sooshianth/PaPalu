from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.db import transaction
from django.db.models import Q, Sum
from django.template.loader import render_to_string
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")
from sales.forms.create_proforma_form import (
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
from access.helpers import check_field_access_prefer_edit
import json
import jdatetime


def get_or_create_company():
    """
    دریافت یا ایجاد شرکت تامین نهاده سیمرغ
    """
    company_name = 'تامین نهاده سیمرغ'
    
    # جستجو برای پیدا کردن شرکت
    company = Person.objects.filter(name=company_name).first()
    
    if not company:
        # اگر شرکت پیدا نشد، ایجاد می‌کنیم
        # استفاده از یک national_id موقت
        # در واقع باید این را از settings دریافت کنیم
        try:
            company = Person.objects.create(
                national_id='0000000000',  # باید یک کد ملی معتبر باشد
                name=company_name,
                type='supplier',
                nature='legal'
            )
        except Exception as e:
            # اگر national_id تکراری بود، سعی می‌کنیم پیدا کنیم
            company = Person.objects.filter(name__icontains='تامین نهاده').first()
    
    return company


def get_person_complete_info(person):
    """
    دریافت اطلاعات کامل یک شخص (مشتری یا شرکت)
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
    لیست پیش فاکتورها
    """
    audit_logger.info("درخواست مشاهده لیست پیش فاکتورها")
    
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
        audit_logger.activity("تلاش برای مشاهده لیست پیش فاکتورها بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست پیش فاکتورها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # نمایش همه پیش فاکتورها
    if request.user.is_superuser:
        proformas = Proforma.objects.all().select_related('order', 'customer', 'company').order_by('-created_at')
    else:
        proformas = Proforma.objects.filter(
            order__registered_by=request.user
        ).select_related('order', 'customer', 'company').order_by('-created_at')

    # دریافت فیلدهای قابل دسترسی برای نمایش
    accessible_fields = get_accessible_proforma_fields_for_view(request.user)

    bug_logger.debug(f"تعداد {proformas.count()} پیش فاکتور برای نمایش لود شد")

    context = {
        'proformas': proformas,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست پیش فاکتورها',
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
                    # اگر company هنوز تنظیم نشده، تنظیم می‌کنیم
                    if not proforma.company:
                        proforma.company = get_or_create_company()
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
        # تنظیم company به صورت خودکار - company_display توسط فرم تنظیم می‌شود
        company = get_or_create_company()
        if company:
            form.initial['company'] = company
            form.company_display = company

    context = {
        'form': form,
        'accessible_fields': access_map if 'access_map' in locals() else get_accessible_proforma_fields(request.user, form),
        'page_title': 'ایجاد پیش فاکتور جدید',
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
        # تنظیم company_display برای نمایش در تمپلیت
        if proforma.company:
            form.company_display = proforma.company
        else:
            company = get_or_create_company()
            if company:
                form.company_display = company

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
    company_info = get_person_complete_info(proforma.company) if proforma.company else None

    context = {
        'proforma': proforma,
        'form': form,
        'accessible_fields': access_map if 'access_map' in locals() else get_accessible_proforma_fields(request.user, form),
        'order': order,
        'order_items': order_items,
        'is_complete': is_complete and items_complete,
        'customer_info': customer_info,
        'company_info': company_info,
        'page_title': f'جزئیات پیش فاکتور {proforma.proforma_number or proforma.id}',
    }
    return render(request, 'proforma/proforma_detail.html', context)


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
        if order:
            order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # دریافت اطلاعات کامل مشتری و شرکت
        customer_info = get_person_complete_info(proforma.customer) if proforma.customer else None
        company_info = get_person_complete_info(proforma.company) if proforma.company else None
        
        # رندر HTML
        from django.template.loader import render_to_string
        html_string = render_to_string('proforma/proforma_pdf_template.html', {
            'proforma': proforma,
            'order': order,
            'order_items': order_items,
            'customer_info': customer_info,
            'company_info': company_info,
        })
        
        # تبدیل به PDF
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        
        # کانفیگ فونت برای فارسی
        font_config = FontConfiguration()
        
        # CSS برای فونت وزیر
        css = CSS(string='''
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

