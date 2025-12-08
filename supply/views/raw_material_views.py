"""
View های مربوط به مدیریت مواد اولیه
این ماژول شامل تمام view های مربوط به تعریف، نمایش و مدیریت مواد اولیه و استعلام قیمت است
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.http import HttpResponseBadRequest
from django_tables2 import RequestConfig
import logging

from core.logging_levels import *
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.RawMaterialFolder.RawMaterialPurchaseInfoModel import RawMaterialPurchaseInfo
from core.SupplyFolder.RawMaterialPriceInquiryModel import RawMaterialPriceInquiry

from supply.views.forms import (
	RawMaterialDefineForm,
	PurchaseInfoInlineForm,
	RawMaterialPriceInquiryForm
)

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def define_basic_material_view(request):
	"""تعریف مواد اولیه - نمایش و عملیات"""
	audit_logger.info("تعریف مواد اولیه - نمایش و عملیات")
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
				return redirect(reverse('supply:define_basic_material'))
			else:
				bug_logger.warning(f"فرم تعریف ماده اولیه نامعتبر است. rm_errors={rm_form.errors} pi_errors={pi_form.errors}")
				messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
		else:
			rm_form = RawMaterialDefineForm()
			pi_form = PurchaseInfoInlineForm()

		from supply.tables import RawMaterialTable
		materials = RawMaterial.objects.all().order_by('-created_at')
		table = RawMaterialTable(materials)
		RequestConfig(request, paginate={'per_page': 25}).configure(table)
		
		# افزودن flag برای نمایان کردن فرم (در صورت وجود خطا)
		form_has_errors = request.method == 'POST' and (not rm_form.is_valid() or not pi_form.is_valid())
		
		context = {
			'rm_form': rm_form,
			'pi_form': pi_form,
			'table': table,
			'form_has_errors': form_has_errors,
		}
		return render(request, 'supply_define_basic_material.html', context)
	except Exception as e:
		bug_logger.error(f"Define basic material error: {e}")
		if request.method == 'POST':
			messages.error(request, 'خطا در ثبت. لطفاً مجدداً تلاش کنید.')
		from supply.tables import RawMaterialTable
		table = RawMaterialTable(RawMaterial.objects.none())
		return render(request, 'supply_define_basic_material.html', {
			'rm_form': RawMaterialDefineForm(),
			'pi_form': PurchaseInfoInlineForm(),
			'table': table,
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

