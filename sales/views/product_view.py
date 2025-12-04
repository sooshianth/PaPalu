from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from core.RBACModel import user_has_task, TaskChoices
from sales.forms.product_create_form import (
    CreateProductForm,
    ProductionInfoFormSet,
    BOMFormSet,
    ProductionInfoModelFormSet,
    BOMModelFormSet,
    get_accessible_product_fields,
)
from core.helpers import check_field_access_prefer_edit
from sales.tables import ProductTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def generate_suggested_product_code():
    """
    تولید شناسه محصول پیشنهادی به صورت خودکار
    الگو: PRD-001, PRD-002, ...
    """
    try:
        # دریافت آخرین محصول بر اساس کد که با PRD- شروع می‌شود
        last_product = Product.objects.filter(code__startswith='PRD-').order_by('-code').first()
        
        if last_product and last_product.code:
            # استخراج عدد از آخرین کد
            try:
                # اگر کد به صورت PRD-001 باشد
                parts = last_product.code.split('-')
                if len(parts) == 2 and parts[0] == 'PRD':
                    last_number = int(parts[1])
                    new_number = last_number + 1
                    # بررسی اینکه آیا این کد جدید تکراری نیست
                    new_code = f"PRD-{new_number:03d}"
                    if not Product.objects.filter(code=new_code).exists():
                        return new_code
                    # اگر تکراری بود، به دنبال کد بعدی می‌گردیم
                    while Product.objects.filter(code=new_code).exists():
                        new_number += 1
                        new_code = f"PRD-{new_number:03d}"
                    return new_code
            except (ValueError, IndexError):
                pass
    except Exception as e:
        bug_logger.warning(f"خطا در تولید شناسه محصول پیشنهادی: {str(e)}")
    
    # اگر محصولی وجود نداشت یا خطا رخ داد، از 001 شروع می‌کنیم
    # اما ابتدا بررسی می‌کنیم که آیا PRD-001 تکراری است یا نه
    suggested_code = "PRD-001"
    counter = 1
    while Product.objects.filter(code=suggested_code).exists():
        counter += 1
        suggested_code = f"PRD-{counter:03d}"
    
    return suggested_code


def generate_suggested_formula_id():
    """
    تولید شناسه فرمول پیشنهادی به صورت خودکار
    الگو: FML-001, FML-002, ...
    """
    from core.ProductFolder.ProductionInfoModel import ProductionInfo
    
    try:
        # دریافت آخرین فرمول بر اساس شناسه که با FML- شروع می‌شود
        last_formula = ProductionInfo.objects.filter(formula_id__startswith='FML-').exclude(formula_id__isnull=True).exclude(formula_id='').order_by('-formula_id').first()
        
        if last_formula and last_formula.formula_id:
            # استخراج عدد از آخرین شناسه
            try:
                parts = last_formula.formula_id.split('-')
                if len(parts) == 2 and parts[0] == 'FML':
                    last_number = int(parts[1])
                    new_number = last_number + 1
                    # بررسی اینکه آیا این شناسه جدید تکراری نیست
                    new_formula_id = f"FML-{new_number:03d}"
                    if not ProductionInfo.objects.filter(formula_id=new_formula_id).exists():
                        return new_formula_id
                    # اگر تکراری بود، به دنبال شناسه بعدی می‌گردیم
                    while ProductionInfo.objects.filter(formula_id=new_formula_id).exists():
                        new_number += 1
                        new_formula_id = f"FML-{new_number:03d}"
                    return new_formula_id
            except (ValueError, IndexError):
                pass
    except Exception as e:
        bug_logger.warning(f"خطا در تولید شناسه فرمول پیشنهادی: {str(e)}")
    
    # اگر فرمولی وجود نداشت یا خطا رخ داد، از 001 شروع می‌کنیم
    # اما ابتدا بررسی می‌کنیم که آیا FML-001 تکراری است یا نه
    suggested_formula_id = "FML-001"
    counter = 1
    while ProductionInfo.objects.filter(formula_id=suggested_formula_id).exists():
        counter += 1
        suggested_formula_id = f"FML-{counter:03d}"
    
    return suggested_formula_id


@login_required
def create_product_view(request):
    """
    ویو ایجاد محصول جدید با formset برای ProductionInfo و BOM
    - بررسی دسترسی با TaskPermission
    - بررسی دسترسی فیلدها با FieldAccessRule
    """
    audit_logger.info(f"درخواست ایجاد محصول جدید توسط کاربر {request.user.username}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_CREATE_PRODUCT.value):
        audit_logger.activity("تلاش برای ایجاد محصول بدون دسترسی")
        messages.error(request, 'شما دسترسی به ایجاد محصول ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت فیلدهای قابل دسترسی برای کاربر
    accessible_fields = get_accessible_product_fields(request.user)
    
    if request.method == 'POST':
        # ایجاد فرم با داده‌های ارسالی
        product_form = CreateProductForm(
            request.POST,
            request.FILES,
            user=request.user,
            accessible_fields=accessible_fields
        )
        
        # ایجاد formset برای ProductionInfo
        production_info_formset = ProductionInfoFormSet(
            request.POST,
            prefix='production_info'
        )
        
        # ایجاد formset برای BOM
        bom_formset = BOMFormSet(
            request.POST,
            prefix='bom'
        )
        
        if product_form.is_valid() and production_info_formset.is_valid() and bom_formset.is_valid():
            try:
                # بررسی اینکه حداقل یک ProductionInfo و BOM وجود دارد
                production_info_count = 0
                for production_info_form in production_info_formset:
                    if production_info_form.cleaned_data and not production_info_form.cleaned_data.get('DELETE', False):
                        # بررسی اینکه آیا همه فیلدهای اجباری پر شده‌اند
                        if all([
                            production_info_form.cleaned_data.get('formula_id'),
                            production_info_form.cleaned_data.get('min_batch_production') is not None,
                            production_info_form.cleaned_data.get('specific_production_instruction'),
                        ]):
                            production_info_count += 1
                
                bom_count = 0
                for bom_form in bom_formset:
                    if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                        # بررسی اینکه آیا همه فیلدهای اجباری پر شده‌اند
                        if all([
                            bom_form.cleaned_data.get('raw_material'),
                            bom_form.cleaned_data.get('quantity') is not None,
                        ]):
                            bom_count += 1
                
                if production_info_count == 0:
                    messages.error(request, 'حداقل یک اطلاعات تولید کامل (شامل شناسه فرمول، حداقل بچ تولید و دستور العمل) الزامی است.')
                elif bom_count == 0:
                    messages.error(request, 'حداقل یک ماده اولیه کامل (شامل نام ماده اولیه و مقدار به کیلوگرم) در BOM الزامی است.')
                else:
                    with transaction.atomic():
                        # ذخیره محصول اصلی
                        product = product_form.save()
                        
                        # ذخیره اطلاعات تولید
                        production_infos = []
                        for production_info_form in production_info_formset:
                            if production_info_form.cleaned_data and not production_info_form.cleaned_data.get('DELETE', False):
                                # بررسی اینکه آیا همه فیلدهای اجباری پر شده‌اند
                                if all([
                                    production_info_form.cleaned_data.get('formula_id'),
                                    production_info_form.cleaned_data.get('min_batch_production') is not None,
                                    production_info_form.cleaned_data.get('specific_production_instruction'),
                                ]):
                                    production_info = production_info_form.save(commit=False)
                                    production_info.product = product
                                    production_info.save()
                                    production_infos.append(production_info)
                        
                        # ذخیره BOM ها - لینک به اولین ProductionInfo
                        if production_infos:
                            first_production_info = production_infos[0]
                            for bom_form in bom_formset:
                                if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                                    # بررسی اینکه آیا همه فیلدهای اجباری پر شده‌اند
                                    if all([
                                        bom_form.cleaned_data.get('raw_material'),
                                        bom_form.cleaned_data.get('quantity') is not None,
                                    ]):
                                        bom = bom_form.save(commit=False)
                                        bom.production_info = first_production_info
                                        bom.save()
                        
                        audit_logger.info(f"محصول جدید با کد {product.code} توسط کاربر {request.user.username} ایجاد شد")
                        messages.success(
                            request,
                            f'محصول "{product.name}" با کد "{product.code}" با موفقیت ایجاد شد.'
                        )
                        
                        return redirect('sales:product_list')
                    
            except Exception as e:
                bug_logger.error(f"خطا در ایجاد محصول: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    f'خطا در ایجاد محصول: {str(e)}'
                )
        else:
            # نمایش خطاهای فرم
            bug_logger.warning("فرم ایجاد محصول معتبر نیست")
            if not product_form.is_valid():
                for field, errors in product_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if not production_info_formset.is_valid():
                for form in production_info_formset:
                    if form.errors:
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'اطلاعات تولید: {field}: {error}')
            if not bom_formset.is_valid():
                for form in bom_formset:
                    if form.errors:
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'ماده اولیه: {field}: {error}')
    else:
        # تولید شناسه‌های پیشنهادی
        suggested_product_code = generate_suggested_product_code()
        suggested_formula_id = generate_suggested_formula_id()
        
        # ایجاد فرم خالی با شناسه پیشنهادی
        product_form = CreateProductForm(
            user=request.user,
            accessible_fields=accessible_fields,
            initial={'code': suggested_product_code}
        )
        
        # ایجاد formset خالی با شناسه فرمول پیشنهادی
        production_info_formset = ProductionInfoFormSet(
            prefix='production_info',
            initial=[{'formula_id': suggested_formula_id}]
        )
        bom_formset = BOMFormSet(prefix='bom')
    
    context = {
        'product_form': product_form,
        'production_info_formset': production_info_formset,
        'bom_formset': bom_formset,
        'accessible_fields': accessible_fields,
        'page_title': 'ایجاد محصول جدید',
        'submit_button_text': 'ثبت محصول',
    }
    
    return render(request, 'product/create_product.html', context)


@login_required
def product_list_view(request):
    """
    ویو لیست محصولات با قابلیت جستجو و فیلتر
    - بررسی دسترسی با TaskPermission
    - استفاده از django-tables2 برای نمایش جدول
    """
    audit_logger.info(f"درخواست مشاهده لیست محصولات توسط کاربر {request.user.username}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_PRODUCT_LIST.value):
        audit_logger.activity("تلاش برای مشاهده لیست محصولات بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست محصولات ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    application_filter = request.GET.get('application', '')
    custom_filter = request.GET.get('is_custom', '')
    
    # شروع با تمام محصولات
    products = Product.objects.all()
    
    # اعمال جستجو
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(category__icontains=search_query) |
            Q(subcategory__icontains=search_query) |
            Q(grade__icontains=search_query)
        )
    
    # اعمال فیلتر گروه
    if category_filter:
        products = products.filter(category=category_filter)
    
    # اعمال فیلتر کاربرد
    if application_filter:
        products = products.filter(main_application=application_filter)
    
    # اعمال فیلتر محصول سفارشی
    if custom_filter:
        is_custom = custom_filter.lower() == 'true'
        products = products.filter(is_custom=is_custom)
    
    # مرتب‌سازی
    products = products.order_by('-created_at')
    
    # دریافت لیست دسته‌بندی‌ها برای فیلتر
    categories = Product.objects.values_list(
        'category', flat=True
    ).distinct()
    
    # دریافت فیلدهای قابل دسترسی برای کاربر
    accessible_fields = get_accessible_product_fields_for_view(request.user)
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    table = ProductTable(products, user=request.user, accessible_fields=accessible_fields)
    
    # RequestConfig به صورت خودکار پارامترهای query string را حفظ می‌کند
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    bug_logger.debug(f"تعداد {products.count()} محصول برای نمایش لود شد")
    
    context = {
        'table': table,
        'search_query': search_query,
        'categories': categories,
        'category_filter': category_filter,
        'application_filter': application_filter,
        'custom_filter': custom_filter,
        'accessible_fields': accessible_fields,
        'page_title': 'لیست محصولات',
    }
    
    return render(request, 'product/product_list.html', context)


@login_required
def product_detail_view(request, product_id):
    """
    ویو نمایش جزئیات محصول
    - بررسی دسترسی با TaskPermission
    """
    audit_logger.info(f"درخواست مشاهده جزئیات محصول {product_id} توسط کاربر {request.user.username}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_PRODUCT_DETAIL.value):
        audit_logger.activity(f"تلاش برای مشاهده جزئیات محصول {product_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده جزئیات محصول ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    product = get_object_or_404(
        Product,
        id=product_id
    )
    
    bug_logger.debug(f"نمایش جزئیات محصول {product.code}")
    
    # دریافت اطلاعات مرتبط
    production_infos = ProductionInfo.objects.filter(product=product).prefetch_related('bom_items')
    
    # دریافت BOM های مرتبط
    boms = BOM.objects.filter(production_info__product=product).select_related('production_info')
    
    # دریافت فیلدهای قابل دسترسی برای کاربر
    accessible_fields = get_accessible_product_fields_for_view(request.user)
    
    context = {
        'product': product,
        'production_infos': production_infos,
        'boms': boms,
        'accessible_fields': accessible_fields,
        'page_title': f'جزئیات محصول: {product.name}',
    }
    
    return render(request, 'product/product_detail.html', context)


@login_required
def edit_product_view(request, product_id):
    """
    ویو ویرایش محصول با formset
    - بررسی دسترسی با TaskPermission
    - بررسی دسترسی فیلدها با FieldAccessRule
    """
    audit_logger.info(f"درخواست ویرایش محصول {product_id} توسط کاربر {request.user.username}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_EDIT_PRODUCT.value):
        audit_logger.activity(f"تلاش برای ویرایش محصول {product_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به ویرایش محصول ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    product = get_object_or_404(Product, id=product_id)
    
    # دریافت فیلدهای قابل دسترسی برای کاربر
    accessible_fields = get_accessible_product_fields(request.user)
    
    if request.method == 'POST':
        product_form = CreateProductForm(
            request.POST,
            request.FILES,
            instance=product,
            user=request.user,
            accessible_fields=accessible_fields
        )
        
        # دریافت ProductionInfo های موجود
        production_infos = ProductionInfo.objects.filter(product=product).prefetch_related('bom_items')
        
        # ایجاد modelformset با داده‌های موجود
        production_info_formset = ProductionInfoModelFormSet(
            request.POST,
            prefix='production_info',
            queryset=production_infos
        )
        
        # دریافت همه BOM های موجود (از همه ProductionInfo های این محصول)
        boms = BOM.objects.filter(production_info__product=product).select_related('production_info')
        
        # ایجاد modelformset با داده‌های موجود
        bom_formset = BOMModelFormSet(
            request.POST,
            prefix='bom',
            queryset=boms
        )
        
        if product_form.is_valid() and production_info_formset.is_valid() and bom_formset.is_valid():
            try:
                # بررسی اینکه حداقل یک ProductionInfo و BOM وجود دارد
                production_info_count = 0
                for production_info_form in production_info_formset:
                    if production_info_form.cleaned_data and not production_info_form.cleaned_data.get('DELETE', False):
                        if all([
                            production_info_form.cleaned_data.get('formula_id'),
                            production_info_form.cleaned_data.get('min_batch_production') is not None,
                            production_info_form.cleaned_data.get('specific_production_instruction'),
                        ]):
                            production_info_count += 1
                
                bom_count = 0
                for bom_form in bom_formset:
                    if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                        if all([
                            bom_form.cleaned_data.get('raw_material'),
                            bom_form.cleaned_data.get('quantity') is not None,
                        ]):
                            bom_count += 1
                
                if production_info_count == 0:
                    messages.error(request, 'حداقل یک اطلاعات تولید کامل (شامل شناسه فرمول، حداقل بچ تولید و دستور العمل) الزامی است.')
                elif bom_count == 0:
                    messages.error(request, 'حداقل یک ماده اولیه کامل (شامل نام ماده اولیه و مقدار به کیلوگرم) در BOM الزامی است.')
                else:
                    with transaction.atomic():
                        # ذخیره تغییرات محصول
                        product = product_form.save()
                        
                        # ذخیره ProductionInfo ها
                        production_infos_saved = []
                        for production_info_form in production_info_formset:
                            if production_info_form.cleaned_data and not production_info_form.cleaned_data.get('DELETE', False):
                                if all([
                                    production_info_form.cleaned_data.get('formula_id'),
                                    production_info_form.cleaned_data.get('min_batch_production') is not None,
                                    production_info_form.cleaned_data.get('specific_production_instruction'),
                                ]):
                                    # اگر instance وجود دارد (ویرایش)، بروزرسانی می‌کنیم
                                    if production_info_form.instance and production_info_form.instance.pk:
                                        production_info = production_info_form.save(commit=False)
                                        production_info.product = product
                                        production_info.save()
                                    else:
                                        # اگر instance وجود ندارد (جدید)، ایجاد می‌کنیم
                                        production_info = production_info_form.save(commit=False)
                                        production_info.product = product
                                        production_info.save()
                                    production_infos_saved.append(production_info)
                        
                        # حذف ProductionInfo های حذف شده (که DELETE=True هستند)
                        for production_info_form in production_info_formset:
                            if production_info_form.cleaned_data and production_info_form.cleaned_data.get('DELETE', False):
                                if production_info_form.instance and production_info_form.instance.pk:
                                    production_info_form.instance.delete()
                        
                        # ذخیره BOM ها - حفظ لینک به ProductionInfo مربوطه
                        if production_infos_saved:
                            for bom_form in bom_formset:
                                if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                                    if all([
                                        bom_form.cleaned_data.get('raw_material'),
                                        bom_form.cleaned_data.get('quantity') is not None,
                                    ]):
                                        bom = bom_form.save(commit=False)
                                        
                                        # اگر instance وجود دارد (ویرایش)، ProductionInfo موجود را حفظ می‌کنیم
                                        if bom_form.instance and bom_form.instance.pk:
                                            # ProductionInfo موجود را از instance حفظ می‌کنیم
                                            # اگر ProductionInfo حذف شده باشد، به اولین ProductionInfo لینک می‌کنیم
                                            original_production_info = bom_form.instance.production_info
                                            if original_production_info and original_production_info.product == product:
                                                # بررسی اینکه آیا این ProductionInfo هنوز وجود دارد
                                                if original_production_info in production_infos_saved:
                                                    bom.production_info = original_production_info
                                                else:
                                                    # ProductionInfo حذف شده، به اولین ProductionInfo لینک می‌کنیم
                                                    bom.production_info = production_infos_saved[0]
                                            else:
                                                # ProductionInfo موجود معتبر نیست، به اولین ProductionInfo لینک می‌کنیم
                                                bom.production_info = production_infos_saved[0]
                                        else:
                                            # اگر instance وجود ندارد (جدید)، به اولین ProductionInfo لینک می‌کنیم
                                            bom.production_info = production_infos_saved[0]
                                        
                                        bom.save()
                        
                        # حذف BOM های حذف شده (که DELETE=True هستند)
                        for bom_form in bom_formset:
                            if bom_form.cleaned_data and bom_form.cleaned_data.get('DELETE', False):
                                if bom_form.instance and bom_form.instance.pk:
                                    bom_form.instance.delete()
                        
                        audit_logger.info(f"محصول {product.code} توسط کاربر {request.user.username} ویرایش شد")
                        messages.success(
                            request,
                            f'محصول "{product.name}" با موفقیت ویرایش شد.'
                        )
                        
                        return redirect('sales:product_detail', product_id=product.id)
                    
            except Exception as e:
                bug_logger.error(f"خطا در ویرایش محصول {product_id}: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    f'خطا در ویرایش محصول: {str(e)}'
                )
        else:
            # نمایش خطاهای فرم
            bug_logger.warning(f"فرم ویرایش محصول {product_id} معتبر نیست")
            if not product_form.is_valid():
                for field, errors in product_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if not production_info_formset.is_valid():
                for form in production_info_formset:
                    if form.errors:
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'اطلاعات تولید: {field}: {error}')
            if not bom_formset.is_valid():
                for form in bom_formset:
                    if form.errors:
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'ماده اولیه: {field}: {error}')
    else:
        # ایجاد فرم با داده‌های موجود
        product_form = CreateProductForm(
            instance=product,
            user=request.user,
            accessible_fields=accessible_fields
        )
        
        # دریافت ProductionInfo های موجود
        production_infos = ProductionInfo.objects.filter(product=product).prefetch_related('bom_items')
        
        # ایجاد modelformset با داده‌های موجود
        production_info_formset = ProductionInfoModelFormSet(
            prefix='production_info',
            queryset=production_infos
        )
        
        # دریافت همه BOM های موجود (از همه ProductionInfo های این محصول)
        boms = BOM.objects.filter(production_info__product=product).select_related('production_info')
        
        # ایجاد modelformset با داده‌های موجود
        bom_formset = BOMModelFormSet(
            prefix='bom',
            queryset=boms
        )
    
    context = {
        'product_form': product_form,
        'production_info_formset': production_info_formset,
        'bom_formset': bom_formset,
        'product': product,
        'accessible_fields': accessible_fields,
        'page_title': f'ویرایش محصول: {product.name}',
        'submit_button_text': 'ذخیره تغییرات',
    }
    
    return render(request, 'product/edit_product.html', context)


@login_required
def delete_product_view(request, product_id):
    """
    ویو حذف محصول
    - بررسی دسترسی با TaskPermission
    """
    audit_logger.info(f"درخواست حذف محصول {product_id} توسط کاربر {request.user.username}")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_DELETE_PRODUCT.value):
        audit_logger.activity(f"تلاش برای حذف محصول {product_id} بدون دسترسی")
        messages.error(request, 'شما دسترسی به حذف محصول ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        try:
            product_name = product.name
            product_code = product.code
            product.delete()
            
            audit_logger.info(f"محصول {product_code} توسط کاربر {request.user.username} حذف شد")
            messages.success(
                request,
                f'محصول "{product_name}" با موفقیت حذف شد.'
            )
            
            return redirect('sales:product_list')
            
        except Exception as e:
            bug_logger.error(f"خطا در حذف محصول {product_id}: {str(e)}", exc_info=True)
            messages.error(
                request,
                f'خطا در حذف محصول: {str(e)}'
            )
            return redirect('sales:product_detail', product_id=product_id)
    else:
        bug_logger.debug(f"نمایش صفحه تأیید حذف محصول {product.code}")
    
    context = {
        'product': product,
        'page_title': f'حذف محصول: {product.name}',
    }
    
    return render(request, 'product/delete_product_confirm.html', context)


@login_required
def generate_product_code_ajax(request):
    """
    تولید شناسه محصول جدید به صورت AJAX
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            suggested_code = generate_suggested_product_code()
            return JsonResponse({'success': True, 'code': suggested_code})
        except Exception as e:
            bug_logger.error(f"خطا در تولید شناسه محصول: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': 'خطا در تولید شناسه محصول'}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def generate_formula_id_ajax(request):
    """
    تولید شناسه فرمول جدید به صورت AJAX
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            suggested_formula_id = generate_suggested_formula_id()
            return JsonResponse({'success': True, 'formula_id': suggested_formula_id})
        except Exception as e:
            bug_logger.error(f"خطا در تولید شناسه فرمول: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': 'خطا در تولید شناسه فرمول'}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def product_search_ajax(request):
    """
    جستجوی AJAX برای محصولات
    - بررسی دسترسی با TaskPermission (نیاز به دسترسی مشاهده لیست)
    """
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_VIEW_PRODUCT_LIST.value):
        audit_logger.activity("تلاش برای جستجوی AJAX محصولات بدون دسترسی")
        return JsonResponse({'error': 'شما دسترسی به جستجوی محصولات ندارید.'}, status=403)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('q', '')
        bug_logger.debug(f"جستجوی AJAX محصولات با عبارت: {search_query}")
        
        products = Product.objects.filter(
            Q(name__icontains=search_query) |
            Q(code__icontains=search_query)
        )[:10]
        
        results = [
            {
                'id': product.id,
                'code': product.code,
                'name': product.name,
                'category': product.category,
                'main_unit': product.main_unit,
            }
            for product in products
        ]
        
        return JsonResponse({'results': results})
    
    audit_logger.alert("درخواست AJAX محصولات بدون هدر X-Requested-With")
    return JsonResponse({'error': 'Invalid request'}, status=400)


def get_accessible_product_fields_for_view(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش محصول
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    
    # فیلدهایی که باید در لیست/جزئیات نمایش داده شوند
    display_fields = {
        'code': 'code',
        'name': 'name',
        'category': 'category',
        'subcategory': 'subcategory',
        'grade': 'grade',
        'physical_shape': 'physical_shape',
        'main_application': 'main_application',
        'is_custom': 'is_custom',
        'full_description': 'full_description',
        'main_unit': 'main_unit',
        'secondary_unit': 'secondary_unit',
        'conversion_coefficient': 'conversion_coefficient',
        'expiration_date': 'expiration_date',
        'pellet_granule_diameter': 'pellet_granule_diameter',
        'image': 'image',
        'lab_analysis': 'lab_analysis',
        'invoice_description': 'invoice_description',
    }
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {field: True for field in display_fields.keys()}

    accessible_fields = {}
    for display_name, model_field_name in display_fields.items():
        accessible_fields[display_name] = check_field_access_prefer_edit(
            user,
            Product,
            model_field_name,
        )

    return accessible_fields
