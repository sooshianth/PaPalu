from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from core.RBACModel import user_has_task, TaskChoices
from access.models.FieldAccessUserModel import FieldAccessRule
from sales.forms.create_customer_form import CreateCustomerForm
from core.PersonFolder import Person
from django.contrib.contenttypes.models import ContentType


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
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        form = CreateCustomerForm(request.POST, request.FILES, user=request.user, accessible_fields=accessible_fields)
        
        if form.is_valid():
            try:
                # ذخیره مشتری
                person = form.save_customer(request.user)
                
                messages.success(request, f'مشتری "{person.name}" با موفقیت ایجاد شد.')
                return redirect('sales:customer_list')  # فرض می‌کنیم این URL را بعداً تعریف می‌کنیم
                
            except Exception as e:
                messages.error(request, f'خطا در ایجاد مشتری: {str(e)}')
    else:
        # در GET نیز فیلدهای غیرمجاز را از فرم حذف کن تا در UI نمایش داده نشوند
        temp_form_for_access = CreateCustomerForm()
        accessible_fields = get_accessible_form_fields(request.user, temp_form_for_access)
        form = CreateCustomerForm(user=request.user, accessible_fields=accessible_fields)
    
    # گرفتن فیلدهای قابل دسترسی برای کاربر
    # اگر در بالا محاسبه نشده بود (به‌ویژه در مسیر POST با خطای ولیدیشن)، محاسبه کن
    if 'accessible_fields' not in locals():
        accessible_fields = get_accessible_form_fields(request.user, form)
    
    context = {
        'form': form,
        'accessible_fields': accessible_fields,
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
                content_type = ContentType.objects.get_for_model(model_class)
                
                rule_edit = FieldAccessRule.objects.filter(
                    user=user,
                    content_type=content_type,
                    field_name=model_field_name,
                    access_type='edit'
                ).first()
                
                if rule_edit is not None:
                    accessible_fields[form_field_name] = rule_edit.allowed
                else:
                    rule_view = FieldAccessRule.objects.filter(
                        user=user,
                        content_type=content_type,
                        field_name=model_field_name,
                        access_type='view'
                    ).first()
                    if rule_view is not None:
                        accessible_fields[form_field_name] = rule_view.allowed
                    else:
                        # اگر هیچ قانونی تعریف نشده، دسترسی داده می‌شود
                        accessible_fields[form_field_name] = True
                
            except Exception as e:
                # در صورت بروز خطا، به طور پیش‌فرض دسترسی داده نمی‌شود
                accessible_fields[form_field_name] = False
        else:
            # اگر فیلد در mapping نباشد، به طور پیش‌فرض دسترسی داده می‌شود
            accessible_fields[form_field_name] = True
    
    return accessible_fields


def get_accessible_customer_fields(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش مشتری
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    if user.is_superuser:
        # superuser به همه فیلدها دسترسی دارد
        return {
            'national_id': True,
            'name': True,
            'nature': True,
            'accounting_code': True,
            'sales_expert': True,
            'description': True,
        }
    
    # import مدل Person
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
    content_type = ContentType.objects.get_for_model(PersonModel)
    
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

