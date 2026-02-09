from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q
from decimal import Decimal
import logging
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.RBACModel import user_has_task, TaskChoices
from sales.forms.product_create_form import (
    CreateProductForm,
    ProductionInfoFormSet,
    ProductionInfoModelFormSet,
    BOMModelFormSet,
    get_accessible_product_fields,
)
from core.helpers import check_field_access_prefer_edit
from sales.tables.tables import ProductTable

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
        
        if product_form.is_valid() and production_info_formset.is_valid():
            try:
                # Parse کردن داده‌های BOM برای هر ProductionInfo
                production_info_total_forms = int(request.POST.get('production_info-TOTAL_FORMS', 0))
                production_bom_data = {}  # {production_index: [(raw_material_id, quantity), ...]}
                
                for prod_idx in range(production_info_total_forms):
                    # بررسی اینکه آیا این ProductionInfo حذف شده یا نه
                    is_deleted = request.POST.get(f'production_info-{prod_idx}-DELETE', 'off') == 'on'
                    if is_deleted:
                        continue
                    
                    # دریافت تعداد BOM های این ProductionInfo
                    bom_total_forms = int(request.POST.get(f'bom_{prod_idx}_TOTAL_FORMS', 0))
                    bom_items = []
                    
                    for bom_idx in range(bom_total_forms):
                        # بررسی اینکه آیا این BOM حذف شده یا نه
                        bom_is_deleted = request.POST.get(f'bom_{prod_idx}_{bom_idx}_DELETE', 'off') == 'on'
                        if bom_is_deleted:
                            continue
                        
                        raw_material_id = request.POST.get(f'bom_{prod_idx}_{bom_idx}_raw_material', '')
                        percentage = request.POST.get(f'bom_{prod_idx}_{bom_idx}_percentage', '')
                        
                        if raw_material_id and percentage:
                            try:
                                from decimal import Decimal
                                bom_items.append((int(raw_material_id), Decimal(percentage)))
                            except (ValueError, TypeError):
                                pass
                    
                    production_bom_data[prod_idx] = bom_items
                
                # بررسی اینکه حداقل یک ProductionInfo و BOM وجود دارد
                valid_production_count = 0
                total_bom_count = 0
                
                for prod_idx, bom_items in production_bom_data.items():
                    if len(bom_items) > 0:
                        valid_production_count += 1
                        total_bom_count += len(bom_items)
                
                if valid_production_count == 0:
                    messages.error(request, 'حداقل یک فرمول تولید با مواد اولیه (BOM) الزامی است.')
                elif total_bom_count == 0:
                    messages.error(request, 'حداقل یک ماده اولیه در BOM الزامی است.')
                else:
                    # بررسی تکراری نبودن مواد اولیه در هر فرمول
                    has_error = False
                    for prod_idx, bom_items in production_bom_data.items():
                        raw_material_ids = [item[0] for item in bom_items]
                        if len(raw_material_ids) != len(set(raw_material_ids)):
                            # پیدا کردن ماده اولیه تکراری
                            seen = set()
                            for rm_id in raw_material_ids:
                                if rm_id in seen:
                                    try:
                                        rm = RawMaterial.objects.get(id=rm_id)
                                        messages.error(request, f'ماده اولیه "{rm.name}" در فرمول #{prod_idx + 1} تکراری است.')
                                        has_error = True
                                        break
                                    except RawMaterial.DoesNotExist:
                                        pass
                                seen.add(rm_id)
                            if has_error:
                                break
                    
                    if not has_error:
                        with transaction.atomic():
                            # ذخیره محصول اصلی
                            product = product_form.save()
                            
                            # ذخیره اطلاعات تولید و BOM های مربوطه
                            for prod_idx, production_info_form in enumerate(production_info_formset):
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
                                        
                                        # ذخیره BOM های مربوط به این ProductionInfo
                                        if prod_idx in production_bom_data:
                                            # بررسی اینکه مجموع درصدها برابر 100 باشد
                                            total_percentage = sum(percentage for _, percentage in production_bom_data[prod_idx])
                                            if abs(total_percentage - Decimal('100')) > Decimal('0.001'):
                                                messages.error(request, f'مجموع درصدهای مواد اولیه در فرمول #{prod_idx + 1} باید برابر 100% باشد. مجموع فعلی: {total_percentage:.3f}%')
                                                raise ValueError(f"مجموع درصدها برابر 100 نیست: {total_percentage}")
                                            
                                            for raw_material_id, percentage in production_bom_data[prod_idx]:
                                                try:
                                                    raw_material = RawMaterial.objects.get(id=raw_material_id)
                                                    BOM.objects.create(
                                                        production_info=production_info,
                                                        raw_material=raw_material,
                                                        percentage=percentage
                                                    )
                                                except RawMaterial.DoesNotExist:
                                                    bug_logger.warning(f"ماده اولیه با ID {raw_material_id} یافت نشد")
                            
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
    
    context = {
        'product_form': product_form,
        'production_info_formset': production_info_formset,
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
    
    # دریافت لیست دسته‌بندی‌ها برای فیلتر (بدون مقادیر خالی و تکراری)
    categories = Product.objects.exclude(
        category__isnull=True
    ).exclude(
        category=''
    ).values_list(
        'category', flat=True
    ).distinct().order_by('category')
    
    # دریافت لیست کاربردهای محصول از CHOICES
    applications = Product.PRODUCT_APPLICATION_CHOICES
    
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
        'applications': applications,
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
        
        # بررسی اعتبار فرم‌ها
        product_valid = product_form.is_valid()
        production_info_valid = production_info_formset.is_valid()
        bom_valid = bom_formset.is_valid()
        
        # لاگ تعداد فرم‌ها
        bug_logger.info(f"تعداد BOM forms: {len(bom_formset)}")
        bug_logger.info(f"BOM TOTAL_FORMS: {request.POST.get('bom-TOTAL_FORMS')}")
        bug_logger.info(f"BOM INITIAL_FORMS: {request.POST.get('bom-INITIAL_FORMS')}")
        for idx, bom_form in enumerate(bom_formset):
            has_cleaned = bool(bom_form.cleaned_data)
            raw_material_in_post = request.POST.get(f'bom-{idx}-raw_material')
            percentage_in_post = request.POST.get(f'bom-{idx}-percentage')
            bug_logger.info(f"BOM[{idx}]: has_cleaned={has_cleaned}, raw_material={raw_material_in_post}, percentage={percentage_in_post}")
        
        bug_logger.info(f"اعتبار فرم‌ها - product: {product_valid}, production_info: {production_info_valid}, bom: {bom_valid}")
        
        if product_valid and production_info_valid and bom_valid:
            try:
                # بررسی اینکه حداقل یک ProductionInfo و BOM وجود دارد
                # فقط فرم‌های غیرحذف‌شده را بررسی می‌کنیم
                production_info_count = 0
                for production_info_form in production_info_formset:
                    # بررسی اینکه آیا فرم حذف شده است یا نه
                    is_deleted = False
                    if production_info_form.cleaned_data:
                        is_deleted = production_info_form.cleaned_data.get('DELETE', False)
                    elif production_info_form.data:
                        # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                        delete_key = None
                        for key in production_info_form.data.keys():
                            if key.endswith('-DELETE'):
                                delete_key = key
                                break
                        if delete_key and production_info_form.data.get(delete_key):
                            is_deleted = True
                    
                    if not is_deleted and production_info_form.cleaned_data:
                        if all([
                            production_info_form.cleaned_data.get('formula_id'),
                            production_info_form.cleaned_data.get('min_batch_production') is not None,
                            production_info_form.cleaned_data.get('specific_production_instruction'),
                        ]):
                            production_info_count += 1
                
                bom_count = 0
                raw_materials_list = []
                has_duplicate = False
                duplicate_material = None
                
                # گروه‌بندی BOM ها بر اساس ProductionInfo برای بررسی مجموع درصدها
                # فقط BOM های غیرحذف‌شده را بررسی می‌کنیم
                bom_by_production_info = {}
                for bom_idx, bom_form in enumerate(bom_formset):
                    # بررسی اینکه آیا فرم حذف شده است یا نه
                    is_deleted = False
                    if bom_form.cleaned_data:
                        is_deleted = bom_form.cleaned_data.get('DELETE', False)
                    elif bom_form.data:
                        # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                        delete_key = None
                        for key in bom_form.data.keys():
                            if key.endswith('-DELETE'):
                                delete_key = key
                                break
                        if delete_key and bom_form.data.get(delete_key):
                            is_deleted = True
                    
                    if not is_deleted:
                        # بررسی اینکه آیا داده‌های لازم وجود دارد
                        raw_material = None
                        percentage = None
                        
                        if bom_form.cleaned_data:
                            raw_material = bom_form.cleaned_data.get('raw_material')
                            percentage = bom_form.cleaned_data.get('percentage')
                        elif bom_form.data:
                            # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                            raw_material_id = bom_form.data.get(f'bom-{bom_idx}-raw_material')
                            percentage_str = bom_form.data.get(f'bom-{bom_idx}-percentage')
                            
                            if raw_material_id:
                                try:
                                    raw_material = RawMaterial.objects.get(id=raw_material_id)
                                except (RawMaterial.DoesNotExist, ValueError, TypeError):
                                    pass
                            
                            if percentage_str:
                                try:
                                    percentage = Decimal(str(percentage_str))
                                except (ValueError, TypeError):
                                    pass
                        
                        if raw_material and percentage is not None:
                            # بررسی تکراری نبودن ماده اولیه
                            if raw_material in raw_materials_list:
                                has_duplicate = True
                                duplicate_material = raw_material
                                break
                            raw_materials_list.append(raw_material)
                            bom_count += 1
                            
                            # گروه‌بندی بر اساس ProductionInfo
                            production_info_id = None
                            if bom_form.instance and bom_form.instance.pk:
                                production_info_id = bom_form.instance.production_info_id
                            else:
                                # برای BOM جدید، باید از فیلد مخفی production_info_id استفاده کنیم
                                # جستجوی فیلد مخفی production_info_id در POST
                                for key in request.POST.keys():
                                    if key.startswith('bom_') and key.endswith('_production_info_id'):
                                        # استخراج prod_idx و bom_idx
                                        parts = key.replace('bom_', '').replace('_production_info_id', '').split('_')
                                        if len(parts) == 2:
                                            try:
                                                prod_idx = int(parts[0])
                                                bom_idx_from_key = int(parts[1])
                                                if bom_idx_from_key == bom_idx:
                                                    prod_info_id_str = request.POST.get(key)
                                                    if prod_info_id_str and prod_info_id_str != 'new':
                                                        try:
                                                            production_info_id = int(prod_info_id_str)
                                                            break
                                                        except (ValueError, TypeError):
                                                            pass
                                                    elif prod_info_id_str == 'new':
                                                        # ProductionInfo جدید است - باید از index استفاده کنیم
                                                        production_info_id = 'new'
                                                        break
                                            except (ValueError, TypeError):
                                                pass
                                
                                # اگر پیدا نشد، از اولین ProductionInfo استفاده می‌کنیم
                                if not production_info_id:
                                    production_info_id = 'new'
                            
                            if production_info_id not in bom_by_production_info:
                                bom_by_production_info[production_info_id] = []
                            bom_by_production_info[production_info_id].append(percentage)
                
                # بررسی مجموع درصدها برای هر ProductionInfo
                percentage_sum_error = False
                for prod_info_id, percentages in bom_by_production_info.items():
                    total_percentage = sum(Decimal(str(p)) for p in percentages)
                    if abs(total_percentage - Decimal('100')) > Decimal('0.001'):  # استفاده از tolerance برای مقایسه اعشاری
                        percentage_sum_error = True
                        messages.error(request, f'مجموع درصدهای مواد اولیه باید برابر 100% باشد. مجموع فعلی: {total_percentage:.3f}%')
                        break
                
                bug_logger.info(f"تعداد ProductionInfo: {production_info_count}, تعداد BOM: {bom_count}, duplicate: {has_duplicate}, percentage_error: {percentage_sum_error}")
                
                if production_info_count == 0:
                    messages.error(request, 'حداقل یک اطلاعات تولید کامل (شامل شناسه فرمول، حداقل بچ تولید و دستور العمل) الزامی است.')
                    bug_logger.warning("تعداد ProductionInfo صفر است")
                    # اگر validation fail شد، باید از transaction خارج شویم
                    raise ValueError("تعداد ProductionInfo صفر است")
                elif has_duplicate:
                    messages.error(request, f'ماده اولیه "{duplicate_material.name}" تکراری است. هر ماده اولیه فقط یک بار قابل تعریف است.')
                    bug_logger.warning(f"ماده اولیه تکراری: {duplicate_material.name}")
                    raise ValueError(f"ماده اولیه تکراری: {duplicate_material.name}")
                elif bom_count == 0:
                    messages.error(request, 'حداقل یک ماده اولیه کامل (شامل نام ماده اولیه و درصد) در BOM الزامی است.')
                    bug_logger.warning("تعداد BOM صفر است")
                    raise ValueError("تعداد BOM صفر است")
                elif percentage_sum_error:
                    # پیام خطا قبلاً اضافه شده است
                    bug_logger.warning("خطا در مجموع درصدها")
                    raise ValueError("خطا در مجموع درصدها")
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
                            # بررسی DELETE از cleaned_data یا data
                            is_deleted = False
                            if production_info_form.cleaned_data:
                                is_deleted = production_info_form.cleaned_data.get('DELETE', False)
                            elif production_info_form.data:
                                # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                                for key in production_info_form.data.keys():
                                    if key.endswith('-DELETE') and production_info_form.data.get(key):
                                        is_deleted = True
                                        break
                            
                            if is_deleted:
                                if production_info_form.instance and production_info_form.instance.pk:
                                    production_info_form.instance.delete()
                        
                        # ذخیره BOM ها - حفظ لینک به ProductionInfo مربوطه
                        
                        # ایجاد mapping از production_info_id به ProductionInfo object
                        production_info_map = {pi.id: pi for pi in production_infos_saved}
                        
                        # گروه‌بندی BOM forms بر اساس ProductionInfo
                        # استفاده از فیلد مخفی production_info_id از POST
                        bom_forms_by_production_info = {}
                        for bom_form in bom_formset:
                            # بررسی اینکه آیا این فرم داده دارد یا نه
                            has_data = False
                            bom_idx = None
                            
                            # پیدا کردن bom_idx از prefix فرم (مثلاً bom-0)
                            if hasattr(bom_form, 'prefix') and bom_form.prefix:
                                prefix = bom_form.prefix
                                if prefix.startswith('bom-'):
                                    try:
                                        bom_idx = int(prefix.split('-')[1])
                                    except (ValueError, IndexError):
                                        pass
                            
                            # اگر bom_idx پیدا نشد، از data استفاده می‌کنیم
                            if bom_idx is None and bom_form.data:
                                for key in bom_form.data.keys():
                                    if 'raw_material' in key:
                                        # استخراج index از نام فیلد
                                        # فرمت: bom-{idx}-raw_material
                                        parts = key.split('-')
                                        if len(parts) >= 2 and parts[0] == 'bom':
                                            try:
                                                bom_idx = int(parts[1])
                                                break
                                            except (ValueError, IndexError):
                                                pass
                            
                            # بررسی اینکه آیا این فرم داده دارد یا نه
                            if bom_form.cleaned_data:
                                has_data = any([
                                    bom_form.cleaned_data.get('raw_material'),
                                    bom_form.cleaned_data.get('percentage') is not None,
                                ])
                            elif bom_form.data and bom_idx is not None:
                                # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                                has_data = any([
                                    bom_form.data.get(f'bom-{bom_idx}-raw_material'),
                                    bom_form.data.get(f'bom-{bom_idx}-percentage'),
                                ])
                            
                            if has_data or (bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False)):
                                production_info_id = None
                                
                                # ابتدا از instance استفاده می‌کنیم (برای BOM های موجود)
                                if bom_form.instance and bom_form.instance.pk:
                                    production_info_id = bom_form.instance.production_info_id
                                    bug_logger.debug(f"BOM[{bom_idx}] موجود - production_info_id: {production_info_id}")
                                
                                # اگر production_info_id پیدا نشد، از POST استفاده می‌کنیم
                                if not production_info_id and bom_idx is not None:
                                    # جستجوی فیلد مخفی production_info_id در POST
                                    # فرمت: bom_{prod_idx}_{bom_idx}_production_info_id
                                    for key in request.POST.keys():
                                        if key.startswith('bom_') and key.endswith('_production_info_id'):
                                            # استخراج prod_idx و bom_idx
                                            parts = key.replace('bom_', '').replace('_production_info_id', '').split('_')
                                            if len(parts) == 2:
                                                try:
                                                    prod_idx = int(parts[0])
                                                    bom_idx_from_key = int(parts[1])
                                                    if bom_idx_from_key == bom_idx:
                                                        prod_info_id_str = request.POST.get(key)
                                                        bug_logger.debug(f"BOM[{bom_idx}] - پیدا شد key: {key}, value: {prod_info_id_str}")
                                                        if prod_info_id_str and prod_info_id_str != 'new':
                                                            try:
                                                                production_info_id = int(prod_info_id_str)
                                                                bug_logger.debug(f"BOM[{bom_idx}] - production_info_id از POST: {production_info_id}")
                                                                break
                                                            except (ValueError, TypeError):
                                                                pass
                                                        elif prod_info_id_str == 'new':
                                                            # ProductionInfo جدید است - باید از index استفاده کنیم
                                                            if prod_idx < len(production_infos_saved):
                                                                production_info_id = production_infos_saved[prod_idx].id
                                                                bug_logger.debug(f"BOM[{bom_idx}] - production_info_id از ProductionInfo جدید: {production_info_id}")
                                                                break
                                                except (ValueError, TypeError):
                                                    pass
                                
                                # اگر production_info_id پیدا نشد و ProductionInfo جدید است، از index استفاده می‌کنیم
                                if not production_info_id and bom_idx is not None:
                                    # پیدا کردن ProductionInfo مربوطه بر اساس index
                                    for prod_idx, production_info_form in enumerate(production_info_formset):
                                        if production_info_form.cleaned_data and not production_info_form.cleaned_data.get('DELETE', False):
                                            # بررسی فیلد مخفی
                                            hidden_field_key = f'bom_{prod_idx}_{bom_idx}_production_info_id'
                                            if hidden_field_key in request.POST:
                                                prod_info_id_str = request.POST.get(hidden_field_key)
                                                if prod_info_id_str == 'new':
                                                    # این ProductionInfo جدید است
                                                    # بعد از ذخیره، production_info_id را پیدا می‌کنیم
                                                    if prod_idx < len(production_infos_saved):
                                                        production_info_id = production_infos_saved[prod_idx].id
                                                        bug_logger.debug(f"BOM[{bom_idx}] - production_info_id از ProductionInfo جدید (fallback): {production_info_id}")
                                                        break
                                
                                # اگر production_info_id در mapping وجود دارد، استفاده می‌کنیم
                                if production_info_id and production_info_id in production_info_map:
                                    if production_info_id not in bom_forms_by_production_info:
                                        bom_forms_by_production_info[production_info_id] = []
                                    bom_forms_by_production_info[production_info_id].append(bom_form)
                                    bug_logger.debug(f"BOM[{bom_idx}] - اضافه شد به production_info_id: {production_info_id}")
                                elif not production_info_id and production_infos_saved:
                                    # برای BOM های جدید که production_info_id ندارند، به اولین ProductionInfo لینک می‌کنیم
                                    first_prod_id = production_infos_saved[0].id
                                    if first_prod_id not in bom_forms_by_production_info:
                                        bom_forms_by_production_info[first_prod_id] = []
                                    bom_forms_by_production_info[first_prod_id].append(bom_form)
                                    bug_logger.debug(f"BOM[{bom_idx}] - اضافه شد به اولین ProductionInfo: {first_prod_id} (fallback)")
                                else:
                                    bug_logger.warning(f"BOM[{bom_idx}] - production_info_id پیدا نشد و ProductionInfo ذخیره شده‌ای وجود ندارد")
                        
                        # بررسی اعتبارسنجی و ذخیره BOM ها برای هر ProductionInfo
                        bom_validation_errors = []
                        for production_info in production_infos_saved:
                            bom_forms = bom_forms_by_production_info.get(production_info.id, [])
                            
                            # بررسی مجموع درصدها برای این ProductionInfo
                            total_percentage = Decimal('0')
                            valid_bom_count = 0
                            
                            for bom_form in bom_forms:
                                # بررسی DELETE
                                is_deleted = False
                                if bom_form.cleaned_data:
                                    is_deleted = bom_form.cleaned_data.get('DELETE', False)
                                elif bom_form.data:
                                    for key in bom_form.data.keys():
                                        if key.endswith('-DELETE') and bom_form.data.get(key):
                                            is_deleted = True
                                            break
                                
                                if not is_deleted:
                                    # بررسی اینکه آیا داده‌های لازم وجود دارد
                                    raw_material = None
                                    percentage = None
                                    
                                    if bom_form.cleaned_data:
                                        raw_material = bom_form.cleaned_data.get('raw_material')
                                        percentage = bom_form.cleaned_data.get('percentage')
                                    elif bom_form.data:
                                        # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                                        for key in bom_form.data.keys():
                                            if key.endswith('-raw_material'):
                                                raw_material_id = bom_form.data.get(key)
                                                if raw_material_id:
                                                    try:
                                                        raw_material = RawMaterial.objects.get(id=raw_material_id)
                                                    except (RawMaterial.DoesNotExist, ValueError, TypeError):
                                                        pass
                                            elif key.endswith('-percentage'):
                                                percentage_str = bom_form.data.get(key)
                                                if percentage_str:
                                                    try:
                                                        percentage = Decimal(str(percentage_str))
                                                    except (ValueError, TypeError):
                                                        pass
                                    
                                    if raw_material and percentage is not None:
                                        total_percentage += Decimal(str(percentage))
                                        valid_bom_count += 1
                            
                            # بررسی مجموع درصدها
                            if valid_bom_count > 0:
                                if abs(total_percentage - Decimal('100')) > Decimal('0.001'):
                                    bom_validation_errors.append(
                                        f'فرمول "{production_info.formula_id}": مجموع درصدهای مواد اولیه باید برابر 100% باشد. مجموع فعلی: {total_percentage:.3f}%'
                                    )
                            
                            # ذخیره BOM ها برای این ProductionInfo
                            for bom_form in bom_forms:
                                # بررسی DELETE
                                is_deleted = False
                                if bom_form.cleaned_data:
                                    is_deleted = bom_form.cleaned_data.get('DELETE', False)
                                elif bom_form.data:
                                    # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                                    for key in bom_form.data.keys():
                                        if key.endswith('-DELETE') and bom_form.data.get(key):
                                            is_deleted = True
                                            break
                                
                                if not is_deleted:
                                    # بررسی اینکه آیا داده‌های لازم وجود دارد
                                    raw_material = None
                                    percentage = None
                                    
                                    if bom_form.cleaned_data:
                                        raw_material = bom_form.cleaned_data.get('raw_material')
                                        percentage = bom_form.cleaned_data.get('percentage')
                                    elif bom_form.data:
                                        # اگر cleaned_data وجود ندارد، از data استفاده می‌کنیم
                                        for key in bom_form.data.keys():
                                            if key.endswith('-raw_material'):
                                                raw_material_id = bom_form.data.get(key)
                                                if raw_material_id:
                                                    try:
                                                        raw_material = RawMaterial.objects.get(id=raw_material_id)
                                                    except (RawMaterial.DoesNotExist, ValueError, TypeError):
                                                        pass
                                            elif key.endswith('-percentage'):
                                                percentage_str = bom_form.data.get(key)
                                                if percentage_str:
                                                    try:
                                                        percentage = Decimal(str(percentage_str))
                                                    except (ValueError, TypeError):
                                                        pass
                                    
                                    if raw_material and percentage is not None:
                                        if bom_form.instance and bom_form.instance.pk:
                                            # BOM موجود - بروزرسانی
                                            bom = bom_form.save(commit=False)
                                            bom.production_info = production_info
                                            bom.raw_material = raw_material
                                            bom.percentage = percentage
                                            bom.save()
                                        else:
                                            # BOM جدید - ایجاد
                                            bom = BOM(
                                                production_info=production_info,
                                                raw_material=raw_material,
                                                percentage=percentage
                                            )
                                            bom.save()
                                            bug_logger.debug(f"BOM جدید ایجاد شد: production_info_id={production_info.id}, raw_material_id={raw_material.id}, percentage={percentage}")
                                elif is_deleted:
                                    # حذف BOM
                                    if bom_form.instance and bom_form.instance.pk:
                                        bom_form.instance.delete()
                        
                        # اگر خطای اعتبارسنجی وجود داشت، نمایش می‌دهیم
                        if bom_validation_errors:
                            for error_msg in bom_validation_errors:
                                messages.error(request, error_msg)
                            # اگر خطا وجود داشت، از transaction خارج می‌شویم
                            raise ValueError("خطا در اعتبارسنجی BOM")
                        
                        # حذف BOM های حذف شده که دیگر به هیچ ProductionInfo تعلق ندارند
                        for bom in BOM.objects.filter(production_info__product=product):
                            if bom.production_info not in production_infos_saved:
                                bom.delete()
                        
                        # همچنین BOM های حذف شده از formset اصلی را حذف می‌کنیم
                        for bom_form in bom_formset:
                            if bom_form.cleaned_data and bom_form.cleaned_data.get('DELETE', False):
                                if bom_form.instance and bom_form.instance.pk:
                                    bom_form.instance.delete()
                        
                        # برای BOM های جدید که هنوز به هیچ ProductionInfo لینک نشده‌اند
                        # (این مورد باید از طریق template حل شود، اما برای اطمینان اینجا هم بررسی می‌کنیم)
                        for bom_form in bom_formset:
                            if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                                if all([
                                    bom_form.cleaned_data.get('raw_material'),
                                    bom_form.cleaned_data.get('percentage') is not None,
                                ]):
                                    # اگر instance وجود ندارد (جدید) و هنوز به ProductionInfo لینک نشده
                                    if not bom_form.instance.pk:
                                        # بررسی اینکه آیا این BOM در bom_forms_by_production_info وجود دارد
                                        found = False
                                        for prod_id, forms in bom_forms_by_production_info.items():
                                            if bom_form in forms:
                                                found = True
                                                break
                                        
                                        # اگر پیدا نشد، به اولین ProductionInfo لینک می‌کنیم
                                        if not found and production_infos_saved:
                                            bom = bom_form.save(commit=False)
                                            bom.production_info = production_infos_saved[0]
                                            bom.save()
                        
                        audit_logger.info(f"محصول {product.code} توسط کاربر {request.user.username} ویرایش شد")
                        messages.success(
                            request,
                            f'محصول "{product.name}" با موفقیت ویرایش شد.'
                        )
                        
                        return redirect('sales:product_detail', product_id=product.id)
                    
            except ValueError as e:
                # خطای اعتبارسنجی - transaction rollback می‌شود
                bug_logger.warning(f"خطا در اعتبارسنجی: {str(e)}")
                # پیام خطا قبلاً اضافه شده است
            except Exception as e:
                bug_logger.error(f"خطا در ویرایش محصول {product_id}: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    f'خطا در ویرایش محصول: {str(e)}'
                )
        else:
            # نمایش خطاهای فرم
            bug_logger.warning(f"فرم ویرایش محصول {product_id} معتبر نیست")
            if not product_valid:
                bug_logger.warning(f"خطاهای product_form: {product_form.errors}")
                for field, errors in product_form.errors.items():
                    for error in errors:
                        messages.error(request, f'محصول - {field}: {error}')
            if not production_info_valid:
                bug_logger.warning(f"خطاهای production_info_formset: {production_info_formset.errors}")
                bug_logger.warning(f"خطاهای production_info_formset (non_form_errors): {production_info_formset.non_form_errors()}")
                for form_idx, form in enumerate(production_info_formset):
                    if form.errors:
                        bug_logger.warning(f"خطاهای production_info_form[{form_idx}]: {form.errors}")
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'اطلاعات تولید [{form_idx}] - {field}: {error}')
            if not bom_valid:
                bug_logger.warning(f"خطاهای bom_formset: {bom_formset.errors}")
                bug_logger.warning(f"خطاهای bom_formset (non_form_errors): {bom_formset.non_form_errors()}")
                for form_idx, form in enumerate(bom_formset):
                    if form.errors:
                        bug_logger.warning(f"خطاهای bom_form[{form_idx}]: {form.errors}")
                        for field, errors in form.errors.items():
                            for error in errors:
                                messages.error(request, f'BOM [{form_idx}] - {field}: {error}')
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
        
        # ایجاد modelformset با داده‌های موجود (برای نمایش در template)
        bom_formset = BOMModelFormSet(
            prefix='bom',
            queryset=boms
        )
    
    # متصل کردن BOM ها به هر ProductionInfo برای نمایش در template
    for prod_form in production_info_formset:
        prod_form.bom_forms = []
        if prod_form.instance and prod_form.instance.pk:
            # برای ProductionInfo موجود، BOM های مربوطه را پیدا می‌کنیم
            for bom_form in bom_formset:
                if bom_form.instance and bom_form.instance.pk:
                    if bom_form.instance.production_info_id == prod_form.instance.id:
                        prod_form.bom_forms.append(bom_form)
        # برای ProductionInfo جدید، bom_forms خالی است
    
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


@login_required
def get_raw_materials_ajax(request):
    """
    API برای دریافت لیست مواد اولیه برای استفاده در BOM
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            raw_materials = RawMaterial.objects.all().values('id', 'name', 'primary_unit')
            raw_materials_list = [
                {
                    'id': rm['id'],
                    'name': rm['name'],
                    'unit': rm['primary_unit'] or 'کیلوگرم'
                }
                for rm in raw_materials
            ]
            return JsonResponse({'success': True, 'raw_materials': raw_materials_list})
        except Exception as e:
            bug_logger.error(f"خطا در دریافت لیست مواد اولیه: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    audit_logger.alert("درخواست AJAX مواد اولیه بدون هدر X-Requested-With")
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
