from django import forms
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from django_jalali.forms import jDateField
from django_jalali.forms.widgets import jDateInput


class ProductionProgramForm(forms.ModelForm):
    """فرم برنامه تولید با استایل مشابه فرم های فروش و اعتبارسنجی گردش وضعیت.

    قوانین اعتبارسنجی (خلاصه):
      - در وضعیت های غیر Draft فیلدهای الزامی باید پر باشند: program_id, product, planned_weight_ton,
        predicted_start_time, predicted_end_time (end > start), execution_date, packaging_type.
      - planned_weight_ton > 0 ، produced_weight_ton در صورت ورود >0.
      - پس از تایید (confirmed) فیلدهای اصلی غیر قابل ویرایش می شوند (به جز produced_weight_ton برای بروزرسانی تحقق).
    """

    # Explicit field widgets & labels (override Model meta widgets)
    production_info = forms.ModelChoiceField(
        queryset=ProductionProgram._meta.get_field('production_info').remote_field.model.objects.all(),
        required=False,
        label='اطلاعات فرمول',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    product = forms.ModelChoiceField(
        queryset=ProductionProgram._meta.get_field('product').remote_field.model.objects.all(),
        required=False,
        label='محصول',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    program_id = forms.CharField(
        max_length=100,
        required=False,
        label='شناسه برنامه',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    planned_weight_ton = forms.DecimalField(
        max_digits=12, decimal_places=3,
        required=False,
        label='تناژ برنامه (تن)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    predicted_start_date = jDateField(
        required=False,
        label='تاریخ شروع پیشبینی شده',
        widget=forms.TextInput(attrs={'class': 'form-control jalali-date', 'dir': 'ltr', 'placeholder': '1403-08-29'})
    )
    predicted_start_time = forms.TimeField(
        required=False,
        label='زمان شروع پیشبینی شده',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
    predicted_end_date = jDateField(
        required=False,
        label='تاریخ پایان پیشبینی شده',
        widget=forms.TextInput(attrs={'class': 'form-control jalali-date', 'dir': 'ltr', 'placeholder': '1403-08-29'})
    )
    predicted_end_time = forms.TimeField(
        required=False,
        label='زمان پایان پیشبینی شده',
        widget=forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'})
    )
    packaging_type = forms.ChoiceField(
        required=False,
        label='نوع بسته بندی',
        choices=ProductionProgram.PACKAGING_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    extra_description = forms.CharField(
        required=False,
        label='توضیحات اضافی',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    inventory_snapshot = forms.DecimalField(
        max_digits=12, decimal_places=3,
        required=False,
        label='موجودی لحظه ثبت',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    net_unplanned_requirement = forms.DecimalField(
        max_digits=12, decimal_places=3,
        required=False,
        label='نیاز برنامه ریزی نشده',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    produced_weight_ton = forms.DecimalField(
        max_digits=12, decimal_places=3,
        required=False,
        label='وزن تولید شده',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    status = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = ProductionProgram
        fields = [
            'production_info', 'product', 'program_id', 'planned_weight_ton',
            'predicted_start_date', 'predicted_start_time', 'predicted_end_date', 'predicted_end_time',
            'packaging_type', 'extra_description',
            'inventory_snapshot', 'net_unplanned_requirement', 'produced_weight_ton', 'status'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Lock fields when not draft
        instance: ProductionProgram | None = getattr(self, 'instance', None)
        if instance and instance.pk and instance.status != ProductionProgram.Status.DRAFT:
            lock_names = [
                'production_info', 'product', 'program_id', 'planned_weight_ton',
                'predicted_start_time', 'predicted_end_time', 'execution_date', 'packaging_type',
                'inventory_snapshot', 'net_unplanned_requirement', 'extra_description'
            ]
            for name in lock_names:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    self.fields[name].widget.attrs['disabled'] = True

    # --- Field-level cleans ---
    def clean_planned_weight_ton(self):
        val = self.cleaned_data.get('planned_weight_ton')
        status = self.data.get('status') or (self.instance.status if self.instance.pk else ProductionProgram.Status.DRAFT)
        if status != ProductionProgram.Status.DRAFT and (not val or val <= 0):
            raise forms.ValidationError('تناژ باید بزرگتر از صفر باشد.')
        return val

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status') or (self.instance.status if self.instance.pk else ProductionProgram.Status.DRAFT)
        required_if_active = [
            'program_id', 'product', 'planned_weight_ton',
            'predicted_start_date', 'predicted_start_time', 'predicted_end_date', 'predicted_end_time',
            'packaging_type'
        ]
        if status != ProductionProgram.Status.DRAFT:
            for fname in required_if_active:
                if not cleaned.get(fname):
                    self.add_error(fname, 'پر کردن این فیلد در وضعیت غیر پیش نویس اجباری است.')
        # DateTime ordering validation
        start_date = cleaned.get('predicted_start_date')
        start_time = cleaned.get('predicted_start_time')
        end_date = cleaned.get('predicted_end_date')
        end_time = cleaned.get('predicted_end_time')
        
        if start_date and start_time and end_date and end_time:
            from datetime import datetime
            try:
                start_greg = start_date.togregorian()
                end_greg = end_date.togregorian()
                start_dt = datetime.combine(start_greg, start_time)
                end_dt = datetime.combine(end_greg, end_time)
                
                if end_dt <= start_dt:
                    self.add_error('predicted_end_date', 'باید بعد از زمان شروع باشد.')
            except Exception:
                pass
        # Produced weight sanity
        pw = cleaned.get('produced_weight_ton')
        if pw is not None and pw < 0:
            self.add_error('produced_weight_ton', 'وزن تولید شده نمی تواند منفی باشد.')
        return cleaned

    def save(self, commit=True):
        instance: ProductionProgram = super().save(commit=False)
        # Preserve original locked values if form disabled fields dropped from POST
        if instance.pk and instance.status != ProductionProgram.Status.DRAFT:
            # Re-fetch from DB for locked fields to avoid accidental overwrite to None
            orig = ProductionProgram.objects.get(pk=instance.pk)
            for attr in [
                'production_info', 'product', 'program_id', 'planned_weight_ton',
                'predicted_start_date', 'predicted_start_time', 'predicted_end_date', 'predicted_end_time',
                'packaging_type', 'inventory_snapshot', 'net_unplanned_requirement', 'extra_description'
            ]:
                setattr(instance, attr, getattr(orig, attr))
        if commit:
            instance.save()
        return instance

