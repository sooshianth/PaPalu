from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.forms import ModelForm
import logging
from core.logging_levels import *

from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.PersonFolder.PersonModel import Person
from core.RawMaterialFolder.RawMaterialPurchaseInfoModel import RawMaterialPurchaseInfo

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


class RawMaterialDefineForm(ModelForm):
	class Meta:
		model = RawMaterial
		fields = [
			'raw_material_id', 'name', 'technical_description', 'physical_form',
			'primary_unit', 'secondary_unit', 'conversion_factor',
			'hs_code', 'veterinary_health_id', 'standard_loss_percentage',
			'expiration_date', 'attachments', 'main_supplier', 'status'
		]
		labels = {
			'raw_material_id': 'شناسه ماده اولیه',
			'name': 'نام ماده اولیه',
			'technical_description': 'توضیحات و مشخصات فنی',
			'physical_form': 'شکل فیزیکی',
			'primary_unit': 'واحد شمارش اصلی',
			'secondary_unit': 'واحد شمارش فرعی',
			'conversion_factor': 'ضریب تبدیل (اصلی→فرعی)',
			'hs_code': 'HS Code',
			'veterinary_health_id': 'شناسه یکتا در سیستم دامپزشکی/بهداشت',
			'standard_loss_percentage': 'درصد افت استاندارد',
			'expiration_date': 'تاریخ انقضا (کاراکتری)',
			'attachments': 'پیوست‌ها (آنالیز یا توضیحات)',
			'main_supplier': 'تامین‌کننده اصلی این کالا',
			'status': 'وضعیت',
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Mark core fields as required (per spec)
		self.fields['raw_material_id'].required = True
		self.fields['name'].required = True
		self.fields['technical_description'].required = True
		self.fields['primary_unit'].required = True
		self.fields['secondary_unit'].required = True
		self.fields['conversion_factor'].required = True
		self.fields['status'].required = True
		# Move transportation & storage to required group (handled in PurchaseInfo form already)
		self.fields['physical_form'].required = False
		self.fields['expiration_date'].required = False
		self.fields['attachments'].required = False
		# Limit supplier choices to Person with type='supplier'
		self.fields['main_supplier'].required = False
		self.fields['main_supplier'].queryset = Person.objects.filter(type='supplier').order_by('name')


class PurchaseInfoInlineForm(ModelForm):
	class Meta:
		model = RawMaterialPurchaseInfo
		fields = ['transportation_conditions', 'storage_conditions', 'minimum_order_quantity', 'vat_percentage', 'accounting_code']
		labels = {
			'minimum_order_quantity': 'حداقل مقدار سفارش',
			'vat_percentage': 'درصد مالیات بر ارزش افزوده',
			'accounting_code': 'کد حسابداری مرتبط',
			'transportation_conditions': 'شرایط حمل',
			'storage_conditions': 'شرایط نگهداری',
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Per spec these two are required at define time
		self.fields['transportation_conditions'].required = True
		self.fields['storage_conditions'].required = True


def supply_home_view(request):
	audit_logger.info("دسترسی به دامنه تامین")
	return redirect(reverse('supply:define_basic_material'))


def define_basic_material_view(request):
	audit_logger.info("تعریف مواد اولیه - نمایش و عملیات")
	try:
		if request.method == 'POST':
			rm_form = RawMaterialDefineForm(request.POST, request.FILES)
			pi_form = PurchaseInfoInlineForm(request.POST)
			if rm_form.is_valid() and pi_form.is_valid():
				with transaction.atomic():
					raw_id = rm_form.cleaned_data['raw_material_id']
					instance, created = RawMaterial.objects.get_or_create(raw_material_id=raw_id)
					for f, v in rm_form.cleaned_data.items():
						setattr(instance, f, v)
					instance.save()

					# Upsert purchase info (one primary row)
					pi, _ = RawMaterialPurchaseInfo.objects.get_or_create(raw_material=instance)
					for f, v in pi_form.cleaned_data.items():
						setattr(pi, f, v)
					pi.save()
				messages.success(request, 'ماده اولیه ثبت شد.')
				bug_logger.info(f"RawMaterial saved rid={instance.raw_material_id}")
				return redirect(reverse('supply:define_basic_material'))
			else:
				bug_logger.warning(f"فرم تعریف ماده اولیه نامعتبر است. rm_errors={rm_form.errors} pi_errors={pi_form.errors}")
		else:
			rm_form = RawMaterialDefineForm()
			pi_form = PurchaseInfoInlineForm()

		materials = RawMaterial.objects.all().order_by('-created_at')
		context = {
			'rm_form': rm_form,
			'pi_form': pi_form,
			'materials': materials,
		}
		return render(request, 'supply_define_basic_material.html', context)
	except Exception as e:
		bug_logger.error(f"Define basic material error: {e}")
		if request.method == 'POST':
			messages.error(request, 'خطا در ثبت. لطفاً مجدداً تلاش کنید.')
		return render(request, 'supply_define_basic_material.html', {
			'rm_form': RawMaterialDefineForm(),
			'pi_form': PurchaseInfoInlineForm(),
			'materials': RawMaterial.objects.none(),
		})
