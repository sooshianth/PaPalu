from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.db import transaction
from django.db.models import Q, Sum
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
from access.models.FieldAccessUserModel import FieldAccessRule
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


@login_required
def proforma_list_view(request):
    """
    لیست پیش فاکتورهای در انتظار تأیید
    - نمایش پیش فاکتورهایی که هنوز تأیید نشده‌اند
    """
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
        messages.error(request, 'شما دسترسی به مشاهده لیست پیش فاکتورها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # پیش فاکتورهای در انتظار تأیید
    # در اینجا ما پیش فاکتورهایی را که مرتبط با سفارش‌های در وضعیت pending هستند نمایش می‌دهیم
    # یا می‌توانیم یک فیلد status به Proforma اضافه کنیم
    # برای اکنون، پیش فاکتورهایی که سفارش آن‌ها هنوز در وضعیت pending است را نمایش می‌دهیم
    
    if request.user.is_superuser:
        proformas = Proforma.objects.filter(
            order__status='pending'
        ).select_related('order', 'customer', 'company').order_by('-created_at')
    else:
        proformas = Proforma.objects.filter(
            order__status='pending',
            order__registered_by=request.user
        ).select_related('order', 'customer', 'company').order_by('-created_at')

    context = {
        'proformas': proformas,
        'page_title': 'لیست پیش فاکتورهای در انتظار تأیید',
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
def proforma_approve_view(request, proforma_id):
    """
    تأیید پیش فاکتور و تغییر وضعیت سفارش به 'در انتظار تأیید پیش فاکتور توسط مشتری'
    """
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA_PRICE.value):
        messages.error(request, 'شما دسترسی به تأیید پیش فاکتور ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    proforma = get_object_or_404(Proforma, pk=proforma_id)

    # بررسی دسترسی
    if not request.user.is_superuser:
        if proforma.order and proforma.order.registered_by != request.user:
            messages.error(request, 'شما دسترسی به این پیش فاکتور ندارید.')
            return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    # بررسی اینکه آیا همه اطلاعات پر شده است
    if not (
        proforma.order and
        proforma.proforma_number and
        proforma.proforma_number.strip() != '' and
        proforma.validity_date and
        proforma.customer and
        proforma.company
    ):
        messages.error(request, 'تمام اطلاعات پیش فاکتور باید پر شده باشد.')
        return redirect('sales:proforma_detail', proforma_id=proforma_id)

    # بررسی اینکه آیا همه اقلام سفارش دارای قیمت هستند
    order_items = OrderItem.objects.filter(order=proforma.order).select_related('product')
    for item in order_items:
        if item.unit_price is None or item.unit_price == 0:
            messages.error(request, 'تمام اقلام سفارش باید دارای قیمت باشند.')
            return redirect('sales:proforma_detail', proforma_id=proforma_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # تغییر وضعیت سفارش
                if proforma.order:
                    proforma.order.status = 'pending_customer_proforma_approval'
                    proforma.order.save(update_fields=['status'])

            messages.success(request, 'پیش فاکتور با موفقیت تأیید شد و سفارش به وضعیت "در انتظار تأیید پیش فاکتور توسط مشتری" تغییر یافت.')
            return redirect('sales:proforma_list')
        except Exception as e:
            messages.error(request, f'خطا در تأیید پیش فاکتور: {str(e)}')
            return redirect('sales:proforma_detail', proforma_id=proforma_id)

    # دریافت اطلاعات کامل مشتری و شرکت
    customer_info = get_person_complete_info(proforma.customer) if proforma.customer else None
    company_info = get_person_complete_info(proforma.company) if proforma.company else None

    context = {
        'proforma': proforma,
        'order': proforma.order,
        'order_items': order_items,
        'customer_info': customer_info,
        'company_info': company_info,
        'page_title': f'تأیید پیش فاکتور {proforma.proforma_number}',
    }
    return render(request, 'sales/proforma_approve.html', context)

