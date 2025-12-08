"""
فرم‌های مربوط به Supply Domain
این ماژول شامل تمام فرم‌ها و formset های مربوط به تامین‌کننده و مواد اولیه است
"""
from django import forms
from django.forms import ModelForm, NumberInput, TextInput, Textarea
from django.forms import inlineformset_factory
from django.forms import FileInput, URLInput, ClearableFileInput
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


# =====================================
# فرم‌های مواد اولیه (Raw Material Forms)
# =====================================

class RawMaterialDefineForm(ModelForm):
	"""فرم تعریف ماده اولیه جدید"""
	class Meta:
		model = RawMaterial
		fields = [
			'name', 'technical_description', 'physical_form',
			'primary_unit', 'secondary_unit', 'conversion_factor',
			'hs_code', 'veterinary_health_id', 'standard_loss_percentage',
			'expiration_date', 'attachments', 'main_supplier', 'status'
		]
		labels = {
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
		# فیلدهای اصلی و الزامی
		self.fields['name'].required = True
		self.fields['technical_description'].required = True
		self.fields['primary_unit'].required = True
		self.fields['secondary_unit'].required = True
		self.fields['conversion_factor'].required = True
		self.fields['status'].required = True
		# فیلدهای اختیاری
		self.fields['physical_form'].required = False
		self.fields['expiration_date'].required = False
		self.fields['attachments'].required = False
		# محدود کردن تامین‌کننده به اشخاص با نوع supplier
		self.fields['main_supplier'].required = False
		self.fields['main_supplier'].queryset = Person.objects.filter(type='supplier').order_by('name')


class PurchaseInfoInlineForm(ModelForm):
	"""فرم اطلاعات خرید ماده اولیه"""
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
		# فیلدهای الزامی
		self.fields['transportation_conditions'].required = True
		self.fields['storage_conditions'].required = True
		# تامین‌کننده اختیاری و محدود به نوع supplier
		if 'supplier' in self.fields:
			self.fields['supplier'].queryset = Person.objects.filter(type='supplier').order_by('name')
			self.fields['supplier'].required = False


class RawMaterialPriceInquiryForm(ModelForm):
	"""فرم استعلام قیمت ماده اولیه"""
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
			'raw_material': forms.HiddenInput(),
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
		# تنظیم تاریخ جلالی پیش‌فرض برای فرم‌های جدید
		if not self.is_bound and not getattr(self.instance, 'pk', None):
			try:
				self.initial['inquiry_date'] = jdate.today().strftime('%Y-%m-%d')
			except Exception:
				pass
		if material is not None:
			self.fields['raw_material'].initial = material.id
			self.fields['raw_material'].required = False
			self.fields['raw_material'].widget = forms.HiddenInput()


# =====================================
# فرم‌های تامین‌کننده (Supplier Forms)
# =====================================

class SupplierPersonForm(ModelForm):
	"""فرم اطلاعات اصلی تامین‌کننده"""
	class Meta:
		model = Person
		fields = [
			'national_id', 'accounting_code', 'name', 'nature', 'registration_number',
			'sales_expert', 'description', 'phone_number', 'introducer'
		]
		labels = {
			'national_id': 'کد ملی',
			'accounting_code': 'کد حسابداری',
			'name': 'نام شخص/شرکت',
			'nature': 'ماهیت (حقوقی/حقیقی)',
			'registration_number': 'شماره ثبت شرکت',
			'sales_expert': 'کارشناس فروش',
			'description': 'توضیحات',
			'phone_number': 'تلفن',
			'introducer': 'معرف',
		}
		widgets = {
			'national_id': TextInput(attrs={'class': 'form-control', 'placeholder': 'مثال: 0123456789'}),
			'accounting_code': TextInput(attrs={'class': 'form-control'}),
			'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'نام کامل شخص یا شرکت'}),
			'nature': forms.Select(attrs={'class': 'form-control'}),
			'registration_number': TextInput(attrs={'class': 'form-control', 'placeholder': 'شماره ثبت شرکت (در صورت وجود)'}),
			'sales_expert': forms.Select(attrs={'class': 'form-control'}),
			'description': Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'توضیحات اضافی'}),
			'phone_number': TextInput(attrs={'class': 'form-control phone-input', 'placeholder': 'مثال: 02112345678 یا 09123456789', 'dir': 'ltr'}),
			'introducer': TextInput(attrs={'class': 'form-control', 'placeholder': 'نام معرف (اختیاری)'}),
		}

	def __init__(self, *args, **kwargs):
		self.editing_instance = kwargs.get('instance')
		super().__init__(*args, **kwargs)
		self.fields['national_id'].required = True
		self.fields['name'].required = True
		self.fields['nature'].required = True
		self.fields['phone_number'].required = True

	def clean_national_id(self):
		"""اعتبارسنجی کد ملی"""
		national_id = self.cleaned_data.get('national_id')
		
		if not national_id:
			raise forms.ValidationError('کد ملی الزامی است.')
		
		# بررسی طول (10 یا 11 رقم)
		if len(national_id) not in [10, 11]:
			raise forms.ValidationError('کد ملی باید 10 یا 11 رقم باشد.')
		
		# بررسی عددی بودن
		if not national_id.isdigit():
			raise forms.ValidationError('کد ملی باید فقط شامل اعداد باشد.')
		
		# بررسی تکراری نبودن (فقط در صورت ایجاد جدید یا تغییر کد ملی)
		if not self.editing_instance or self.editing_instance.national_id != national_id:
			if Person.objects.filter(national_id=national_id).exists():
				raise forms.ValidationError('این کد ملی قبلاً ثبت شده است.')
		
		return national_id

	def clean_phone_number(self):
		"""اعتبارسنجی و فرمت‌دهی چند شماره تلفن (کاما جدا)"""
		import re
		raw = self.cleaned_data.get('phone_number')
		if not raw:
			raise forms.ValidationError('حداقل یک شماره تلفن الزامی است.')
		
		# اجازه چند شماره با جداکننده کاما
		numbers = [s.strip() for s in str(raw).split(',') if s and s.strip()]
		if not numbers:
			raise forms.ValidationError('حداقل یک شماره تلفن معتبر وارد کنید.')
		
		formatted = []
		for phone in numbers:
			# حذف تمام کاراکترهای غیرعددی
			digits_only = re.sub(r'\D', '', phone)
			
			if not digits_only:
				raise forms.ValidationError(f'شماره "{phone}" نامعتبر است. شماره تلفن باید شامل اعداد باشد.')
			
			# 1. موبایل: 11 رقم که با 09 شروع شود
			if len(digits_only) == 11 and digits_only.startswith('09'):
				# بررسی فرمت صحیح موبایل ایران
				if not re.match(r'^09[0-9]{9}$', digits_only):
					raise forms.ValidationError(f'شماره موبایل "{phone}" نامعتبر است. فرمت صحیح: 09123456789')
				# فرمت: 0912-345-6789
				formatted.append(f"{digits_only[:4]}-{digits_only[4:7]}-{digits_only[7:]}")
			
			# 2. تلفن ثابت: 11 رقم که با 0 شروع شود (اما نه 09)
			elif len(digits_only) == 11 and digits_only.startswith('0') and not digits_only.startswith('09'):
				# بررسی فرمت صحیح تلفن ثابت (0XX-XXXX-XXXX)
				# کد شهر باید 2 یا 3 رقم باشد (مثل 021، 031، 051)
				if not re.match(r'^0[1-9][0-9]{9}$', digits_only):
					raise forms.ValidationError(f'شماره تلفن ثابت "{phone}" نامعتبر است. فرمت صحیح: 02112345678')
				# فرمت: 021-1234-5678
				formatted.append(f"{digits_only[:3]}-{digits_only[3:7]}-{digits_only[7:]}")
			
			# 3. تلفن ثابت: 10 رقم (بدون صفر اول)
			elif len(digits_only) == 10:
				# کد شهر 2 رقمی + شماره 8 رقمی
				if not re.match(r'^[1-9][0-9]{9}$', digits_only):
					raise forms.ValidationError(f'شماره تلفن "{phone}" نامعتبر است.')
				# اضافه کردن 0 و فرمت: 021-1234-5678
				formatted.append(f"0{digits_only[:2]}-{digits_only[2:6]}-{digits_only[6:]}")
			
			# 4. تلفن ثابت تهران: 8 رقم (بدون کد شهر)
			elif len(digits_only) == 8:
				# شماره باید با 1 تا 9 شروع شود
				if not re.match(r'^[1-9][0-9]{7}$', digits_only):
					raise forms.ValidationError(f'شماره تلفن "{phone}" نامعتبر است. باید 8 رقم باشد.')
				# اضافه کردن کد تهران 021 و فرمت: 021-1234-5678
				formatted.append(f"021-{digits_only[:4]}-{digits_only[4:]}")
			
			else:
				raise forms.ValidationError(
					f'شماره "{phone}" با {len(digits_only)} رقم نامعتبر است. '
					'فرمت‌های مجاز: موبایل 11 رقمی (09...), تلفن ثابت 11 رقمی (021...), '
					'10 رقمی (بدون 0 اول), یا 8 رقمی (بدون کد شهر)'
				)
		
		# برگرداندن به صورت کاما جدا
		return ', '.join(formatted)


class FinancialBankingForm(ModelForm):
	"""فرم اطلاعات مالی و بانکی"""
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


# =====================================
# فرم‌ها و Formset های مرتبط با تامین‌کننده
# =====================================

class RepresentativeForm(ModelForm):
	"""فرم نمایندگان تامین‌کننده"""
	class Meta:
		model = Representative
		fields = ['name', 'position', 'mobile_number', 'phone_number', 'confirmation_letter']
		widgets = {
			'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'نام نماینده'}),
			'position': TextInput(attrs={'class': 'form-control', 'placeholder': 'سمت (مثل: مدیر فروش)'}),
			'mobile_number': TextInput(attrs={'class': 'form-control', 'placeholder': 'شماره موبایل', 'dir': 'ltr'}),
			'phone_number': TextInput(attrs={'class': 'form-control', 'placeholder': 'شماره تلفن ثابت', 'dir': 'ltr'}),
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


def get_representative_formset_with_phone(prefix='rep', person_phone=None, **kwargs):
	"""
	تابع کمکی برای ایجاد RepresentativeFormSet با مقدار پیش‌فرض شماره تلفن
	اگر person_phone داده شده باشد، به عنوان مقدار اولیه در اولین فرم نماینده قرار می‌گیرد
	"""
	if person_phone and 'initial' not in kwargs and 'instance' not in kwargs:
		# فقط برای فرم‌های جدید (بدون instance) و در صورت وجود شماره تلفن
		kwargs['initial'] = [{'phone_number': person_phone}]
	kwargs['prefix'] = prefix
	return RepresentativeFormSet(**kwargs)


class BankAccountForm(ModelForm):
	"""فرم حساب‌های بانکی"""
	class Meta:
		model = BankAccount
		fields = ['bank_name', 'account_number', 'shaba_number']
		widgets = {
			'bank_name': TextInput(attrs={'class': 'form-control'}),
			'account_number': TextInput(attrs={'class': 'form-control', 'dir': 'ltr'}),
			'shaba_number': TextInput(attrs={'class': 'form-control', 'dir': 'ltr', 'placeholder': 'IR...'}),
		}

	def clean_shaba_number(self):
		"""اعتبارسنجی شماره شبا"""
		shaba = self.cleaned_data.get('shaba_number')
		if shaba:
			# حذف فاصله‌ها
			shaba = shaba.replace(' ', '').replace('-', '').upper()
			# بررسی شروع با IR
			if not shaba.startswith('IR'):
				raise forms.ValidationError('شماره شبا باید با IR شروع شود.')
			# بررسی طول (IR + 24 رقم)
			if len(shaba) != 26:
				raise forms.ValidationError('شماره شبا باید 26 کاراکتر باشد (IR + 24 رقم).')
			# بررسی عددی بودن قسمت بعد از IR
			if not shaba[2:].isdigit():
				raise forms.ValidationError('قسمت عددی شماره شبا نامعتبر است.')
			return shaba
		return shaba

	def clean_account_number(self):
		"""اعتبارسنجی شماره حساب"""
		account = self.cleaned_data.get('account_number')
		if account:
			# حذف فاصله‌ها و خط تیره
			account = account.replace(' ', '').replace('-', '')
			# بررسی عددی بودن
			if not account.isdigit():
				raise forms.ValidationError('شماره حساب باید فقط شامل اعداد باشد.')
			# بررسی طول معقول (معمولاً بین 10 تا 16 رقم)
			if len(account) < 10 or len(account) > 20:
				raise forms.ValidationError('شماره حساب باید بین 10 تا 20 رقم باشد.')
			return account
		return account


BankAccountFormSet = inlineformset_factory(
	FinancialBanking,
	BankAccount,
	form=BankAccountForm,
	fields=['bank_name', 'account_number', 'shaba_number'],
	extra=1,
	can_delete=True
)


class PaymentPreferenceForm(ModelForm):
	"""فرم ترجیحات پرداخت"""
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
	"""فرم شبکه‌های اجتماعی"""
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
	"""فرم پیوست‌ها"""
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

