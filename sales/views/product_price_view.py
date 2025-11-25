from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q
import logging
import jdatetime
from core.logging_levels import *
import django_tables2 as tables
from django_tables2 import RequestConfig

from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo
from core.RBACModel import user_has_task, TaskChoices
from sales.forms.product_financial_info_form import (
    ProductFinancialInfoForm,
    get_accessible_financial_info_fields
)
from sales.tables import ProductPriceTable

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_product_price_list_fields(user):
    """
    بررسی دسترسی کاربر به فیلدهای نمایش لیست قیمت‌گذاری محصولات
    برای استفاده در django-tables2
    
    Returns:
        dict: دیکشنری از نام فیلد به دسترسی (True/False)
    """
    from core.ProductFolder.ProductFinancialInfoModel import ProductFinancialInfo as ProductFinancialInfoModel
    from core.ProductFolder.ProductModel import Product as ProductModel
    from access.helpers import check_field_access_prefer_edit
    
    # superuser به همه فیلدها دسترسی دارد
    if user.is_superuser:
        return {
            'product_code': True,
            'product_name': True,
            'price': True,
            'deadline': True,
            'loading_date': True,
            'condition': True,
            'created_at': True,
            'actions': True,
        }
    
    # فیلدهایی که در لیست نمایش داده می‌شوند
    field_mapping = {
        'product_code': (ProductModel, 'code'),
        'product_name': (ProductModel, 'name'),
        'price': (ProductFinancialInfoModel, 'price'),
        'deadline': (ProductFinancialInfoModel, 'deadline'),
        'loading_date': (ProductFinancialInfoModel, 'loading_date'),
        'condition': (ProductFinancialInfoModel, 'condition'),
        'created_at': None,  # همیشه نمایش داده می‌شود
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
def product_price_list_view(request):
    """
    ویو لیست قیمت‌گذاری‌های محصولات با استفاده از django-tables2
    - بررسی دسترسی با TaskPermission
    - کنترل دسترسی فیلدها با FieldPermission
    - قابلیت جستجو و فیلتر
    """
    audit_logger.info("درخواست مشاهده لیست قیمت‌گذاری‌های محصولات")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_SET_PRODUCT_PRICE.value):
        audit_logger.activity("تلاش برای مشاهده لیست قیمت‌گذاری‌ها بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست قیمت‌گذاری‌ها ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    product_filter = request.GET.get('product', '')
    
    # حذف خودکار قیمت‌گذاری‌های منقضی شده
    today = jdatetime.date.today()
    expired_prices = ProductFinancialInfo.objects.filter(deadline__lt=today)
    expired_count = expired_prices.count()
    if expired_count > 0:
        expired_prices.delete()
        bug_logger.info(f"تعداد {expired_count} قیمت‌گذاری منقضی شده حذف شد")
    
    # شروع با تمام قیمت‌گذاری‌ها
    price_list = ProductFinancialInfo.objects.all().select_related('product').order_by('-created_at')
    
    # اعمال جستجو
    if search_query:
        price_list = price_list.filter(
            Q(product__name__icontains=search_query) |
            Q(product__code__icontains=search_query) |
            Q(condition__icontains=search_query)
        )
    
    # اعمال فیلتر محصول
    if product_filter:
        price_list = price_list.filter(product_id=product_filter)
    
    bug_logger.debug(f"تعداد {price_list.count()} قیمت‌گذاری برای نمایش لود شد")
    
    # محاسبه فیلدهای قابل دسترسی
    accessible_fields = get_accessible_product_price_list_fields(request.user)
    
    # ایجاد جدول با django-tables2 و پاس دادن دسترسی فیلدها
    table = ProductPriceTable(price_list, user=request.user, accessible_fields=accessible_fields)
    
    RequestConfig(request, paginate={'per_page': 20}).configure(table)
    
    # دریافت لیست محصولات برای فیلتر
    products = Product.objects.all().order_by('code')
    
    context = {
        'table': table,
        'accessible_fields': accessible_fields,
        'search_query': search_query,
        'products': products,
        'product_filter': product_filter,
        'page_title': 'لیست قیمت‌گذاری محصولات',
    }
    
    return render(request, 'product/product_price_list.html', context)


@login_required
def set_product_price_view(request, product_id=None):
    """
    ویو قیمت‌گذاری محصول
    - بررسی دسترسی با TaskPermission
    - بررسی دسترسی فیلدها با FieldAccessRule
    - product_id اختیاری است - اگر نباشد، کاربر می‌تواند از فرم انتخاب کند
    """
    if product_id:
        audit_logger.info(f"درخواست قیمت‌گذاری محصول با شناسه {product_id}")
    else:
        audit_logger.info("درخواست قیمت‌گذاری محصول (بدون شناسه)")
    
    # بررسی دسترسی TaskPermission
    if not user_has_task(request.user, TaskChoices.SALES_SET_PRODUCT_PRICE.value):
        audit_logger.activity(f"تلاش برای قیمت‌گذاری محصول بدون دسترسی (product_id: {product_id})")
        messages.error(request, 'شما دسترسی به قیمت‌گذاری محصول ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    product = None
    if product_id:
        product = get_object_or_404(Product, id=product_id)
    
    # دریافت فیلدهای قابل دسترسی برای کاربر
    accessible_fields = get_accessible_financial_info_fields(request.user)
    
    if request.method == 'POST':
        # ایجاد فرم با داده‌های ارسالی
        financial_info_form = ProductFinancialInfoForm(
            request.POST,
            user=request.user,
            accessible_fields=accessible_fields
        )
        
        if financial_info_form.is_valid():
            try:
                # ذخیره اطلاعات مالی
                financial_info = financial_info_form.save()
                
                product = financial_info.product
                bug_logger.info(f"قیمت محصول {product.code} با موفقیت ثبت شد")
                messages.success(
                    request,
                    f'قیمت محصول "{product.name}" با کد "{product.code}" با موفقیت ثبت شد.'
                )
                
                return redirect('sales:product_price_list')
                
            except Exception as e:
                bug_logger.error(f"خطا در ثبت قیمت محصول: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    f'خطا در ثبت قیمت محصول: {str(e)}'
                )
        else:
            # نمایش خطاهای فرم
            bug_logger.warning("فرم قیمت‌گذاری محصول معتبر نیست")
            for field, errors in financial_info_form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        # ایجاد فرم خالی
        initial_data = {}
        if product:
            initial_data['product'] = product.id
        
        financial_info_form = ProductFinancialInfoForm(
            user=request.user,
            accessible_fields=accessible_fields,
            initial=initial_data
        )
    
    # اطلاعات محصول برای نمایش (اگر product_id داده شده باشد)
    product_info = None
    if product:
        product_info = {
            'code': product.code,
            'name': product.name,
            'main_unit': product.main_unit or 'تعریف نشده',
            'invoice_description': product.invoice_description or 'تعریف نشده',
        }
        bug_logger.debug(f"نمایش صفحه قیمت‌گذاری برای محصول {product.code}")
    
    context = {
        'product': product,
        'product_info': product_info,
        'financial_info_form': financial_info_form,
        'accessible_fields': accessible_fields,
        'page_title': f'قیمت‌گذاری محصول' + (f': {product.name}' if product else ''),
        'submit_button_text': 'ثبت قیمت',
    }
    
    return render(request, 'product/set_product_price.html', context)

