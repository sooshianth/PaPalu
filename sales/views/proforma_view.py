from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.db import transaction
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from core.RBACModel import user_has_task, TaskChoices
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
from core.RBACModel import user_has_field_access, get_accessible_fields
from django.contrib.contenttypes.models import ContentType
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
    
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}
    
    # استفاده از ContentType برای بررسی دسترسی
    content_type = ContentType.objects.get_for_model(Proforma)
    accessible_fields = {}
    
    for display_name, model_field_name in display_fields.items():
        # بررسی آیا قانونی برای این فیلد وجود دارد
        rule = FieldAccessRule.objects.filter(
            user=user,
            content_type=content_type,
            field_name=model_field_name,
            access_type='view'
        ).first()
        
        if rule is None:
            # اگر هیچ قانونی تعریف نشده، دسترسی داده می‌شود
            accessible_fields[display_name] = True
        else:
            # اگر قانون وجود دارد، مقدار allowed را بررسی می‌کنیم
            accessible_fields[display_name] = rule.allowed
    
    return accessible_fields


@login_required
def proforma_list_view(request):
    """
    لیست پیش فاکتورها
    """
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
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

    context = {
        'proformas': proformas,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست پیش فاکتورها',
    }
    return render(request, 'sales/proforma_list.html', context)


@login_required
def proforma_create_view(request):
    """
    ایجاد پیش فاکتور جدید برای یک سفارش
    """
    if not user_has_task(request.user, TaskChoices.SALES_ISSUE_PROFORMA.value):
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

                messages.success(request, 'پیش فاکتور با موفقیت ایجاد شد.')
                return redirect('sales:proforma_list')
            except Exception as e:
                messages.error(request, f'خطا در ایجاد پیش فاکتور: {str(e)}')
        else:
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
    return render(request, 'sales/proforma_create.html', context)


@login_required
def proforma_detail_view(request, proforma_id):
    """
    نمایش جزئیات پیش فاکتور و امکان ویرایش و تکمیل اطلاعات
    """
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
        messages.error(request, 'شما دسترسی به مشاهده جزئیات پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    proforma = get_object_or_404(Proforma, pk=proforma_id)

    # بررسی دسترسی - کاربر باید بتواند پیش فاکتورهای مرتبط با سفارش‌های خود را ببیند
    if not request.user.is_superuser:
        if proforma.order and proforma.order.registered_by != request.user:
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
                messages.success(request, 'پیش فاکتور با موفقیت به‌روزرسانی شد.')
                return redirect('sales:proforma_detail', proforma_id=proforma_id)
            except Exception as e:
                messages.error(request, f'خطا در به‌روزرسانی پیش فاکتور: {str(e)}')
        else:
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
    return render(request, 'sales/proforma_detail.html', context)


@login_required
def proforma_download_pdf(request, proforma_id):
    """
    دانلود پیش فاکتور به صورت PDF
    """
    # بررسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
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
            messages.error(request, 'شما دسترسی به این پیش فاکتور ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
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
        html_string = render_to_string('sales/proforma_pdf_template.html', {
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
        
        return response
    except Exception as e:
        messages.error(request, f"خطا در تولید PDF: {str(e)}")
        return redirect('sales:proforma_detail', proforma_id=proforma_id)

