"""
View های مربوط به مدیریت مواد اولیه
این ماژول شامل تمام view های مربوط به تعریف، نمایش و مدیریت مواد اولیه و استعلام قیمت است
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django_tables2 import RequestConfig
from django.contrib.auth.decorators import login_required
import logging

from core.logging_levels import *
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.RawMaterialFolder.RawMaterialPurchaseInfoModel import RawMaterialPurchaseInfo
from core.SupplyFolder.RawMaterialPriceInquiryModel import RawMaterialPriceInquiry
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from core.PersonFolder.PersonModel import Person

from supply.forms.forms import (
	RawMaterialDefineForm,
	PurchaseInfoInlineForm,
	RawMaterialPriceInquiryForm
)

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_raw_material_fields(user):
	"""دریافت فیلدهای قابل دسترس برای مدل RawMaterial"""
	return {
		'raw_material_id': user_can_access_field(user, RawMaterial, 'raw_material_id', 'view'),
		'name': user_can_access_field(user, RawMaterial, 'name', 'view'),
		'technical_description': user_can_access_field(user, RawMaterial, 'technical_description', 'view'),
		'physical_form': user_can_access_field(user, RawMaterial, 'physical_form', 'view'),
		'primary_unit': user_can_access_field(user, RawMaterial, 'primary_unit', 'view'),
		'secondary_unit': user_can_access_field(user, RawMaterial, 'secondary_unit', 'view'),
		'conversion_factor': user_can_access_field(user, RawMaterial, 'conversion_factor', 'view'),
		'hs_code': user_can_access_field(user, RawMaterial, 'hs_code', 'view'),
		'status': user_can_access_field(user, RawMaterial, 'status', 'view'),
		'attachments': user_can_access_field(user, RawMaterial, 'attachments', 'view'),
		'main_supplier': user_can_access_field(user, RawMaterial, 'main_supplier', 'view'),
		'veterinary_health_id': user_can_access_field(user, RawMaterial, 'veterinary_health_id', 'view'),
		'standard_loss_percentage': user_can_access_field(user, RawMaterial, 'standard_loss_percentage', 'view'),
		'expiration_date': user_can_access_field(user, RawMaterial, 'expiration_date', 'view'),
		'created_at': user_can_access_field(user, RawMaterial, 'created_at', 'view'),
		'updated_at': user_can_access_field(user, RawMaterial, 'updated_at', 'view'),
	}


def get_accessible_purchase_info_fields(user):
	"""دریافت فیلدهای قابل دسترس برای مدل RawMaterialPurchaseInfo"""
	return {
		'minimum_order_quantity': user_can_access_field(user, RawMaterialPurchaseInfo, 'minimum_order_quantity', 'view'),
		'transportation_conditions': user_can_access_field(user, RawMaterialPurchaseInfo, 'transportation_conditions', 'view'),
		'storage_conditions': user_can_access_field(user, RawMaterialPurchaseInfo, 'storage_conditions', 'view'),
		'vat_percentage': user_can_access_field(user, RawMaterialPurchaseInfo, 'vat_percentage', 'view'),
		'accounting_code': user_can_access_field(user, RawMaterialPurchaseInfo, 'accounting_code', 'view'),
		'tax_code': user_can_access_field(user, RawMaterialPurchaseInfo, 'tax_code', 'view'),
		'supplier': user_can_access_field(user, RawMaterialPurchaseInfo, 'supplier', 'view'),
	}


def get_accessible_person_fields(user):
	"""دریافت فیلدهای قابل دسترس برای مدل Person (برای main_supplier)"""
	return {
		'name': user_can_access_field(user, Person, 'name', 'view'),
		'national_id': user_can_access_field(user, Person, 'national_id', 'view'),
	}


@login_required
def raw_material_list_view(request):
	"""تعریف مواد اولیه - نمایش و عملیات"""
	audit_logger.info("تعریف مواد اولیه - نمایش و عملیات")
	
	# Check task permission
	if not user_has_task(request.user, TaskChoices.SUPPLY_DEFINE_RAW_MATERIAL.value):
		audit_logger.activity(f"تلاش برای دسترسی به تعریف مواد اولیه بدون مجوز - کاربر: {request.user.username}")
		messages.error(request, 'شما دسترسی به این بخش را ندارید.')
		return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
	
	# Get field access permissions
	accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
	accessible_purchase_info_fields = get_accessible_purchase_info_fields(request.user)
	accessible_person_fields = get_accessible_person_fields(request.user)
	
	# دریافت پارامترهای جستجو و فیلتر
	search_query = request.GET.get('search', '')
	status_filter = request.GET.get('status', '')
	physical_form_filter = request.GET.get('physical_form', '')
	
	try:
		if request.method == 'POST':
			rm_form = RawMaterialDefineForm(request.POST, request.FILES)
			pi_form = PurchaseInfoInlineForm(request.POST)
			if rm_form.is_valid() and pi_form.is_valid():
				with transaction.atomic():
					# ایجاد نمونه جدید - raw_material_id به صورت خودکار تولید خواهد شد
					instance = rm_form.save(commit=False)
					instance.save()

					# ایجاد یا به‌روزرسانی اطلاعات خرید (یک رکورد اصلی)
					pi, _ = RawMaterialPurchaseInfo.objects.get_or_create(raw_material=instance)
					for f, v in pi_form.cleaned_data.items():
						setattr(pi, f, v)
					pi.save()
				messages.success(request, 'ماده اولیه ثبت شد.')
				bug_logger.info(f"RawMaterial saved rid={instance.raw_material_id}")
				return redirect(reverse('supply:raw_material_list'))
			else:
				bug_logger.warning(f"فرم تعریف ماده اولیه نامعتبر است. rm_errors={rm_form.errors} pi_errors={pi_form.errors}")
				messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
		else:
			rm_form = RawMaterialDefineForm()
			pi_form = PurchaseInfoInlineForm()

		from supply.tables import RawMaterialTable
		from django.db.models import Q
		
		materials = RawMaterial.objects.all()
		
		# اعمال جستجو
		if search_query:
			materials = materials.filter(
				Q(raw_material_id__icontains=search_query) |
				Q(name__icontains=search_query) |
				Q(technical_description__icontains=search_query) |
				Q(hs_code__icontains=search_query)
			).distinct()
		
		# اعمال فیلتر وضعیت
		if status_filter:
			materials = materials.filter(status=status_filter)
		
		# اعمال فیلتر شکل فیزیکی
		if physical_form_filter:
			materials = materials.filter(physical_form=physical_form_filter)
		
		materials = materials.order_by('-created_at')
		table = RawMaterialTable(materials, accessible_fields=accessible_raw_material_fields)
		RequestConfig(request, paginate={'per_page': 25}).configure(table)
		
		# افزودن flag برای نمایان کردن فرم (در صورت وجود خطا)
		form_has_errors = request.method == 'POST' and (not rm_form.is_valid() or not pi_form.is_valid())
		
		context = {
			'rm_form': rm_form,
			'pi_form': pi_form,
			'table': table,
			'form_has_errors': form_has_errors,
			'accessible_raw_material_fields': accessible_raw_material_fields,
			'accessible_purchase_info_fields': accessible_purchase_info_fields,
			'accessible_person_fields': accessible_person_fields,
			'search_query': search_query,
			'status_filter': status_filter,
			'physical_form_filter': physical_form_filter,
		}
		return render(request, 'raw_material/raw_material_list.html', context)
	except Exception as e:
		bug_logger.error(f"Define basic material error: {e}")
		if request.method == 'POST':
			messages.error(request, 'خطا در ثبت. لطفاً مجدداً تلاش کنید.')
		from supply.tables import RawMaterialTable
		table = RawMaterialTable(RawMaterial.objects.none(), accessible_fields=accessible_raw_material_fields)
		return render(request, 'raw_material/raw_material_list.html', {
			'rm_form': RawMaterialDefineForm(),
			'pi_form': PurchaseInfoInlineForm(),
			'table': table,
			'accessible_raw_material_fields': accessible_raw_material_fields,
			'accessible_purchase_info_fields': accessible_purchase_info_fields,
			'accessible_person_fields': accessible_person_fields,
		})


def price_inquiry_modal_view(request, raw_material_id: str):
	"""مشاهده/ویرایش استعلام‌های قیمت ماده اولیه"""
	audit_logger.info("مشاهده/ویرایش استعلام‌های قیمت ماده اولیه")
	try:
		material = RawMaterial.objects.get(raw_material_id=raw_material_id)
		if request.method == 'POST':
			# ایجاد یا به‌روزرسانی
			post = request.POST.copy()
			post['raw_material'] = str(material.id)
			pk = post.get('pk')
			if pk:
				instance = RawMaterialPriceInquiry.objects.filter(pk=pk, raw_material=material).first()
				form = RawMaterialPriceInquiryForm(post, instance=instance, material=material)
			else:
				form = RawMaterialPriceInquiryForm(post, material=material)
			if form.is_valid():
				with transaction.atomic():
					rec = form.save(commit=False)
					rec.raw_material = material
					rec.save()
				bug_logger.info(f"PriceInquiry saved for rid={raw_material_id}")
				# پس از ذخیره موفق، بازگشت فرم خالی
				form = RawMaterialPriceInquiryForm(material=material)
			else:
				bug_logger.warning(f"PriceInquiry form invalid rid={raw_material_id} errors={form.errors}")
		else:
			form = RawMaterialPriceInquiryForm(material=material)

		inquiries = RawMaterialPriceInquiry.objects.filter(raw_material=material).order_by('-inquiry_date', '-created_at')
		return render(request, 'partials/price_inquiry_modal.html', {
			'material': material,
			'form': form,
			'inquiries': inquiries,
		})
	except RawMaterial.DoesNotExist:
		bug_logger.warning(f"PriceInquiry modal: raw material not found rid={raw_material_id}")
		return HttpResponseBadRequest("raw material not found")
	except Exception as e:
		bug_logger.error(f"PriceInquiry modal error: {e}")
		return HttpResponseBadRequest("error")


@login_required
def raw_material_detail_view(request, raw_material_id: str):
	"""مشاهده جزئیات ماده اولیه"""
	audit_logger.info(f"مشاهده جزئیات ماده اولیه rid={raw_material_id}")
	
	# Check task permission
	if not user_has_task(request.user, TaskChoices.SUPPLY_DEFINE_RAW_MATERIAL.value):
		audit_logger.activity(f"تلاش برای مشاهده جزئیات ماده اولیه بدون مجوز - کاربر: {request.user.username}")
		messages.error(request, 'شما دسترسی به این بخش را ندارید.')
		return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
	
	try:
		material = get_object_or_404(RawMaterial, raw_material_id=raw_material_id)
		
		# Get purchase info
		purchase_info = None
		try:
			purchase_info = RawMaterialPurchaseInfo.objects.get(raw_material=material)
		except RawMaterialPurchaseInfo.DoesNotExist:
			pass
		
		# Get field access permissions
		accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
		accessible_purchase_info_fields = get_accessible_purchase_info_fields(request.user)
		accessible_person_fields = get_accessible_person_fields(request.user)
		
		context = {
			'material': material,
			'purchase_info': purchase_info,
			'accessible_raw_material_fields': accessible_raw_material_fields,
			'accessible_purchase_info_fields': accessible_purchase_info_fields,
			'accessible_person_fields': accessible_person_fields,
		}
		
		return render(request, 'raw_material/raw_material_detail.html', context)
	except Exception as e:
		bug_logger.error(f"Raw material detail error: {e}")
		messages.error(request, 'خطا در بارگذاری جزئیات.')
		return redirect(reverse('supply:raw_material_list'))


@login_required
def raw_material_edit_view(request, raw_material_id: str):
	"""ویرایش ماده اولیه"""
	audit_logger.info(f"ویرایش ماده اولیه rid={raw_material_id}")
	
	# Check task permission
	if not user_has_task(request.user, TaskChoices.SUPPLY_DEFINE_RAW_MATERIAL.value):
		audit_logger.activity(f"تلاش برای ویرایش ماده اولیه بدون مجوز - کاربر: {request.user.username}")
		messages.error(request, 'شما دسترسی به این بخش را ندارید.')
		return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
	
	try:
		material = get_object_or_404(RawMaterial, raw_material_id=raw_material_id)
		
		# Get purchase info
		purchase_info, _ = RawMaterialPurchaseInfo.objects.get_or_create(raw_material=material)
		
		# Get field access permissions
		accessible_raw_material_fields = get_accessible_raw_material_fields(request.user)
		accessible_purchase_info_fields = get_accessible_purchase_info_fields(request.user)
		accessible_person_fields = get_accessible_person_fields(request.user)
		
		if request.method == 'POST':
			# In POST, restore values from instance for readonly/disabled fields
			post_data = request.POST.copy()
			post_data['primary_unit'] = str(material.primary_unit) if material.primary_unit else ''
			post_data['secondary_unit'] = str(material.secondary_unit) if material.secondary_unit else ''
			post_data['name'] = material.name
			post_data['conversion_factor'] = str(material.conversion_factor) if material.conversion_factor else ''
			
			rm_form = RawMaterialDefineForm(post_data, request.FILES, instance=material)
			pi_form = PurchaseInfoInlineForm(request.POST, instance=purchase_info)
		else:
			rm_form = RawMaterialDefineForm(instance=material)
			pi_form = PurchaseInfoInlineForm(instance=purchase_info)
		
		# Set readonly/disabled fields for edit mode (both GET and POST)
		# For text fields, use readonly
		rm_form.fields['name'].widget.attrs['readonly'] = True
		rm_form.fields['conversion_factor'].widget.attrs['readonly'] = True
		# For select fields, use disabled (values are restored from instance in POST)
		rm_form.fields['primary_unit'].widget.attrs['disabled'] = True
		rm_form.fields['secondary_unit'].widget.attrs['disabled'] = True
		
		if request.method == 'POST':
			if rm_form.is_valid() and pi_form.is_valid():
				with transaction.atomic():
					rm_form.save()
					pi_form.save()
				messages.success(request, 'ماده اولیه با موفقیت به‌روزرسانی شد.')
				bug_logger.info(f"RawMaterial updated rid={material.raw_material_id}")
				return redirect(reverse('supply:raw_material_detail', args=[material.raw_material_id]))
			else:
				bug_logger.warning(f"فرم ویرایش ماده اولیه نامعتبر است. rm_errors={rm_form.errors} pi_errors={pi_form.errors}")
				messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
		
		context = {
			'material': material,
			'rm_form': rm_form,
			'pi_form': pi_form,
			'accessible_raw_material_fields': accessible_raw_material_fields,
			'accessible_purchase_info_fields': accessible_purchase_info_fields,
			'accessible_person_fields': accessible_person_fields,
		}
		return render(request, 'raw_material/raw_material_edit.html', context)
	except Exception as e:
		bug_logger.error(f"Raw material edit error: {e}")
		messages.error(request, 'خطا در ویرایش.')
		return redirect(reverse('supply:raw_material_list'))

