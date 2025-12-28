"""
View های مربوط به مدیریت تامین‌کنندگان
این ماژول شامل تمام view های مربوط به ثبت، نمایش، ویرایش و مدیریت تامین‌کنندگان است
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction
from django.http import HttpResponseForbidden
from django_tables2 import RequestConfig
import logging

from core.RBACModel import user_has_task, TaskChoices, user_can_access_field

from core.logging_levels import *
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.PersonFolder.RepresentativeModel import Representative
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.PaymentPreferenceModel import PaymentPreference
from core.PersonFolder.SocialNetworkModel import SocialNetwork
from core.PersonFolder.AttachmentModel import Attachment
from core.WarehouseFolder.WarehouseModel import Warehouse

from supply.views.forms import (
	SupplierPersonForm, FinancialBankingForm,
	RepresentativeFormSet, BankAccountFormSet,
	PaymentPreferenceFormSet, SocialNetworkFormSet, AttachmentFormSet
)

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_person_fields(user):
	"""بررسی دسترسی کاربر به فیلدهای Person"""
	return {
		'national_id': user_can_access_field(user, Person, 'national_id', 'view'),
		'name': user_can_access_field(user, Person, 'name', 'view'),
		'nature': user_can_access_field(user, Person, 'nature', 'view'),
		'registration_number': user_can_access_field(user, Person, 'registration_number', 'view'),
		'phone_number': user_can_access_field(user, Person, 'phone_number', 'view'),
		'type': user_can_access_field(user, Person, 'type', 'view'),
		'accounting_code': user_can_access_field(user, Person, 'accounting_code', 'view'),
		'birth_date': user_can_access_field(user, Person, 'birth_date', 'view'),
		'activity_fields': user_can_access_field(user, Person, 'activity_fields', 'view'),
		'sales_expert': user_can_access_field(user, Person, 'sales_expert', 'view'),
		'description': user_can_access_field(user, Person, 'description', 'view'),
		'introducer': user_can_access_field(user, Person, 'introducer', 'view'),
		'warehouse': user_can_access_field(user, Person, 'warehouse', 'view'),
		'is_active': user_can_access_field(user, Person, 'is_active', 'view'),
	}


def create_supplier_view(request):
	"""ایجاد تامین‌کننده جدید"""
	audit_logger.info("تعریف تامین‌کننده جدید - نمایش و عملیات")
	try:
		if request.method == 'POST':
			person_form = SupplierPersonForm(request.POST, instance=None)
			fb_form = FinancialBankingForm(request.POST)

			if person_form.is_valid() and fb_form.is_valid():
				with transaction.atomic():
					person = person_form.save(commit=False)
					person.type = 'supplier'
					person.save()

					# ایجاد یا دریافت اطلاعات مالی/بانکی
					financial, _ = FinancialBanking.objects.get_or_create(person=person)
					for f, v in fb_form.cleaned_data.items():
						setattr(financial, f, v)
					financial.save()

					# ایجاد انبار برای تامین‌کننده (اگر وجود نداشته باشد)
					if not person.warehouse:
						warehouse_name = f"انبار {person.name or person.national_id}"
						warehouse_id = f"WH-SUP-{person.national_id}"
						warehouse, created = Warehouse.objects.get_or_create(
							warehouse_id=warehouse_id,
							defaults={
								'name': warehouse_name,
								'warehouse_type': 'supplier',
							}
						)
						if created:
							bug_logger.info(f"انبار جدید برای تامین‌کننده {person.national_id} ایجاد شد: {warehouse_id}")
							audit_logger.info(f"انبار {warehouse_id} برای تامین‌کننده {person.national_id} ایجاد شد")
						person.warehouse = warehouse
						person.save()

					# اتصال و ذخیره formset ها
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

			# در صورت نامعتبر بودن: بازسازی formset ها با داده‌های وارد شده
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
		return render(request, 'supplier/create_supplier.html', context)
	except Exception as e:
		bug_logger.error(f"Create supplier error: {e}")
		if request.method == 'POST':
			messages.error(request, 'خطا در ثبت تامین‌کننده. لطفاً مجدداً تلاش کنید.')
		# نمایش فرم‌های خالی در صورت بروز خطا
		return render(request, 'supplier/create_supplier.html', {
			'person_form': SupplierPersonForm(),
			'fb_form': FinancialBankingForm(),
			'rep_formset': RepresentativeFormSet(prefix='rep'),
			'ba_formset': BankAccountFormSet(prefix='ba'),
			'pay_formset': PaymentPreferenceFormSet(prefix='pay'),
			'sn_formset': SocialNetworkFormSet(prefix='sn'),
			'att_formset': AttachmentFormSet(prefix='att'),
		})


def supply_home_view(request):
	"""صفحه اصلی دامنه تامین"""
	audit_logger.info("دسترسی به دامنه تامین")
	return redirect(reverse('supply:supplier_list'))


@login_required
def supplier_list_view(request):
	"""نمایش لیست تأمین‌کنندگان و ایجاد تامین‌کننده جدید"""
	audit_logger.info("مشاهده لیست تأمین‌کنندگان")
	
	# Check task permission
	if not user_has_task(request.user, TaskChoices.SUPPLY_CREATE_SUPPLIER.value):
		audit_logger.activity(f"تلاش برای دسترسی به لیست تامین‌کنندگان بدون مجوز - کاربر: {request.user.username}")
		messages.error(request, 'شما دسترسی به این بخش را ندارید.')
		return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
	
	# Get accessible fields
	accessible_person_fields = get_accessible_person_fields(request.user)
	
	try:
		if request.method == 'POST':
			audit_logger.info("تعریف تامین‌کننده جدید")
			person_form = SupplierPersonForm(request.POST, instance=None)
			fb_form = FinancialBankingForm(request.POST)

			# بررسی اعتبار فرم‌ها و formset ها
			rep_fs = RepresentativeFormSet(request.POST, request.FILES, prefix='rep')
			ba_fs = BankAccountFormSet(request.POST, prefix='ba')
			pay_fs = PaymentPreferenceFormSet(request.POST, prefix='pay')
			sn_fs = SocialNetworkFormSet(request.POST, prefix='sn')
			att_fs = AttachmentFormSet(request.POST, request.FILES, prefix='att')
			
			person_valid = person_form.is_valid()
			fb_valid = fb_form.is_valid()
			rep_valid = rep_fs.is_valid()
			ba_valid = ba_fs.is_valid()
			pay_valid = pay_fs.is_valid()
			sn_valid = sn_fs.is_valid()
			att_valid = att_fs.is_valid()
			
			all_valid = person_valid and fb_valid and rep_valid and ba_valid and pay_valid and sn_valid and att_valid
			
			if all_valid:
				with transaction.atomic():
					person = person_form.save(commit=False)
					person.type = 'supplier'
					person.save()

					# ایجاد یا دریافت اطلاعات مالی/بانکی
					financial, _ = FinancialBanking.objects.get_or_create(person=person)
					for f, v in fb_form.cleaned_data.items():
						setattr(financial, f, v)
					financial.save()

					# ایجاد انبار برای تامین‌کننده (اگر وجود نداشته باشد)
					if not person.warehouse:
						warehouse_name = f"انبار {person.name or person.national_id}"
						warehouse_id = f"WH-SUP-{person.national_id}"
						warehouse, created = Warehouse.objects.get_or_create(
							warehouse_id=warehouse_id,
							defaults={
								'name': warehouse_name,
								'warehouse_type': 'supplier',
							}
						)
						if created:
							bug_logger.info(f"انبار جدید برای تامین‌کننده {person.national_id} ایجاد شد: {warehouse_id}")
							audit_logger.info(f"انبار {warehouse_id} برای تامین‌کننده {person.national_id} ایجاد شد")
						person.warehouse = warehouse
						person.save()

					# اتصال و ذخیره formset ها
					rep_fs.instance = person
					ba_fs.instance = financial
					pay_fs.instance = person
					sn_fs.instance = person
					att_fs.instance = person

					rep_fs.save()
					ba_fs.save()
					pay_fs.save()
					sn_fs.save()
					att_fs.save()

				messages.success(request, 'تامین‌کننده با موفقیت ثبت شد.')
				return redirect(reverse('supply:supplier_list'))
			else:
				bug_logger.warning(f"Supplier form invalid person={person_form.errors} fb={fb_form.errors} rep={rep_fs.errors} ba={ba_fs.errors} pay={pay_fs.errors} sn={sn_fs.errors} att={att_fs.errors}")
				
				# ایجاد پیام خطا برای هر بخش
				error_sections = []
				if not person_valid:
					error_sections.append('اطلاعات شخص/شرکت')
				if not fb_valid:
					error_sections.append('اطلاعات مالی/بانکی')
				if not rep_valid:
					error_sections.append('نمایندگان')
				if not ba_valid:
					error_sections.append('حساب‌های بانکی')
				if not pay_valid:
					error_sections.append('ترجیحات پرداخت')
				if not sn_valid:
					error_sections.append('شبکه‌های اجتماعی')
				if not att_valid:
					error_sections.append('پیوست‌ها')
				
				if error_sections:
					messages.error(request, f'لطفاً خطاهای بخش‌های زیر را برطرف کنید: {", ".join(error_sections)}')
				else:
					messages.error(request, 'لطفاً خطاهای فرم را برطرف کنید.')
		else:
			person_form = SupplierPersonForm()
			fb_form = FinancialBankingForm()
			rep_fs = RepresentativeFormSet(prefix='rep')
			ba_fs = BankAccountFormSet(prefix='ba')
			pay_fs = PaymentPreferenceFormSet(prefix='pay')
			sn_fs = SocialNetworkFormSet(prefix='sn')
			att_fs = AttachmentFormSet(prefix='att')
		
		from supply.tables import SupplierTable
		suppliers = Person.objects.filter(type='supplier').order_by('-national_id')
		table = SupplierTable(suppliers, accessible_fields=accessible_person_fields)
		RequestConfig(request, paginate={'per_page': 25}).configure(table)
		
		# افزودن flag برای نمایان کردن فرم (در صورت وجود خطا)
		form_has_errors = request.method == 'POST' and (
			not person_form.is_valid() or not fb_form.is_valid() or
			not rep_fs.is_valid() or not ba_fs.is_valid() or
			not pay_fs.is_valid() or not sn_fs.is_valid() or not att_fs.is_valid()
		)
		
		# بررسی خطاهای هر بخش
		section_errors = {
			'person': not person_form.is_valid() if request.method == 'POST' else False,
			'financial': not fb_form.is_valid() if request.method == 'POST' else False,
			'representatives': not rep_fs.is_valid() if request.method == 'POST' else False,
			'bank_accounts': not ba_fs.is_valid() if request.method == 'POST' else False,
			'payment_preferences': not pay_fs.is_valid() if request.method == 'POST' else False,
			'social_networks': not sn_fs.is_valid() if request.method == 'POST' else False,
			'attachments': not att_fs.is_valid() if request.method == 'POST' else False,
		}
		
		context = {
			'table': table,
			'person_form': person_form,
			'fb_form': fb_form,
			'rep_formset': rep_fs,
			'ba_formset': ba_fs,
			'pay_formset': pay_fs,
			'sn_formset': sn_fs,
			'att_formset': att_fs,
			'form_has_errors': form_has_errors,
			'section_errors': section_errors,
			'accessible_person_fields': accessible_person_fields,
		}
		return render(request, 'supplier/supplier_list.html', context)
	except Exception as e:
		bug_logger.error(f"Supplier list error: {e}")
		messages.error(request, 'خطا در بارگذاری لیست تأمین‌کنندگان.')
		from supply.tables import SupplierTable
		accessible_person_fields = get_accessible_person_fields(request.user)
		table = SupplierTable(Person.objects.none(), accessible_fields=accessible_person_fields)
		return render(request, 'supplier/supplier_list.html', {'table': table, 'accessible_person_fields': accessible_person_fields})


def supplier_detail_view(request, national_id):
	"""نمایش جزئیات تأمین‌کننده"""
	audit_logger.info(f"مشاهده جزئیات تأمین‌کننده با کد ملی {national_id}")
	try:
		from supply.tables import (
			RepresentativeTable, BankAccountTable, PaymentPreferenceTable,
			SocialNetworkTable, AttachmentTable
		)
		supplier = Person.objects.get(national_id=national_id, type='supplier')
		financial_banking = FinancialBanking.objects.filter(person=supplier).first()
		representatives = Representative.objects.filter(person=supplier)
		bank_accounts = BankAccount.objects.filter(financial_banking=financial_banking) if financial_banking else []
		payment_preferences = PaymentPreference.objects.filter(person=supplier)
		social_networks = SocialNetwork.objects.filter(person=supplier)
		attachments = Attachment.objects.filter(person=supplier)
		
		# ایجاد جداول
		rep_table = RepresentativeTable(representatives)
		ba_table = BankAccountTable(bank_accounts)
		pp_table = PaymentPreferenceTable(payment_preferences)
		sn_table = SocialNetworkTable(social_networks)
		att_table = AttachmentTable(attachments)
		
		context = {
			'supplier': supplier,
			'financial_banking': financial_banking,
			'representatives': representatives,
			'bank_accounts': bank_accounts,
			'payment_preferences': payment_preferences,
			'social_networks': social_networks,
			'attachments': attachments,
			'rep_table': rep_table,
			'ba_table': ba_table,
			'pp_table': pp_table,
			'sn_table': sn_table,
			'att_table': att_table,
		}
		return render(request, 'supplier/supplier_detail.html', context)
	except Person.DoesNotExist:
		bug_logger.warning(f"Supplier not found: {national_id}")
		messages.error(request, 'تأمین‌کننده مورد نظر یافت نشد.')
		return redirect(reverse('supply:supplier_list'))
	except Exception as e:
		bug_logger.error(f"Supplier detail error: {e}")
		messages.error(request, 'خطا در بارگذاری اطلاعات تأمین‌کننده.')
		return redirect(reverse('supply:supplier_list'))


def supplier_edit_view(request, national_id):
	"""ویرایش تأمین‌کننده"""
	audit_logger.info(f"ویرایش تأمین‌کننده با کد ملی {national_id}")
	try:
		supplier = Person.objects.get(national_id=national_id, type='supplier')
		financial_banking, _ = FinancialBanking.objects.get_or_create(person=supplier)
		
		if request.method == 'POST':
			person_form = SupplierPersonForm(request.POST, instance=supplier)
			fb_form = FinancialBankingForm(request.POST, instance=financial_banking)
			
			if person_form.is_valid() and fb_form.is_valid():
				with transaction.atomic():
					person_form.save()
					fb_form.save()
					
					# اتصال و ذخیره formset ها
					rep_fs = RepresentativeFormSet(request.POST, request.FILES, instance=supplier, prefix='rep')
					ba_fs = BankAccountFormSet(request.POST, instance=financial_banking, prefix='ba')
					pay_fs = PaymentPreferenceFormSet(request.POST, instance=supplier, prefix='pay')
					sn_fs = SocialNetworkFormSet(request.POST, instance=supplier, prefix='sn')
					att_fs = AttachmentFormSet(request.POST, request.FILES, instance=supplier, prefix='att')
					
					all_valid = rep_fs.is_valid() and ba_fs.is_valid() and pay_fs.is_valid() and sn_fs.is_valid() and att_fs.is_valid()
					if not all_valid:
						raise ValueError(f"invalid formsets: rep={rep_fs.errors} ba={ba_fs.errors} pay={pay_fs.errors} sn={sn_fs.errors} att={att_fs.errors}")
					
					rep_fs.save()
					ba_fs.save()
					pay_fs.save()
					sn_fs.save()
					att_fs.save()
				
				messages.success(request, 'تأمین‌کننده با موفقیت ویرایش شد.')
				return redirect(reverse('supply:supplier_detail', kwargs={'national_id': national_id}))
			else:
				bug_logger.warning(f"Supplier edit form invalid person={person_form.errors} fb={fb_form.errors}")
			
			# در صورت نامعتبر بودن: بازسازی formset ها با داده‌های وارد شده
			rep_fs = RepresentativeFormSet(request.POST, request.FILES, instance=supplier, prefix='rep')
			ba_fs = BankAccountFormSet(request.POST, instance=financial_banking, prefix='ba')
			pay_fs = PaymentPreferenceFormSet(request.POST, instance=supplier, prefix='pay')
			sn_fs = SocialNetworkFormSet(request.POST, instance=supplier, prefix='sn')
			att_fs = AttachmentFormSet(request.POST, request.FILES, instance=supplier, prefix='att')
		else:
			person_form = SupplierPersonForm(instance=supplier)
			fb_form = FinancialBankingForm(instance=financial_banking)
			rep_fs = RepresentativeFormSet(instance=supplier, prefix='rep')
			ba_fs = BankAccountFormSet(instance=financial_banking, prefix='ba')
			pay_fs = PaymentPreferenceFormSet(instance=supplier, prefix='pay')
			sn_fs = SocialNetworkFormSet(instance=supplier, prefix='sn')
			att_fs = AttachmentFormSet(instance=supplier, prefix='att')
		
		context = {
			'supplier': supplier,
			'person_form': person_form,
			'fb_form': fb_form,
			'rep_formset': rep_fs,
			'ba_formset': ba_fs,
			'pay_formset': pay_fs,
			'sn_formset': sn_fs,
			'att_formset': att_fs,
		}
		return render(request, 'supplier/supplier_edit.html', context)
	except Person.DoesNotExist:
		bug_logger.warning(f"Supplier not found for edit: {national_id}")
		messages.error(request, 'تأمین‌کننده مورد نظر یافت نشد.')
		return redirect(reverse('supply:supplier_list'))
	except Exception as e:
		bug_logger.error(f"Supplier edit error: {e}")
		messages.error(request, 'خطا در ویرایش تأمین‌کننده.')
		return redirect(reverse('supply:supplier_list'))

