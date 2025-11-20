from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django import forms
from django.forms import ModelForm, NumberInput, TextInput, Textarea
from django.forms import inlineformset_factory
from django.forms import FileInput, URLInput, ClearableFileInput
from django.http import JsonResponse, HttpResponseBadRequest
import logging
from core.logging_levels import *
from jdatetime import date as jdate

from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from core.RawMaterialFolder.RawMaterialPurchaseInfoModel import RawMaterialPurchaseInfo
from core.SupplyFolder.RawMaterialPriceInquiryModel import RawMaterialPriceInquiry

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
		fields = ['transportation_conditions', 'storage_conditions', 'minimum_order_quantity', 'vat_percentage', 'accounting_code', 'tax_code', 'supplier']
		labels = {
			'minimum_order_quantity': 'حداقل مقدار سفارش',
			'vat_percentage': 'درصد مالیات بر ارزش افزوده',
			'accounting_code': 'کد حسابداری مرتبط',
			'tax_code': 'کد مالیاتی ماده',
			'supplier': 'تامین‌کننده (Purchase Info)',
			'transportation_conditions': 'شرایط حمل',
			'storage_conditions': 'شرایط نگهداری',
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Per spec these two are required at define time
		self.fields['transportation_conditions'].required = True
		self.fields['storage_conditions'].required = True
		# Optional supplier limited to type 'supplier'
		if 'supplier' in self.fields:
			self.fields['supplier'].queryset = Person.objects.filter(type='supplier').order_by('name')
			self.fields['supplier'].required = False

class RawMaterialPriceInquiryForm(ModelForm):
	class Meta:
		model = RawMaterialPriceInquiry
		fields = [
			'inquiry_date', 'supplier', 'price', 'raw_material',
			'delivery_terms', 'loading_location', 'freight_unit_price', 'negotiation_note'
		]
		labels = {
			'inquiry_date': 'تاریخ',
			'supplier': 'تامین کننده',
			'price': 'قیمت',
			'raw_material': 'ماده',
			'delivery_terms': 'شرایط تحویل',
			'loading_location': 'محل بارگیری',
			'freight_unit_price': 'فی کرایه',
			'negotiation_note': 'شرح مذاکره',
		}
		widgets = {
			'inquiry_date': TextInput(attrs={'class': 'form-control jalali-date', 'dir': 'ltr', 'placeholder': 'YYYY-MM-DD'}),
			'price': NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
			'freight_unit_price': NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
			'delivery_terms': TextInput(attrs={'maxlength': 255, 'class': 'form-control'}),
			'loading_location': TextInput(attrs={'maxlength': 255, 'class': 'form-control'}),
			'negotiation_note': Textarea(attrs={'rows': 3, 'class': 'form-control'}),
			'supplier': forms.Select(attrs={'class': 'form-control'}),
		}

	def __init__(self, *args, **kwargs):
		material = kwargs.pop('material', None)
		super().__init__(*args, **kwargs)
		self.fields['supplier'].queryset = Person.objects.filter(type='supplier').order_by('name')
		self.fields['supplier'].required = True
		self.fields['price'].required = True
		self.fields['inquiry_date'].required = True
		self.fields['delivery_terms'].required = True
		self.fields['loading_location'].required = True
		# Ensure default Jalali date appears for new forms
		if not self.is_bound and not getattr(self.instance, 'pk', None):
			try:
				self.initial['inquiry_date'] = jdate.today().strftime('%Y-%m-%d')
			except Exception:
				pass
		if material is not None:
			self.fields['raw_material'].initial = material
			self.fields['raw_material'].disabled = True
			self.fields['raw_material'].required = True


class SupplierPersonForm(ModelForm):
	class Meta:
		model = Person
		fields = [
			'national_id', 'accounting_code', 'name', 'nature', 'registration_number',
			'birth_date', 'user_type', 'sales_expert', 'description', 'phone_number', 'introducer'
		]
		labels = {
			'national_id': 'کد ملی',
			'accounting_code': 'کد حسابداری',
			'name': 'نام شخص/شرکت',
			'nature': 'ماهیت (حقوقی/حقیقی)',
			'registration_number': 'شماره ثبت شرکت',
			'birth_date': 'تاریخ تولد',
			'user_type': 'نوع کاربری',
			'sales_expert': 'کارشناس فروش',
			'description': 'توضیحات',
			'phone_number': 'تلفن',
			'introducer': 'معرف',
		}
		widgets = {
			'national_id': TextInput(attrs={'class': 'form-control'}),
			'accounting_code': TextInput(attrs={'class': 'form-control'}),
			'name': TextInput(attrs={'class': 'form-control'}),
			'nature': forms.Select(attrs={'class': 'form-control'}),
			'registration_number': TextInput(attrs={'class': 'form-control'}),
			'birth_date': TextInput(attrs={'class': 'form-control jalali-date', 'dir': 'ltr', 'placeholder': 'YYYY-MM-DD'}),
			'user_type': forms.Select(attrs={'class': 'form-control'}),
			'sales_expert': TextInput(attrs={'class': 'form-control'}),
			'description': Textarea(attrs={'class': 'form-control', 'rows': 3}),
			'phone_number': TextInput(attrs={'class': 'form-control'}),
			'introducer': TextInput(attrs={'class': 'form-control'}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['national_id'].required = True
		self.fields['name'].required = True
		self.fields['nature'].required = True


class FinancialBankingForm(ModelForm):
	class Meta:
		model = FinancialBanking
		fields = [
			'tax_group', 'account_balance', 'economic_code', 'tax_postal_code',
			'tax_province', 'tax_city', 'tax_address'
		]
		labels = {
			'tax_group': 'گروه مالیاتی',
			'account_balance': 'مانده حساب',
			'economic_code': 'کد اقتصادی',
			'tax_postal_code': 'کد پستی مالیاتی',
			'tax_province': 'استان مالیاتی',
			'tax_city': 'شهر مالیاتی',
			'tax_address': 'آدرس مالیاتی',
		}
		widgets = {
			'tax_group': forms.Select(attrs={'class': 'form-control'}),
			'account_balance': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
			'economic_code': TextInput(attrs={'class': 'form-control'}),
			'tax_postal_code': TextInput(attrs={'class': 'form-control'}),
			'tax_province': TextInput(attrs={'class': 'form-control'}),
			'tax_city': TextInput(attrs={'class': 'form-control'}),
			'tax_address': Textarea(attrs={'class': 'form-control', 'rows': 2}),
		}


 


class RepresentativeForm(ModelForm):
	class Meta:
		model = Representative
		fields = ['name', 'position', 'mobile_number', 'phone_number', 'confirmation_letter']
		widgets = {
			'name': TextInput(attrs={'class': 'form-control'}),
			'position': TextInput(attrs={'class': 'form-control'}),
			'mobile_number': TextInput(attrs={'class': 'form-control'}),
			'phone_number': TextInput(attrs={'class': 'form-control'}),
			'confirmation_letter': ClearableFileInput(attrs={'class': 'form-control'}),
		}

RepresentativeFormSet = inlineformset_factory(
	Person,
	Representative,
	form=RepresentativeForm,
	fields=['name', 'position', 'mobile_number', 'phone_number', 'confirmation_letter'],
	extra=1,
	can_delete=True
)


class BankAccountForm(ModelForm):
	class Meta:
		model = BankAccount
		fields = ['bank_name', 'account_number', 'shaba_number']
		widgets = {
			'bank_name': TextInput(attrs={'class': 'form-control'}),
			'account_number': TextInput(attrs={'class': 'form-control'}),
			'shaba_number': TextInput(attrs={'class': 'form-control'}),
		}

BankAccountFormSet = inlineformset_factory(
	FinancialBanking,
	BankAccount,
	form=BankAccountForm,
	fields=['bank_name', 'account_number', 'shaba_number'],
	extra=1,
	can_delete=True
)


class PaymentPreferenceForm(ModelForm):
	class Meta:
		model = PaymentPreference
		fields = ['payment_method', 'payment_term_days', 'credit_limit', 'notes']
		widgets = {
			'payment_method': forms.Select(attrs={'class': 'form-control'}),
			'payment_term_days': NumberInput(attrs={'class': 'form-control'}),
			'credit_limit': NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
			'notes': Textarea(attrs={'class': 'form-control', 'rows': 3}),
		}

PaymentPreferenceFormSet = inlineformset_factory(
	Person,
	PaymentPreference,
	form=PaymentPreferenceForm,
	fields=['payment_method', 'payment_term_days', 'credit_limit', 'notes'],
	extra=1,
	can_delete=True
)


class SocialNetworkForm(ModelForm):
	class Meta:
		model = SocialNetwork
		fields = ['platform', 'handle', 'url']
		widgets = {
			'platform': forms.Select(attrs={'class': 'form-control'}),
			'handle': TextInput(attrs={'class': 'form-control'}),
			'url': URLInput(attrs={'class': 'form-control'}),
		}

SocialNetworkFormSet = inlineformset_factory(
	Person,
	SocialNetwork,
	form=SocialNetworkForm,
	fields=['platform', 'handle', 'url'],
	extra=1,
	can_delete=True
)


class AttachmentForm(ModelForm):
	class Meta:
		model = Attachment
		fields = ['doc_type', 'file', 'description']
		widgets = {
			'doc_type': forms.Select(attrs={'class': 'form-control'}),
			'file': ClearableFileInput(attrs={'class': 'form-control'}),
			'description': TextInput(attrs={'class': 'form-control'}),
		}

AttachmentFormSet = inlineformset_factory(
	Person,
	Attachment,
	form=AttachmentForm,
	fields=['doc_type', 'file', 'description'],
	extra=1,
	can_delete=True
)


def create_supplier_view(request):
	audit_logger.info("تعریف تامین‌کننده جدید - نمایش و عملیات")
	try:
		if request.method == 'POST':
			person_form = SupplierPersonForm(request.POST)
			# We'll create FinancialBanking after person saved
			fb_form = FinancialBankingForm(request.POST)

			# Initialize empty parent instances for binding formsets later after save
			if person_form.is_valid() and fb_form.is_valid():
				with transaction.atomic():
					person = person_form.save(commit=False)
					person.type = 'supplier'
					person.save()

					# Financial/Banking single row per person
					financial, _ = FinancialBanking.objects.get_or_create(person=person)
					# Update with form values
					for f, v in fb_form.cleaned_data.items():
						setattr(financial, f, v)
					financial.save()

					# Bind and save formsets
					rep_fs = RepresentativeFormSet(request.POST, request.FILES, instance=person, prefix='rep')
					ba_fs = BankAccountFormSet(request.POST, instance=financial, prefix='ba')
					pay_fs = PaymentPreferenceFormSet(request.POST, instance=person, prefix='pay')
					sn_fs = SocialNetworkFormSet(request.POST, instance=person, prefix='sn')
					att_fs = AttachmentFormSet(request.POST, request.FILES, instance=person, prefix='att')

					all_valid = rep_fs.is_valid() and ba_fs.is_valid() and pay_fs.is_valid() and sn_fs.is_valid() and att_fs.is_valid()
					if not all_valid:
						raise ValueError(f"invalid formsets: rep={rep_fs.errors} ba={ba_fs.errors} pay={pay_fs.errors} sn={sn_fs.errors} att={att_fs.errors}")

					rep_fs.save()
					ba_fs.save()
					pay_fs.save()
					sn_fs.save()
					att_fs.save()

				messages.success(request, 'تامین‌کننده با موفقیت ثبت شد.')
				return redirect(reverse('supply:create_supplier'))
			else:
				bug_logger.warning(f"Supplier form invalid person={person_form.errors} fb={fb_form.errors}")

			# Fall-through on invalid: rebuild blank formsets to display errors with entered data
			person_form = SupplierPersonForm(request.POST)
			fb_form = FinancialBankingForm(request.POST)
			rep_fs = RepresentativeFormSet(request.POST, request.FILES, prefix='rep')
			ba_fs = BankAccountFormSet(request.POST, prefix='ba')
			pay_fs = PaymentPreferenceFormSet(request.POST, prefix='pay')
			sn_fs = SocialNetworkFormSet(request.POST, prefix='sn')
			att_fs = AttachmentFormSet(request.POST, request.FILES, prefix='att')
		else:
			person_form = SupplierPersonForm()
			fb_form = FinancialBankingForm()
			rep_fs = RepresentativeFormSet(prefix='rep')
			ba_fs = BankAccountFormSet(prefix='ba')
			pay_fs = PaymentPreferenceFormSet(prefix='pay')
			sn_fs = SocialNetworkFormSet(prefix='sn')
			att_fs = AttachmentFormSet(prefix='att')

		context = {
			'person_form': person_form,
			'fb_form': fb_form,
			'rep_formset': rep_fs,
			'ba_formset': ba_fs,
			'pay_formset': pay_fs,
			'sn_formset': sn_fs,
			'att_formset': att_fs,
		}
		return render(request, 'supply_create_supplier.html', context)
	except Exception as e:
			bug_logger.error(f"Create supplier error: {e}")
			if request.method == 'POST':
				messages.error(request, 'خطا در ثبت تامین‌کننده. لطفاً مجدداً تلاش کنید.')
			# Show clean forms on exception
			return render(request, 'supply_create_supplier.html', {
				'person_form': SupplierPersonForm(),
				'fb_form': FinancialBankingForm(),
				'rep_formset': RepresentativeFormSet(prefix='rep'),
				'ba_formset': BankAccountFormSet(prefix='ba'),
				'pay_formset': PaymentPreferenceFormSet(prefix='pay'),
				'sn_formset': SocialNetworkFormSet(prefix='sn'),
				'att_formset': AttachmentFormSet(prefix='att'),
			})


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


def price_inquiry_modal_view(request, raw_material_id: str):
	audit_logger.info("مشاهده/ویرایش استعلام‌های قیمت ماده اولیه")
	try:
		material = RawMaterial.objects.get(raw_material_id=raw_material_id)
		if request.method == 'POST':
			# Create or update
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
				# After successful save return a fresh, reset form
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
