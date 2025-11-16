from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction

from core.RBACModel import user_has_task, TaskChoices
from access.helpers import check_field_access_prefer_edit
from sales.forms.create_customer_form import (
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
from sales.forms.create_customer_form import clean_empty_to_none


@login_required
def create_customer_view(request):
    """
    ویو برای ایجاد مشتری جدید
    - بررسی دسترسی با TaskPermission
    - بررسی دسترسی فیلدها با FieldAccessRule
    """
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_CUSTOMER.value):
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
                    
                    # ایجاد اطلاعات مالیاتی (در صورت وجود هر یک از فیلدها)
                    financial_banking = None
                    if any([
                        form.cleaned_data.get('economic_code'),
                        form.cleaned_data.get('tax_postal_code'),
                        form.cleaned_data.get('tax_province'),
                        form.cleaned_data.get('tax_city'),
                        form.cleaned_data.get('tax_address')
                    ]):
                        from core.PersonFolder.FinancialBankingModel import FinancialBanking
                        financial_banking = FinancialBanking.objects.create(
                            person=person,
                            economic_code=clean_empty_to_none(form.cleaned_data.get('economic_code')),
                            tax_postal_code=clean_empty_to_none(form.cleaned_data.get('tax_postal_code')),
                            tax_province=clean_empty_to_none(form.cleaned_data.get('tax_province')),
                            tax_city=clean_empty_to_none(form.cleaned_data.get('tax_city')),
                            tax_address=clean_empty_to_none(form.cleaned_data.get('tax_address'))
                        )
                    
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
                                object_id=representative.name,
                                phone_type='mobile',
                                number=rep_form.cleaned_data['mobile'],
                                is_primary=True
                            )
                        
                        if rep_form.cleaned_data.get('landline'):
                            PhoneNumber.objects.create(
                                content_type=rep_content_type,
                                object_id=representative.name,
                                phone_type='landline',
                                number=rep_form.cleaned_data['landline'],
                                is_primary=False
                            )
                
                messages.success(request, f'مشتری "{person.name}" با موفقیت ایجاد شد.')
                return redirect('sales:customer_list')
                
            except Exception as e:
                messages.error(request, f'خطا در ایجاد مشتری: {str(e)}')
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
    
    return render(request, 'sales/create_customer.html', context)


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
        'user_type': ('Person', 'user_type'),
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


@login_required
def customer_list_view(request):
    """
    ویو برای نمایش لیست مشتریان
    - فقط مشتریانی که کارشناس فروششان کاربر فعلی است نمایش داده می‌شوند
    """
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_CUSTOMER.value):
        messages.error(request, 'شما دسترسی به مشاهده لیست مشتریان ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # اگر کاربر superuser است، همه مشتریان را نمایش بده
    if request.user.is_superuser:
        customers = Person.objects.filter(type='customer').order_by('-name')
    else:
        # فقط مشتریانی که کارشناس فروششان کاربر فعلی است
        customers = Person.objects.filter(
            type='customer',
            sales_expert=request.user.username
        ).order_by('-name')
    
    # گرفتن فیلدهای قابل دسترسی برای کاربر
    accessible_fields = get_accessible_customer_fields(request.user)
    
    context = {
        'customers': customers,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست مشتریان'
    }
    
    return render(request, 'sales/customer_list.html', context)

