from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.ProductFolder.BOMModel import BOM
from sales.forms.create_product_form import (
    CreateProductForm, 
    ProductionInfoFormSet,
    BOMFormSet,
    get_accessible_product_fields
)


@login_required
def create_product_view(request):
    """
    ویو ایجاد محصول جدید با formset برای ProductionInfo و BOM
    """
    
    if request.method == 'POST':
        # ایجاد فرم با داده‌های ارسالی
        product_form = CreateProductForm(
            request.POST,
            request.FILES,
            user=request.user,
            accessible_fields=get_accessible_product_fields(
                request.user,
                CreateProductForm(user=request.user)
            )
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
                            production_info_form.cleaned_data.get('name'),
                            production_info_form.cleaned_data.get('min_batch_production') is not None,
                            production_info_form.cleaned_data.get('specific_production_instruction'),
                        ]):
                            production_info_count += 1
                
                bom_count = 0
                for bom_form in bom_formset:
                    if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                        # بررسی اینکه آیا همه فیلدهای اجباری پر شده‌اند
                        if all([
                            bom_form.cleaned_data.get('raw_material_id'),
                            bom_form.cleaned_data.get('raw_material'),
                            bom_form.cleaned_data.get('unit_used'),
                            bom_form.cleaned_data.get('quantity') is not None,
                        ]):
                            bom_count += 1
                
                if production_info_count == 0:
                    messages.error(request, 'حداقل یک اطلاعات تولید با تمام فیلدهای اجباری الزامی است.')
                elif bom_count == 0:
                    messages.error(request, 'حداقل یک ماده اولیه (BOM) با تمام فیلدهای اجباری الزامی است.')
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
                                    production_info_form.cleaned_data.get('name'),
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
                                        bom_form.cleaned_data.get('raw_material_id'),
                                        bom_form.cleaned_data.get('raw_material'),
                                        bom_form.cleaned_data.get('unit_used'),
                                        bom_form.cleaned_data.get('quantity') is not None,
                                    ]):
                                        bom = bom_form.save(commit=False)
                                        bom.production_info = first_production_info
                                        bom.save()
                        
                        messages.success(
                            request,
                            f'محصول "{product.name}" با کد "{product.code}" با موفقیت ایجاد شد.'
                        )
                        
                        return redirect('sales:product_list')
                    
            except Exception as e:
                import traceback
                messages.error(
                    request,
                    f'خطا در ایجاد محصول: {str(e)}'
                )
                print(traceback.format_exc())
        else:
            # نمایش خطاهای فرم
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
        # ایجاد فرم خالی
        product_form = CreateProductForm(
            user=request.user,
            accessible_fields=get_accessible_product_fields(
                request.user,
                CreateProductForm(user=request.user)
            )
        )
        
        # ایجاد formset خالی
        production_info_formset = ProductionInfoFormSet(prefix='production_info')
        bom_formset = BOMFormSet(prefix='bom')
    
    context = {
        'product_form': product_form,
        'production_info_formset': production_info_formset,
        'bom_formset': bom_formset,
        'page_title': 'ایجاد محصول جدید',
        'submit_button_text': 'ثبت محصول',
    }
    
    return render(request, 'sales/create_product.html', context)


@login_required
def product_list_view(request):
    """
    ویو لیست محصولات با قابلیت جستجو و فیلتر
    """
    
    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    application_filter = request.GET.get('application', '')
    custom_filter = request.GET.get('is_custom', '')
    
    # شروع با تمام محصولات
    products = Product.objects.all().select_related('physical_shape')
    
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
    
    # صفحه‌بندی
    paginator = Paginator(products, 20)  # 20 محصول در هر صفحه
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # دریافت لیست دسته‌بندی‌ها برای فیلتر
    categories = Product.objects.values_list(
        'category', flat=True
    ).distinct()
    
    context = {
        'page_obj': page_obj,
        'products': page_obj,
        'search_query': search_query,
        'categories': categories,
        'category_filter': category_filter,
        'application_filter': application_filter,
        'custom_filter': custom_filter,
        'page_title': 'لیست محصولات',
    }
    
    return render(request, 'sales/product_list.html', context)


@login_required
def product_detail_view(request, product_id):
    """
    ویو نمایش جزئیات محصول
    """
    
    product = get_object_or_404(
        Product.objects.select_related('physical_shape'),
        id=product_id
    )
    
    # دریافت اطلاعات مرتبط
    production_infos = ProductionInfo.objects.filter(product=product).prefetch_related('bom_items')
    
    # دریافت BOM های مرتبط
    boms = BOM.objects.filter(production_info__product=product).select_related('production_info')
    
    context = {
        'product': product,
        'production_infos': production_infos,
        'boms': boms,
        'page_title': f'جزئیات محصول: {product.name}',
    }
    
    return render(request, 'sales/product_detail.html', context)


@login_required
def edit_product_view(request, product_id):
    """
    ویو ویرایش محصول با formset
    """
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product_form = CreateProductForm(
            request.POST,
            request.FILES,
            instance=product,
            user=request.user,
            accessible_fields=get_accessible_product_fields(
                request.user,
                CreateProductForm(user=request.user)
            )
        )
        
        # دریافت ProductionInfo های موجود
        production_infos = ProductionInfo.objects.filter(product=product)
        
        # ایجاد formset با داده‌های موجود
        production_info_formset = ProductionInfoFormSet(
            request.POST,
            prefix='production_info',
            initial=[
                {
                    'formula_id': pi.formula_id,
                    'name': pi.name,
                    'min_batch_production': pi.min_batch_production,
                    'specific_production_instruction': pi.specific_production_instruction,
                }
                for pi in production_infos
            ]
        )
        
        # دریافت BOM های موجود
        boms = BOM.objects.filter(production_info__product=product)
        
        # ایجاد formset با داده‌های موجود
        bom_formset = BOMFormSet(
            request.POST,
            prefix='bom',
            initial=[
                {
                    'raw_material_id': bom.raw_material_id,
                    'raw_material': bom.raw_material,
                    'unit_used': bom.unit_used,
                    'quantity': bom.quantity,
                }
                for bom in boms
            ]
        )
        
        if product_form.is_valid() and production_info_formset.is_valid() and bom_formset.is_valid():
            try:
                with transaction.atomic():
                    # ذخیره تغییرات محصول
                    product = product_form.save()
                    
                    # حذف ProductionInfo های حذف شده
                    for production_info_form in production_info_formset:
                        if production_info_form.cleaned_data.get('DELETE', False):
                            if production_info_form.instance.pk:
                                production_info_form.instance.delete()
                    
                    # ذخیره یا بروزرسانی ProductionInfo
                    for production_info_form in production_info_formset:
                        if production_info_form.cleaned_data and not production_info_form.cleaned_data.get('DELETE', False):
                            production_info = production_info_form.save(commit=False)
                            production_info.product = product
                            production_info.save()
                    
                    # حذف BOM های حذف شده
                    for bom_form in bom_formset:
                        if bom_form.cleaned_data.get('DELETE', False):
                            if bom_form.instance.pk:
                                bom_form.instance.delete()
                    
                    # ذخیره یا بروزرسانی BOM
                    for bom_form in bom_formset:
                        if bom_form.cleaned_data and not bom_form.cleaned_data.get('DELETE', False):
                            bom = bom_form.save(commit=False)
                            # BOM باید به یک ProductionInfo لینک شود
                            # برای سادگی، به اولین ProductionInfo لینک می‌کنیم
                            if not bom.production_info_id:
                                first_production_info = ProductionInfo.objects.filter(product=product).first()
                                if first_production_info:
                                    bom.production_info = first_production_info
                            bom.save()
                    
                    messages.success(
                        request,
                        f'محصول "{product.name}" با موفقیت ویرایش شد.'
                    )
                    
                    return redirect('sales:product_detail', product_id=product.id)
                    
            except Exception as e:
                messages.error(
                    request,
                    f'خطا در ویرایش محصول: {str(e)}'
                )
        else:
            messages.error(
                request,
                'لطفاً خطاهای فرم را بررسی و اصلاح کنید.'
            )
    else:
        # ایجاد فرم با داده‌های موجود
        product_form = CreateProductForm(
            instance=product,
            user=request.user,
            accessible_fields=get_accessible_product_fields(
                request.user,
                CreateProductForm(user=request.user)
            )
        )
        
        # دریافت ProductionInfo های موجود
        production_infos = ProductionInfo.objects.filter(product=product)
        
        # ایجاد formset با داده‌های موجود
        production_info_formset = ProductionInfoFormSet(
            prefix='production_info',
            initial=[
                {
                    'formula_id': pi.formula_id,
                    'name': pi.name,
                    'min_batch_production': pi.min_batch_production,
                    'specific_production_instruction': pi.specific_production_instruction,
                }
                for pi in production_infos
            ]
        )
        
        # دریافت BOM های موجود
        boms = BOM.objects.filter(production_info__product=product)
        
        # ایجاد formset با داده‌های موجود
        bom_formset = BOMFormSet(
            prefix='bom',
            initial=[
                {
                    'raw_material_id': bom.raw_material_id,
                    'raw_material': bom.raw_material,
                    'unit_used': bom.unit_used,
                    'quantity': bom.quantity,
                }
                for bom in boms
            ]
        )
    
    context = {
        'product_form': product_form,
        'production_info_formset': production_info_formset,
        'bom_formset': bom_formset,
        'product': product,
        'page_title': f'ویرایش محصول: {product.name}',
        'submit_button_text': 'ذخیره تغییرات',
    }
    
    return render(request, 'sales/edit_product.html', context)


@login_required
def delete_product_view(request, product_id):
    """
    ویو حذف محصول
    """
    
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        try:
            product_name = product.name
            product.delete()
            
            messages.success(
                request,
                f'محصول "{product_name}" با موفقیت حذف شد.'
            )
            
            return redirect('sales:product_list')
            
        except Exception as e:
            messages.error(
                request,
                f'خطا در حذف محصول: {str(e)}'
            )
            return redirect('sales:product_detail', product_id=product_id)
    
    context = {
        'product': product,
        'page_title': f'حذف محصول: {product.name}',
    }
    
    return render(request, 'sales/delete_product_confirm.html', context)


@login_required
def product_search_ajax(request):
    """
    جستجوی AJAX برای محصولات
    """
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        search_query = request.GET.get('q', '')
        
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
    
    return JsonResponse({'error': 'Invalid request'}, status=400)
