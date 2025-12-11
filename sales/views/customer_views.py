from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from django.db.models import Q, Exists, OuterRef, Subquery, IntegerField
from django.db.models.functions import Cast
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.RBACModel import user_has_task, TaskChoices

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")
from core.helpers import check_field_access_prefer_edit
from sales.forms.customer_create_form import (
    CreateCustomerForm,
    build_delivery_address_formset,
    build_representative_formset,
    build_bank_account_formset,
    DeliveryAddressForm,
    RepresentativeForm,
    BankAccountForm,
)
from core.PersonFolder import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.BankAccountModel import BankAccount
from django.contrib.contenttypes.models import ContentType
from sales.forms.customer_create_form import clean_empty_to_none
from sales.tables import CustomerTable


@login_required
def create_customer_view(request):
    """
    ویو برای ایجاد مشتری جدید
    - بررسی دسترسی با TaskPermission
    - بررسی دسترسی فیلدها با FieldAccessRule
    """
    audit_logger.info("درخواست ایجاد مشتری جدید")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_CUSTOMER.value):
        audit_logger.activity("تلاش برای ایجاد مشتری بدون دسترسی")
        messages.error(request, 'شما دسترسی به ایجاد مشتری ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    if request.method == 'POST':
        # ابتدا map دسترسی فیلدها را به دست آوریم و سپس فرم را با آن بسازیم
        temp_form_for_access = CreateCustomerForm()
        temp_delivery_form = DeliveryAddressForm()
        temp_rep_form = RepresentativeForm()
        temp_bank_form = BankAccountForm()
        
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        accessible_delivery_fields = get_accessible_delivery_fields(request.user, temp_delivery_form)
        accessible_rep_fields = get_accessible_representative_fields(request.user, temp_rep_form)
        accessible_bank_fields = get_accessible_bank_account_fields(request.user, temp_bank_form)
        
        form = CreateCustomerForm(request.POST, request.FILES, user=request.user, accessible_fields=accessible_fields)
        delivery_formset = build_delivery_address_formset(request.POST, request.FILES, accessible_fields=accessible_delivery_fields)
        rep_formset = build_representative_formset(request.POST, request.FILES, accessible_fields=accessible_rep_fields)
        bank_formset = build_bank_account_formset(request.POST, request.FILES, accessible_fields=accessible_bank_fields)
        
        if form.is_valid() and delivery_formset.is_valid() and rep_formset.is_valid() and bank_formset.is_valid():
            try:
                with transaction.atomic():
                    # ذخیره مشتری
                    person = form.save_customer(request.user)
                    
                    # بررسی وجود حساب بانکی
                    has_bank_account = False
                    for bank_form in bank_formset:
                        if not getattr(bank_form, 'cleaned_data', None):
                            continue
                        if bank_form.cleaned_data.get('DELETE', False):
                            continue
                        account_number = bank_form.cleaned_data.get('account_number')
                        if account_number:
                            has_bank_account = True
                            break
                    
                    # ایجاد یا دریافت اطلاعات مالیاتی
                    from core.PersonFolder.FinancialBankingModel import FinancialBanking
                    financial_banking = None
                    
                    # اگر حساب بانکی وجود دارد یا فیلدهای مالیاتی پر شده‌اند، FinancialBanking ایجاد/دریافت کن
                    if has_bank_account or any([
                        form.cleaned_data.get('economic_code'),
                        form.cleaned_data.get('tax_postal_code'),
                        form.cleaned_data.get('tax_province'),
                        form.cleaned_data.get('tax_city'),
                        form.cleaned_data.get('tax_address')
                    ]):
                        # بررسی وجود FinancialBanking برای این شخص
                        financial_banking = FinancialBanking.objects.filter(person=person).first()
                        
                        if not financial_banking:
                            # ایجاد FinancialBanking جدید
                            financial_banking = FinancialBanking.objects.create(
                                person=person,
                                economic_code=clean_empty_to_none(form.cleaned_data.get('economic_code')),
                                tax_postal_code=clean_empty_to_none(form.cleaned_data.get('tax_postal_code')),
                                tax_province=clean_empty_to_none(form.cleaned_data.get('tax_province')),
                                tax_city=clean_empty_to_none(form.cleaned_data.get('tax_city')),
                                tax_address=clean_empty_to_none(form.cleaned_data.get('tax_address'))
                            )
                        else:
                            # به‌روزرسانی FinancialBanking موجود
                            financial_banking.economic_code = clean_empty_to_none(form.cleaned_data.get('economic_code'))
                            financial_banking.tax_postal_code = clean_empty_to_none(form.cleaned_data.get('tax_postal_code'))
                            financial_banking.tax_province = clean_empty_to_none(form.cleaned_data.get('tax_province'))
                            financial_banking.tax_city = clean_empty_to_none(form.cleaned_data.get('tax_city'))
                            financial_banking.tax_address = clean_empty_to_none(form.cleaned_data.get('tax_address'))
                            financial_banking.save()
                    
                    # ذخیره حساب‌های بانکی (در صورت وجود FinancialBanking)
                    if financial_banking:
                        for bank_form in bank_formset:
                            if not getattr(bank_form, 'cleaned_data', None):
                                continue
                            if bank_form.cleaned_data.get('DELETE', False):
                                continue
                            account_number = bank_form.cleaned_data.get('account_number')
                            if not account_number:
                                continue
                            
                            BankAccount.objects.create(
                                financial_banking=financial_banking,
                                account_number=account_number,
                                shaba_number=clean_empty_to_none(bank_form.cleaned_data.get('shaba_number')),
                                bank_name=clean_empty_to_none(bank_form.cleaned_data.get('bank_name'))
                            )
                    
                    # ذخیره آدرس‌های تحویل
                    for delivery_form in delivery_formset:
                        if not getattr(delivery_form, 'cleaned_data', None):
                            continue
                        if delivery_form.cleaned_data.get('DELETE', False):
                            continue
                        postal_code = delivery_form.cleaned_data.get('postal_code')
                        if not postal_code:
                            continue
                        
                        delivery_address = DeliveryAddress.objects.create(
                            person=person,
                            postal_code=postal_code,
                            recipient_name=delivery_form.cleaned_data.get('recipient_name', person.name),
                            recipient_national_id=clean_empty_to_none(delivery_form.cleaned_data.get('recipient_national_id')),
                            unique_delivery_id=clean_empty_to_none(delivery_form.cleaned_data.get('unique_delivery_id')),
                            province=delivery_form.cleaned_data.get('province', ''),
                            city=delivery_form.cleaned_data.get('city', ''),
                            address=delivery_form.cleaned_data.get('address', ''),
                            delivery_limit=clean_empty_to_none(delivery_form.cleaned_data.get('delivery_limit')),
                            recipient_type=clean_empty_to_none(delivery_form.cleaned_data.get('recipient_type'))
                        )
                        
                        # اضافه کردن شماره‌های تماس آدرس تحویل
                        delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
                        
                        if delivery_form.cleaned_data.get('delivery_mobile'):
                            PhoneNumber.objects.create(
                                content_type=delivery_content_type,
                                object_id=delivery_address.postal_code,
                                phone_type='mobile',
                                number=delivery_form.cleaned_data['delivery_mobile'],
                                is_primary=True
                            )
                        
                        if delivery_form.cleaned_data.get('delivery_landline'):
                            PhoneNumber.objects.create(
                                content_type=delivery_content_type,
                                object_id=delivery_address.postal_code,
                                phone_type='landline',
                                number=delivery_form.cleaned_data['delivery_landline'],
                                is_primary=False
                            )
                    
                    # ذخیره نمایندگان
                    for rep_form in rep_formset:
                        if not getattr(rep_form, 'cleaned_data', None):
                            continue
                        if rep_form.cleaned_data.get('DELETE', False):
                            continue
                        rep_name = rep_form.cleaned_data.get('name')
                        if not rep_name:
                            continue
                        
                        representative = Representative.objects.create(
                            person=person,
                            name=rep_name,
                            position=rep_form.cleaned_data.get('position') or '',
                            confirmation_letter=rep_form.cleaned_data.get('confirmation_letter')
                        )
                        
                        # اضافه کردن شماره‌های تماس نماینده
                        rep_content_type = ContentType.objects.get_for_model(Representative)
                        
                        if rep_form.cleaned_data.get('mobile'):
                            PhoneNumber.objects.create(
                                content_type=rep_content_type,
                                object_id=representative.id,
                                phone_type='mobile',
                                number=rep_form.cleaned_data['mobile'],
                                is_primary=True
                            )
                        
                        if rep_form.cleaned_data.get('landline'):
                            PhoneNumber.objects.create(
                                content_type=rep_content_type,
                                object_id=representative.id,
                                phone_type='landline',
                                number=rep_form.cleaned_data['landline'],
                                is_primary=False
                            )
                
                bug_logger.info(f"مشتری جدید با نام {person.name} ایجاد شد")
                messages.success(request, f'مشتری "{person.name}" با موفقیت ایجاد شد.')
                return redirect('sales:customer_list')
                
            except Exception as e:
                bug_logger.error(f"خطا در ایجاد مشتری: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ایجاد مشتری: {str(e)}')
        else:
            # فرم معتبر نیست
            bug_logger.warning("فرم ایجاد مشتری معتبر نیست")
    else:
        # در GET نیز فیلدهای غیرمجاز را از فرم حذف کن تا در UI نمایش داده نشوند
        temp_form_for_access = CreateCustomerForm()
        temp_delivery_form = DeliveryAddressForm()
        temp_rep_form = RepresentativeForm()
        temp_bank_form = BankAccountForm()
        
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        accessible_delivery_fields = get_accessible_delivery_fields(request.user, temp_delivery_form)
        accessible_rep_fields = get_accessible_representative_fields(request.user, temp_rep_form)
        accessible_bank_fields = get_accessible_bank_account_fields(request.user, temp_bank_form)
        
        form = CreateCustomerForm(user=request.user, accessible_fields=accessible_fields)
        delivery_formset = build_delivery_address_formset(accessible_fields=accessible_delivery_fields)
        rep_formset = build_representative_formset(accessible_fields=accessible_rep_fields)
        bank_formset = build_bank_account_formset(accessible_fields=accessible_bank_fields)
    
    # گرفتن فیلدهای قابل دسترسی برای کاربر
    # اگر در بالا محاسبه نشده بود (به‌ویژه در مسیر POST با خطای ولیدیشن)، محاسبه کن
    if 'accessible_fields' not in locals():
        temp_form_for_access = CreateCustomerForm()
        temp_delivery_form = DeliveryAddressForm()
        temp_rep_form = RepresentativeForm()
        temp_bank_form = BankAccountForm()
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        accessible_delivery_fields = get_accessible_delivery_fields(request.user, temp_delivery_form)
        accessible_rep_fields = get_accessible_representative_fields(request.user, temp_rep_form)
        accessible_bank_fields = get_accessible_bank_account_fields(request.user, temp_bank_form)
    
    if 'delivery_formset' not in locals():
        delivery_formset = build_delivery_address_formset(accessible_fields=accessible_delivery_fields)
    if 'rep_formset' not in locals():
        rep_formset = build_representative_formset(accessible_fields=accessible_rep_fields)
    if 'bank_formset' not in locals():
        bank_formset = build_bank_account_formset(accessible_fields=accessible_bank_fields)
    
    context = {
        'form': form,
        'delivery_formset': delivery_formset,
        'rep_formset': rep_formset,
        'bank_formset': bank_formset,
        'accessible_fields': accessible_fields,
        'accessible_delivery_fields': accessible_delivery_fields,
        'accessible_rep_fields': accessible_rep_fields,
        'accessible_bank_fields': accessible_bank_fields,
        'page_title': 'ایجاد مشتری جدید'
    }
    
    return render(request, 'customer/create_customer.html', context)


def get_accessible_form_fields(user, form):
    """
    بررسی دسترسی کاربر به فیلدهای فرم بر اساس FieldAccessRule
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    if user.is_superuser:
        # superuser به همه فیلدها دسترسی دارد
        return {field_name: True for field_name in form.fields.keys()}
    
    # نقشه‌برداری فیلدهای فرم به فیلدهای مدل
    field_mapping = {
        # فیلدهای Person
        'national_id': ('Person', 'national_id'),
        'name': ('Person', 'name'),
        'nature': ('Person', 'nature'),
        'registration_number': ('Person', 'registration_number'),
        'birth_date': ('Person', 'birth_date'),
        'activity_fields': ('Person', 'activity_fields'),
        'introducer': ('Person', 'introducer'),
        'description': ('Person', 'description'),
        
        # فیلدهای PhoneNumber
        'mobile_number': ('PhoneNumber', 'number'),
        'landline_number': ('PhoneNumber', 'number'),
        
        # فیلدهای FinancialBanking
        'economic_code': ('FinancialBanking', 'economic_code'),
        'tax_postal_code': ('FinancialBanking', 'tax_postal_code'),
        'tax_province': ('FinancialBanking', 'tax_province'),
        'tax_city': ('FinancialBanking', 'tax_city'),
        'tax_address': ('FinancialBanking', 'tax_address'),
        
        # فیلدهای DeliveryAddress
        'delivery_postal_code': ('DeliveryAddress', 'postal_code'),
        'recipient_name': ('DeliveryAddress', 'recipient_name'),
        'recipient_national_id': ('DeliveryAddress', 'recipient_national_id'),
        'unique_delivery_id': ('DeliveryAddress', 'unique_delivery_id'),
        'delivery_province': ('DeliveryAddress', 'province'),
        'delivery_city': ('DeliveryAddress', 'city'),
        'delivery_address': ('DeliveryAddress', 'address'),
        'delivery_landline': ('PhoneNumber', 'number'),
        'delivery_mobile': ('PhoneNumber', 'number'),
        'delivery_limit': ('DeliveryAddress', 'delivery_limit'),
        'recipient_type': ('DeliveryAddress', 'recipient_type'),
        
        # فیلدهای Representative
        'representative_name': ('Representative', 'name'),
        'representative_position': ('Representative', 'position'),
        'representative_mobile': ('PhoneNumber', 'number'),
        'representative_landline': ('PhoneNumber', 'number'),
        'representative_confirmation_letter': ('Representative', 'confirmation_letter'),
    }
    
    accessible_fields = {}
    
    for form_field_name in form.fields.keys():
        if form_field_name in field_mapping:
            model_name, model_field_name = field_mapping[form_field_name]
            
            # گرفتن ContentType برای مدل
            try:
                if model_name == 'Person':
                    from core.PersonFolder import Person as PersonModel
                    model_class = PersonModel
                elif model_name == 'PhoneNumber':
                    from core.PersonFolder.PhoneNumberModel import PhoneNumber
                    model_class = PhoneNumber
                elif model_name == 'FinancialBanking':
                    from core.PersonFolder.FinancialBankingModel import FinancialBanking
                    model_class = FinancialBanking
                elif model_name == 'DeliveryAddress':
                    from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
                    model_class = DeliveryAddress
                elif model_name == 'Representative':
                    from core.PersonFolder.RepresentativeModel import Representative
                    model_class = Representative
                else:
                    # اگر مدل شناخته شده نباشد، به طور پیش‌فرض دسترسی داده نمی‌شود
                    accessible_fields[form_field_name] = False
                    continue
                
                # بررسی دسترسی به فیلد: اولویت با قانون edit است، اگر نبود، قانون view بررسی شود
                accessible_fields[form_field_name] = check_field_access_prefer_edit(user, model_class, model_field_name)
                
            except Exception as e:
                # در صورت بروز خطا، به طور پیش‌فرض دسترسی داده نمی‌شود
                accessible_fields[form_field_name] = False
        else:
            # اگر فیلد در mapping نباشد، به طور پیش‌فرض دسترسی داده می‌شود
            accessible_fields[form_field_name] = True
    
    return accessible_fields


def get_accessible_delivery_fields(user, form):
    """بررسی دسترسی کاربر به فیلدهای فرم آدرس تحویل با سیستم جدید FieldPermission"""
    if user.is_superuser:
        return {field_name: True for field_name in form.fields.keys()}

    field_mapping = {
        'postal_code': ('DeliveryAddress', 'postal_code'),
        'recipient_name': ('DeliveryAddress', 'recipient_name'),
        'recipient_national_id': ('DeliveryAddress', 'recipient_national_id'),
        'unique_delivery_id': ('DeliveryAddress', 'unique_delivery_id'),
        'province': ('DeliveryAddress', 'province'),
        'city': ('DeliveryAddress', 'city'),
        'address': ('DeliveryAddress', 'address'),
        'delivery_limit': ('DeliveryAddress', 'delivery_limit'),
        'recipient_type': ('DeliveryAddress', 'recipient_type'),
        'delivery_mobile': ('PhoneNumber', 'number'),
        'delivery_landline': ('PhoneNumber', 'number'),
    }

    from core.PersonFolder.DeliveryAddressModel import DeliveryAddress as DeliveryAddressModel
    from core.PersonFolder.PhoneNumberModel import PhoneNumber as PhoneNumberModel

    model_map = {
        'DeliveryAddress': DeliveryAddressModel,
        'PhoneNumber': PhoneNumberModel,
    }

    accessible_fields = {}
    for form_field_name in form.fields.keys():
        if form_field_name in field_mapping:
            model_name, model_field_name = field_mapping[form_field_name]
            model_class = model_map.get(model_name)
            if model_class is None:
                accessible_fields[form_field_name] = False
                continue

            accessible_fields[form_field_name] = check_field_access_prefer_edit(
                user,
                model_class,
                model_field_name,
            )
        else:
            accessible_fields[form_field_name] = True

    return accessible_fields


def get_accessible_representative_fields(user, form):
    """بررسی دسترسی کاربر به فیلدهای فرم نماینده با سیستم جدید FieldPermission"""
    if user.is_superuser:
        return {field_name: True for field_name in form.fields.keys()}

    field_mapping = {
        'name': ('Representative', 'name'),
        'position': ('Representative', 'position'),
        'confirmation_letter': ('Representative', 'confirmation_letter'),
        'mobile': ('PhoneNumber', 'number'),
        'landline': ('PhoneNumber', 'number'),
    }

    from core.PersonFolder.RepresentativeModel import Representative as RepresentativeModel
    from core.PersonFolder.PhoneNumberModel import PhoneNumber as PhoneNumberModel

    model_map = {
        'Representative': RepresentativeModel,
        'PhoneNumber': PhoneNumberModel,
    }

    accessible_fields = {}
    for form_field_name in form.fields.keys():
        if form_field_name in field_mapping:
            model_name, model_field_name = field_mapping[form_field_name]
            model_class = model_map.get(model_name)
            if model_class is None:
                accessible_fields[form_field_name] = False
                continue

            accessible_fields[form_field_name] = check_field_access_prefer_edit(
                user,
                model_class,
                model_field_name,
            )
        else:
            accessible_fields[form_field_name] = True

    return accessible_fields


def get_accessible_bank_account_fields(user, form):
    """بررسی دسترسی کاربر به فیلدهای فرم حساب بانکی با سیستم جدید FieldPermission"""
    if user.is_superuser:
        return {field_name: True for field_name in form.fields.keys()}

    field_mapping = {
        'account_number': ('BankAccount', 'account_number'),
        'shaba_number': ('BankAccount', 'shaba_number'),
        'bank_name': ('BankAccount', 'bank_name'),
    }

    from core.PersonFolder.BankAccountModel import BankAccount as BankAccountModel

    accessible_fields = {}
    for form_field_name in form.fields.keys():
        if form_field_name in field_mapping:
            _, model_field_name = field_mapping[form_field_name]
            accessible_fields[form_field_name] = check_field_access_prefer_edit(
                user,
                BankAccountModel,
                model_field_name,
            )
        else:
            accessible_fields[form_field_name] = True

    return accessible_fields


def get_accessible_customer_fields(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش مشتری
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {
            'national_id': True,
            'name': True,
            'nature': True,
            'accounting_code': True,
            'sales_expert': True,
            'description': True,
        }

    from core.PersonFolder import Person as PersonModel

    # فیلدهایی که در لیست نمایش داده می‌شوند
    display_fields = {
        'national_id': 'national_id',
        'name': 'name',
        'nature': 'nature',
        'accounting_code': 'accounting_code',
        'sales_expert': 'sales_expert',
        'description': 'description',
    }

    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            PersonModel,
            model_field_name,
        )

    return accessible_fields


def get_accessible_customer_list_fields(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش لیست مشتریان
    برای استفاده در django-tables2
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    from core.PersonFolder import Person as PersonModel
    from core.PersonFolder.PhoneNumberModel import PhoneNumber as PhoneNumberModel
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {
            'national_id': True,
            'name': True,
            'nature': True,
            'mobile_number': True,
            'activity_fields': True,
            'actions': True,
        }
    
    # فیلدهایی که در لیست نمایش داده می‌شوند
    field_mapping = {
        'national_id': (PersonModel, 'national_id'),
        'name': (PersonModel, 'name'),
        'nature': (PersonModel, 'nature'),
        'mobile_number': (PhoneNumberModel, 'number'),
        'activity_fields': (PersonModel, 'activity_fields'),
        'actions': None,  # عملیات همیشه نمایش داده می‌شود
    }
    
    accessible_fields = {}
    for display_name, mapping in field_mapping.items():
        if mapping is None:
            # فیلدهایی که نیازی به بررسی دسترسی ندارند
            accessible_fields[display_name] = True
        else:
            model_class, model_field_name = mapping
            accessible_fields[display_name] = check_field_access_prefer_edit(
                user,
                model_class,
                model_field_name,
            )
    
    return accessible_fields


@login_required
def customer_list_view(request):
    """
    ویو برای نمایش لیست مشتریان با استفاده از django-tables2
    - فقط مشتریانی که کارشناس فروششان کاربر فعلی است نمایش داده می‌شوند
    - کنترل دسترسی فیلدها با FieldPermission
    - قابلیت جستجو و فیلتر
    """
    audit_logger.info("درخواست مشاهده لیست مشتریان")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_CUSTOMER.value):
        audit_logger.activity("تلاش برای مشاهده لیست مشتریان بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست مشتریان ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    activity_field_filter = request.GET.get('activity_field', '')
    province_filter = request.GET.get('province', '')
    
    # اگر کاربر superuser است، همه مشتریان را نمایش بده
    from django.db.models import OuterRef, Subquery, IntegerField, Q, Exists
    from django.contrib.contenttypes.models import ContentType
    from django.db.models.functions import Cast
    
    person_content_type = ContentType.objects.get_for_model(Person)
    
    # ایجاد subquery برای دریافت شماره همراه
    # تبدیل national_id به عدد برای مقایسه با object_id (PositiveIntegerField)
    # استفاده از Cast برای تبدیل national_id به integer
    # توجه: اگر national_id عدد نباشد، Cast خطا می‌دهد، اما در بیشتر موارد national_id عدد است
    mobile_subquery = PhoneNumber.objects.filter(
        content_type=person_content_type,
        object_id=Cast(OuterRef('national_id'), IntegerField()),
        phone_type='mobile',
        is_primary=True
    ).values('number')[:1]
    
    if request.user.is_superuser:
        customers = Person.objects.filter(type='customer').annotate(
            mobile_number_sort=Subquery(mobile_subquery)
        ).select_related().prefetch_related('activity_fields', 'financial_banking')
    else:
        # فقط مشتریانی که کارشناس فروششان کاربر فعلی است
        customers = Person.objects.filter(
            type='customer',
            sales_expert=request.user
        ).annotate(
            mobile_number_sort=Subquery(mobile_subquery)
        ).select_related().prefetch_related('activity_fields', 'financial_banking')
    
    # اعمال جستجو (عام‌تر - شامل نام، کد ملی، شماره همراه، حیطه فعالیت و استان)
    if search_query:
        from core.PersonFolder.PersonModel import ActivityField
        from core.PersonFolder.DeliveryAddressModel import DeliveryAddress
        
        # جستجو در شماره همراه با استفاده از Exists
        mobile_search_subquery = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=Cast(OuterRef('national_id'), IntegerField()),
            phone_type='mobile',
            is_primary=True,
            number__icontains=search_query
        )
        
        # ساخت query برای جستجو
        search_conditions = Q(
            Q(name__icontains=search_query) |
            Q(national_id__icontains=search_query) |
            Q(Exists(mobile_search_subquery))
        )
        
        # جستجو در حیطه فعالیت (اگر نتیجه‌ای پیدا شد)
        activity_field_search = ActivityField.objects.filter(
            code__icontains=search_query
        ).values_list('id', flat=True)
        if activity_field_search:
            search_conditions |= Q(activity_fields__in=activity_field_search)
        
        # جستجو در استان مالیاتی (اگر نتیجه‌ای پیدا شد)
        from core.PersonFolder.FinancialBankingModel import FinancialBanking
        province_search_persons = FinancialBanking.objects.filter(
            tax_province__icontains=search_query
        ).values_list('person_id', flat=True)
        if province_search_persons:
            search_conditions |= Q(id__in=province_search_persons)
        
        # اعمال جستجو
        customers = customers.filter(search_conditions).distinct()
    
    # اعمال فیلتر حیطه فعالیت
    if activity_field_filter:
        customers = customers.filter(activity_fields__id=activity_field_filter).distinct()
    
    # اعمال فیلتر استان مالیاتی
    if province_filter:
        from core.PersonFolder.FinancialBankingModel import FinancialBanking
        province_persons = FinancialBanking.objects.filter(
            tax_province=province_filter
        ).values_list('person_id', flat=True)
        customers = customers.filter(id__in=province_persons).distinct()
    
    bug_logger.debug(f"تعداد {customers.count()} مشتری برای نمایش لود شد")
    
    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = get_accessible_customer_list_fields(request.user)
    
    # دریافت لیست حیطه‌های فعالیت و استان‌های مالیاتی برای dropdown
    from core.PersonFolder.PersonModel import ActivityField
    activity_fields = ActivityField.objects.all().order_by('code')
    
    from core.PersonFolder.FinancialBankingModel import FinancialBanking
    provinces = FinancialBanking.objects.exclude(
        tax_province__isnull=True
    ).exclude(
        tax_province=''
    ).values_list('tax_province', flat=True).distinct().order_by('tax_province')
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    table = CustomerTable(customers, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'search_query': search_query,
        'activity_field_filter': activity_field_filter,
        'province_filter': province_filter,
        'activity_fields': activity_fields,
        'provinces': provinces,
        'page_title': 'لیست مشتریان'
    }
    
    return render(request, 'customer/customer_list.html', context)


@login_required
def customer_detail_view(request, national_id):
    """
    ویو برای نمایش جزئیات مشتری (فقط نمایشی - read-only)
    - نمایش اطلاعات در popup
    - پشتیبانی از AJAX
    """
    audit_logger.info(f"درخواست مشاهده جزئیات مشتری با کد ملی {national_id}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_CUSTOMER.value):
        audit_logger.activity("تلاش برای مشاهده جزئیات مشتری بدون دسترسی")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'error': 'شما دسترسی به این بخش ندارید.'}, status=403)
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت مشتری
    person = get_object_or_404(Person, national_id=national_id, type='customer')
    
    # بررسی دسترسی: فقط superuser یا کارشناس فروش خود مشتری می‌تواند مشاهده کند
    if not request.user.is_superuser and person.sales_expert != request.user:
        audit_logger.activity(f"تلاش برای مشاهده جزئیات مشتری {national_id} متعلق به کاربر دیگر")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'error': 'شما دسترسی به این بخش ندارید.'}, status=403)
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت اطلاعات مرتبط
    person_content_type = ContentType.objects.get_for_model(Person)
    try:
        person_national_id_int = int(person.national_id)
    except (ValueError, TypeError):
        person_national_id_int = person.national_id
    
    person_phones = PhoneNumber.objects.filter(
        content_type=person_content_type,
        object_id=person_national_id_int
    )
    mobile_number = person_phones.filter(phone_type='mobile', is_primary=True).first()
    landline_number = person_phones.filter(phone_type='landline').first()
    
    # دریافت FinancialBanking
    financial_banking = None
    try:
        financial_banking = person.financial_banking.first()
    except:
        pass
    
    # دریافت آدرس‌های تحویل
    delivery_addresses = person.delivery_addresses.all()
    
    # دریافت نمایندگان
    representatives = person.representatives.all()
    
    # دریافت حساب‌های بانکی
    bank_accounts = []
    if financial_banking:
        bank_accounts = financial_banking.bank_accounts.all()
    
    # محاسبه فیلدهای قابل دسترسی برای نمایش
    accessible_fields = get_accessible_customer_fields(request.user)
    
    context = {
        'person': person,
        'mobile_number': mobile_number,
        'landline_number': landline_number,
        'financial_banking': financial_banking,
        'delivery_addresses': delivery_addresses,
        'representatives': representatives,
        'bank_accounts': bank_accounts,
        'accessible_fields': accessible_fields,
    }
    
    return render(request, 'customer/customer_detail_popup.html', context)


@login_required
def edit_customer_view(request, national_id):
    """
    ویو برای ویرایش مشتری موجود
    - بررسی دسترسی با TaskPermission
    - بررسی دسترسی فیلدها با FieldAccessRule
    """
    audit_logger.info(f"درخواست ویرایش مشتری با کد ملی {national_id}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_CUSTOMER.value):
        audit_logger.activity("تلاش برای ویرایش مشتری بدون دسترسی")
        messages.error(request, 'شما دسترسی به ویرایش مشتری ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت مشتری
    person = get_object_or_404(Person, national_id=national_id, type='customer')
    
    # بررسی دسترسی: فقط superuser یا کارشناس فروش خود مشتری می‌تواند ویرایش کند
    if not request.user.is_superuser and person.sales_expert != request.user:
        audit_logger.activity(f"تلاش برای ویرایش مشتری {national_id} متعلق به کاربر دیگر")
        messages.error(request, 'شما دسترسی به ویرایش این مشتری ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت اطلاعات مرتبط
    person_content_type = ContentType.objects.get_for_model(Person)
    # استفاده از int() برای تبدیل national_id به عدد (چون object_id یک PositiveIntegerField است)
    try:
        person_national_id_int = int(person.national_id)
    except (ValueError, TypeError):
        person_national_id_int = person.national_id
    person_phones = PhoneNumber.objects.filter(
        content_type=person_content_type,
        object_id=person_national_id_int
    )
    mobile_number = person_phones.filter(phone_type='mobile', is_primary=True).first()
    landline_number = person_phones.filter(phone_type='landline').first()
    
    # دریافت FinancialBanking
    financial_banking = None
    try:
        financial_banking = person.financial_banking.first()
    except:
        pass
    
    # دریافت آدرس‌های تحویل
    delivery_addresses = person.delivery_addresses.all()
    
    # دریافت نمایندگان
    representatives = person.representatives.all()
    
    # دریافت حساب‌های بانکی
    bank_accounts = []
    if financial_banking:
        bank_accounts = financial_banking.bank_accounts.all()
    
    if request.method == 'POST':
        # ابتدا map دسترسی فیلدها را به دست آوریم و سپس فرم را با آن بسازیم
        temp_form_for_access = CreateCustomerForm()
        temp_delivery_form = DeliveryAddressForm()
        temp_rep_form = RepresentativeForm()
        temp_bank_form = BankAccountForm()
        
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        accessible_delivery_fields = get_accessible_delivery_fields(request.user, temp_delivery_form)
        accessible_rep_fields = get_accessible_representative_fields(request.user, temp_rep_form)
        accessible_bank_fields = get_accessible_bank_account_fields(request.user, temp_bank_form)
        
        form = CreateCustomerForm(request.POST, request.FILES, user=request.user, accessible_fields=accessible_fields, instance=person)
        delivery_formset = build_delivery_address_formset(request.POST, request.FILES, accessible_fields=accessible_delivery_fields, instance=person)
        rep_formset = build_representative_formset(request.POST, request.FILES, accessible_fields=accessible_rep_fields, instance=person)
        bank_formset = build_bank_account_formset(request.POST, request.FILES, accessible_fields=accessible_bank_fields, instance=financial_banking)
        
        if form.is_valid() and delivery_formset.is_valid() and rep_formset.is_valid() and bank_formset.is_valid():
            try:
                with transaction.atomic():
                    # به‌روزرسانی مشتری
                    person = form.save_customer(request.user, update=True)
                    
                    # بررسی وجود حساب بانکی
                    has_bank_account = False
                    for bank_form in bank_formset:
                        if not getattr(bank_form, 'cleaned_data', None):
                            continue
                        if bank_form.cleaned_data.get('DELETE', False):
                            continue
                        account_number = bank_form.cleaned_data.get('account_number')
                        if account_number:
                            has_bank_account = True
                            break
                    
                    # ایجاد یا به‌روزرسانی اطلاعات مالیاتی
                    from core.PersonFolder.FinancialBankingModel import FinancialBanking
                    
                    # اگر حساب بانکی وجود دارد یا فیلدهای مالیاتی پر شده‌اند، FinancialBanking ایجاد/به‌روزرسانی کن
                    if has_bank_account or any([
                        form.cleaned_data.get('economic_code'),
                        form.cleaned_data.get('tax_postal_code'),
                        form.cleaned_data.get('tax_province'),
                        form.cleaned_data.get('tax_city'),
                        form.cleaned_data.get('tax_address')
                    ]):
                        if not financial_banking:
                            # ایجاد FinancialBanking جدید
                            financial_banking = FinancialBanking.objects.create(
                                person=person,
                                economic_code=clean_empty_to_none(form.cleaned_data.get('economic_code')),
                                tax_postal_code=clean_empty_to_none(form.cleaned_data.get('tax_postal_code')),
                                tax_province=clean_empty_to_none(form.cleaned_data.get('tax_province')),
                                tax_city=clean_empty_to_none(form.cleaned_data.get('tax_city')),
                                tax_address=clean_empty_to_none(form.cleaned_data.get('tax_address'))
                            )
                        else:
                            # به‌روزرسانی FinancialBanking موجود
                            financial_banking.economic_code = clean_empty_to_none(form.cleaned_data.get('economic_code'))
                            financial_banking.tax_postal_code = clean_empty_to_none(form.cleaned_data.get('tax_postal_code'))
                            financial_banking.tax_province = clean_empty_to_none(form.cleaned_data.get('tax_province'))
                            financial_banking.tax_city = clean_empty_to_none(form.cleaned_data.get('tax_city'))
                            financial_banking.tax_address = clean_empty_to_none(form.cleaned_data.get('tax_address'))
                            financial_banking.save()
                    
                    # مدیریت حساب‌های بانکی
                    if financial_banking:
                        for bank_form in bank_formset:
                            if not getattr(bank_form, 'cleaned_data', None):
                                continue
                            
                            if bank_form.cleaned_data.get('DELETE', False):
                                # حذف حساب بانکی
                                if bank_form.cleaned_data.get('id'):
                                    BankAccount.objects.filter(id=bank_form.cleaned_data['id']).delete()
                                continue
                            
                            account_number = bank_form.cleaned_data.get('account_number')
                            if not account_number:
                                continue
                            
                            bank_id = bank_form.cleaned_data.get('id')
                            if bank_id:
                                # به‌روزرسانی حساب بانکی موجود
                                bank_account = BankAccount.objects.get(id=bank_id)
                                bank_account.account_number = account_number
                                bank_account.shaba_number = clean_empty_to_none(bank_form.cleaned_data.get('shaba_number'))
                                bank_account.bank_name = clean_empty_to_none(bank_form.cleaned_data.get('bank_name'))
                                bank_account.save()
                            else:
                                # ایجاد حساب بانکی جدید
                                BankAccount.objects.create(
                                    financial_banking=financial_banking,
                                    account_number=account_number,
                                    shaba_number=clean_empty_to_none(bank_form.cleaned_data.get('shaba_number')),
                                    bank_name=clean_empty_to_none(bank_form.cleaned_data.get('bank_name'))
                                )
                    
                    # مدیریت آدرس‌های تحویل
                    for delivery_form in delivery_formset:
                        if not getattr(delivery_form, 'cleaned_data', None):
                            continue
                        if delivery_form.cleaned_data.get('DELETE', False):
                            # حذف آدرس تحویل
                            if delivery_form.cleaned_data.get('postal_code'):
                                DeliveryAddress.objects.filter(postal_code=delivery_form.cleaned_data['postal_code']).delete()
                            continue
                        postal_code = delivery_form.cleaned_data.get('postal_code')
                        if not postal_code:
                            continue
                        
                        delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
                        
                        # بررسی وجود آدرس
                        existing_address = DeliveryAddress.objects.filter(postal_code=postal_code, person=person).first()
                        if existing_address:
                            # به‌روزرسانی آدرس موجود
                            existing_address.recipient_name = delivery_form.cleaned_data.get('recipient_name', person.name)
                            existing_address.recipient_national_id = clean_empty_to_none(delivery_form.cleaned_data.get('recipient_national_id'))
                            existing_address.unique_delivery_id = clean_empty_to_none(delivery_form.cleaned_data.get('unique_delivery_id'))
                            existing_address.province = delivery_form.cleaned_data.get('province', '')
                            existing_address.city = delivery_form.cleaned_data.get('city', '')
                            existing_address.address = delivery_form.cleaned_data.get('address', '')
                            existing_address.delivery_limit = clean_empty_to_none(delivery_form.cleaned_data.get('delivery_limit'))
                            existing_address.recipient_type = clean_empty_to_none(delivery_form.cleaned_data.get('recipient_type'))
                            existing_address.save()
                            delivery_address = existing_address
                        else:
                            # ایجاد آدرس جدید
                            delivery_address = DeliveryAddress.objects.create(
                                person=person,
                                postal_code=postal_code,
                                recipient_name=delivery_form.cleaned_data.get('recipient_name', person.name),
                                recipient_national_id=clean_empty_to_none(delivery_form.cleaned_data.get('recipient_national_id')),
                                unique_delivery_id=clean_empty_to_none(delivery_form.cleaned_data.get('unique_delivery_id')),
                                province=delivery_form.cleaned_data.get('province', ''),
                                city=delivery_form.cleaned_data.get('city', ''),
                                address=delivery_form.cleaned_data.get('address', ''),
                                delivery_limit=clean_empty_to_none(delivery_form.cleaned_data.get('delivery_limit')),
                                recipient_type=clean_empty_to_none(delivery_form.cleaned_data.get('recipient_type'))
                            )
                        
                        # مدیریت شماره‌های تماس آدرس تحویل
                        # حذف شماره‌های قدیمی
                        PhoneNumber.objects.filter(
                            content_type=delivery_content_type,
                            object_id=delivery_address.postal_code
                        ).delete()
                        
                        if delivery_form.cleaned_data.get('delivery_mobile'):
                            PhoneNumber.objects.create(
                                content_type=delivery_content_type,
                                object_id=delivery_address.postal_code,
                                phone_type='mobile',
                                number=delivery_form.cleaned_data['delivery_mobile'],
                                is_primary=True
                            )
                        
                        if delivery_form.cleaned_data.get('delivery_landline'):
                            PhoneNumber.objects.create(
                                content_type=delivery_content_type,
                                object_id=delivery_address.postal_code,
                                phone_type='landline',
                                number=delivery_form.cleaned_data['delivery_landline'],
                                is_primary=False
                            )
                    
                    # مدیریت نمایندگان
                    for rep_form in rep_formset:
                        if not getattr(rep_form, 'cleaned_data', None):
                            continue
                        if rep_form.cleaned_data.get('DELETE', False):
                            # حذف نماینده
                            if rep_form.cleaned_data.get('name'):
                                Representative.objects.filter(name=rep_form.cleaned_data['name'], person=person).delete()
                            continue
                        rep_name = rep_form.cleaned_data.get('name')
                        if not rep_name:
                            continue
                        
                        rep_content_type = ContentType.objects.get_for_model(Representative)
                        
                        # بررسی وجود نماینده
                        existing_rep = Representative.objects.filter(name=rep_name, person=person).first()
                        if existing_rep:
                            # به‌روزرسانی نماینده موجود
                            existing_rep.position = rep_form.cleaned_data.get('position') or ''
                            if rep_form.cleaned_data.get('confirmation_letter'):
                                existing_rep.confirmation_letter = rep_form.cleaned_data.get('confirmation_letter')
                            existing_rep.save()
                            representative = existing_rep
                        else:
                            # ایجاد نماینده جدید
                            representative = Representative.objects.create(
                                person=person,
                                name=rep_name,
                                position=rep_form.cleaned_data.get('position') or '',
                                confirmation_letter=rep_form.cleaned_data.get('confirmation_letter')
                            )
                        
                        # مدیریت شماره‌های تماس نماینده
                        # حذف شماره‌های قدیمی
                        PhoneNumber.objects.filter(
                            content_type=rep_content_type,
                            object_id=representative.id
                        ).delete()
                        
                        if rep_form.cleaned_data.get('mobile'):
                            PhoneNumber.objects.create(
                                content_type=rep_content_type,
                                object_id=representative.id,
                                phone_type='mobile',
                                number=rep_form.cleaned_data['mobile'],
                                is_primary=True
                            )
                        
                        if rep_form.cleaned_data.get('landline'):
                            PhoneNumber.objects.create(
                                content_type=rep_content_type,
                                object_id=representative.id,
                                phone_type='landline',
                                number=rep_form.cleaned_data['landline'],
                                is_primary=False
                            )
                
                bug_logger.info(f"مشتری {person.name} با موفقیت ویرایش شد")
                messages.success(request, f'مشتری "{person.name}" با موفقیت ویرایش شد.')
                return redirect('sales:customer_list')
                
            except Exception as e:
                bug_logger.error(f"خطا در ویرایش مشتری: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ویرایش مشتری: {str(e)}')
        else:
            # فرم معتبر نیست
            bug_logger.warning("فرم ویرایش مشتری معتبر نیست")
    else:
        # در GET نیز فیلدهای غیرمجاز را از فرم حذف کن تا در UI نمایش داده نشوند
        temp_form_for_access = CreateCustomerForm()
        temp_delivery_form = DeliveryAddressForm()
        temp_rep_form = RepresentativeForm()
        temp_bank_form = BankAccountForm()
        
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        accessible_delivery_fields = get_accessible_delivery_fields(request.user, temp_delivery_form)
        accessible_rep_fields = get_accessible_representative_fields(request.user, temp_rep_form)
        accessible_bank_fields = get_accessible_bank_account_fields(request.user, temp_bank_form)
        
        # پر کردن فرم با اطلاعات موجود
        initial_data = {
            'national_id': person.national_id,
            'name': person.name,
            'nature': person.nature,
            'registration_number': person.registration_number,
            'birth_date': person.birth_date.strftime('%Y-%m-%d') if person.birth_date else '',
            'activity_fields': list(person.activity_fields.all()),
            'introducer': person.introducer,
            'description': person.description,
        }
        
        if mobile_number:
            initial_data['mobile_number'] = mobile_number.number
        if landline_number:
            initial_data['landline_number'] = landline_number.number
        
        if financial_banking:
            initial_data['economic_code'] = financial_banking.economic_code
            initial_data['tax_postal_code'] = financial_banking.tax_postal_code
            initial_data['tax_province'] = financial_banking.tax_province
            initial_data['tax_city'] = financial_banking.tax_city
            initial_data['tax_address'] = financial_banking.tax_address
        
        form = CreateCustomerForm(initial=initial_data, user=request.user, accessible_fields=accessible_fields, instance=person)
        
        # آماده‌سازی formsets با اطلاعات موجود
        delivery_initial = []
        for addr in delivery_addresses:
            delivery_content_type = ContentType.objects.get_for_model(DeliveryAddress)
            addr_mobile = PhoneNumber.objects.filter(
                content_type=delivery_content_type,
                object_id=addr.postal_code,
                phone_type='mobile'
            ).first()
            addr_landline = PhoneNumber.objects.filter(
                content_type=delivery_content_type,
                object_id=addr.postal_code,
                phone_type='landline'
            ).first()
            
            delivery_initial.append({
                'postal_code': addr.postal_code,
                'recipient_name': addr.recipient_name,
                'recipient_national_id': addr.recipient_national_id,
                'unique_delivery_id': addr.unique_delivery_id,
                'province': addr.province,
                'city': addr.city,
                'address': addr.address,
                'delivery_limit': addr.delivery_limit,
                'recipient_type': addr.recipient_type,
                'delivery_mobile': addr_mobile.number if addr_mobile else '',
                'delivery_landline': addr_landline.number if addr_landline else '',
            })
        
        rep_initial = []
        for rep in representatives:
            rep_content_type = ContentType.objects.get_for_model(Representative)
            rep_mobile = PhoneNumber.objects.filter(
                content_type=rep_content_type,
                object_id=rep.id,
                phone_type='mobile'
            ).first()
            rep_landline = PhoneNumber.objects.filter(
                content_type=rep_content_type,
                object_id=rep.id,
                phone_type='landline'
            ).first()
            
            rep_initial.append({
                'name': rep.name,
                'position': rep.position,
                'confirmation_letter': rep.confirmation_letter,
                'mobile': rep_mobile.number if rep_mobile else '',
                'landline': rep_landline.number if rep_landline else '',
            })
        
        bank_initial = []
        for bank in bank_accounts:
            bank_initial.append({
                'id': bank.id,
                'account_number': bank.account_number,
                'shaba_number': bank.shaba_number,
                'bank_name': bank.bank_name,
            })
        
        delivery_formset = build_delivery_address_formset(initial=delivery_initial, accessible_fields=accessible_delivery_fields)
        rep_formset = build_representative_formset(initial=rep_initial, accessible_fields=accessible_rep_fields)
        bank_formset = build_bank_account_formset(initial=bank_initial, accessible_fields=accessible_bank_fields)
    
    # گرفتن فیلدهای قابل دسترسی برای کاربر
    if 'accessible_fields' not in locals():
        temp_form_for_access = CreateCustomerForm()
        temp_delivery_form = DeliveryAddressForm()
        temp_rep_form = RepresentativeForm()
        temp_bank_form = BankAccountForm()
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        accessible_delivery_fields = get_accessible_delivery_fields(request.user, temp_delivery_form)
        accessible_rep_fields = get_accessible_representative_fields(request.user, temp_rep_form)
        accessible_bank_fields = get_accessible_bank_account_fields(request.user, temp_bank_form)
    
    if 'delivery_formset' not in locals():
        delivery_formset = build_delivery_address_formset(accessible_fields=accessible_delivery_fields)
    if 'rep_formset' not in locals():
        rep_formset = build_representative_formset(accessible_fields=accessible_rep_fields)
    if 'bank_formset' not in locals():
        bank_formset = build_bank_account_formset(accessible_fields=accessible_bank_fields)
    
    context = {
        'form': form,
        'delivery_formset': delivery_formset,
        'rep_formset': rep_formset,
        'bank_formset': bank_formset,
        'accessible_fields': accessible_fields,
        'accessible_delivery_fields': accessible_delivery_fields,
        'accessible_rep_fields': accessible_rep_fields,
        'accessible_bank_fields': accessible_bank_fields,
        'page_title': f'ویرایش مشتری {person.name}',
        'person': person,
    }
    
    return render(request, 'customer/edit_customer.html', context)
