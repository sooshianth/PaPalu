from django import forms
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from django_jalali.forms import jDateField
from django_jalali.forms.widgets import jDateTimeInput
from django.utils import timezone
import jdatetime


class ProductionForm(forms.ModelForm):
    """فرم تولید با فیلدهای زمان شروع و تکمیل واقعی برای گردش وضعیت.

    قوانین گردش وضعیت:
      - وضعیت تایید شده: فقط می‌توان start کرد، هیچ ویرایشی ممکن نیست.
      - وضعیت در حال اجرا: می‌توان زمان شروع واقعی و وزن تولید شده را ویرایش کرد.
      - وضعیت تکمیل شده: می‌توان زمان تکمیل و وزن تولید شده را ویرایش کرد.
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
    execution_date = jDateField(
        required=False,
        label='تاریخ اجرای برنامه',
        widget=forms.TextInput(attrs={'class': 'form-control jalali-date-input', 'dir': 'ltr', 'placeholder': '1403-08-29'})
    )
    # Custom datetime fields (will be split into date + time fields)
    predicted_start_datetime = forms.CharField(
        required=False,
        label='شروع پیشبینی شده',
        widget=forms.HiddenInput()
    )
    predicted_end_datetime = forms.CharField(
        required=False,
        label='پایان پیشبینی شده',
        widget=forms.HiddenInput()
    )
    predicted_end_date = jDateField(
        required=False,
        label='تاریخ پایان پیشبینی شده',
        widget=forms.TextInput(attrs={'class': 'form-control jalali-date-input', 'dir': 'ltr', 'placeholder': '1403-08-29'})
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
    actual_start_date = jDateField(
        required=False,
        label='تاریخ شروع واقعی',
        widget=forms.TextInput(attrs={'class': 'form-control jalali-date-input', 'dir': 'ltr', 'placeholder': '1403-08-29'})
    )
    started_at = forms.TimeField(
        required=False,
        label='زمان شروع واقعی',
        widget=forms.TimeInput(attrs={'class': 'form-control time-picker-input', 'type': 'text', 'placeholder': 'HH:MM'})
    )
    completed_at = forms.TimeField(
        required=False,
        label='زمان تکمیل',
        widget=forms.TimeInput(attrs={'class': 'form-control time-picker-input', 'type': 'text', 'placeholder': 'HH:MM'})
    )
    status = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = ProductionProgram
        fields = [
            'production_info', 'product', 'program_id', 'planned_weight_ton',
            'execution_date', 'predicted_start_time', 'predicted_end_time', 'packaging_type', 'extra_description',
            'inventory_snapshot', 'net_unplanned_requirement', 'produced_weight_ton',
            'actual_start_date', 'started_at', 'completed_at', 'status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the current status
        instance: ProductionProgram | None = getattr(self, 'instance', None)
        status = instance.status if instance and instance.pk else ProductionProgram.Status.DRAFT
        
        # Override time field widgets to use text input for time picker
        if 'predicted_start_time' in self.fields:
            self.fields['predicted_start_time'].widget = forms.TimeInput(attrs={
                'class': 'form-control time-picker-input',
                'type': 'text',
                'placeholder': 'HH:MM'
            })
        if 'predicted_end_time' in self.fields:
            self.fields['predicted_end_time'].widget = forms.TimeInput(attrs={
                'class': 'form-control time-picker-input',
                'type': 'text',
                'placeholder': 'HH:MM'
            })
        
        # Set initial values for datetime fields from model's time fields
        if instance and instance.pk:
            # For start: use execution_date
            if instance.execution_date:
                self.fields['execution_date'].initial = instance.execution_date
            
            # For end: use execution_date as default (or we could add a separate field in model later)
            if instance.execution_date:
                self.fields['predicted_end_date'].initial = instance.execution_date

        # All main fields (cannot edit when confirmed)
        main_field_names = [
            'production_info', 'product', 'program_id', 'planned_weight_ton',
            'predicted_start_datetime', 'predicted_end_datetime', 'predicted_end_date', 'execution_date', 'packaging_type',
            'inventory_snapshot', 'net_unplanned_requirement', 'extra_description'
        ]

        if status == ProductionProgram.Status.DRAFT:
            # In draft: make snapshot fields readonly
            for name in ['inventory_snapshot', 'net_unplanned_requirement']:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
            # Hide actual date/time fields in draft
            self.fields['actual_start_date'].widget = forms.HiddenInput()
            self.fields['started_at'].widget = forms.HiddenInput()
            self.fields['completed_at'].widget = forms.HiddenInput()

        # Lock/hide main fields when status is confirmed or higher
        elif status == ProductionProgram.Status.CONFIRMED:
            # Can't edit anything, only view
            for name in main_field_names:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    self.fields[name].widget.attrs['disabled'] = True
            # For actual date/time fields, only use readonly (no disabled) so values get sent in POST
            for name in ['actual_start_date', 'started_at', 'completed_at']:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    # Do NOT set disabled for these fields

        elif status == ProductionProgram.Status.IN_PROGRESS:
            # Lock main planning fields
            for name in main_field_names:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    self.fields[name].widget.attrs['disabled'] = True
            # Can edit actual_start_date and started_at
            self.fields['actual_start_date'].widget.attrs.pop('disabled', None)
            self.fields['actual_start_date'].widget.attrs.pop('readonly', None)
            self.fields['started_at'].widget.attrs.pop('disabled', None)
            self.fields['started_at'].widget.attrs.pop('readonly', None)
            # Lock completed_at (readonly but not disabled)
            self.fields['completed_at'].widget.attrs['readonly'] = True
            self.fields['completed_at'].widget.attrs.pop('disabled', None)

        elif status == ProductionProgram.Status.COMPLETED:
            # Lock main planning fields
            for name in main_field_names:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    self.fields[name].widget.attrs['disabled'] = True
            # Can edit produced_weight_ton and completed_at
            self.fields['produced_weight_ton'].widget.attrs.pop('disabled', None)
            self.fields['produced_weight_ton'].widget.attrs.pop('readonly', None)
            self.fields['completed_at'].widget.attrs.pop('disabled', None)
            self.fields['completed_at'].widget.attrs.pop('readonly', None)
            # Lock actual_start_date and started_at but show them (readonly but not disabled)
            self.fields['actual_start_date'].widget.attrs['readonly'] = True
            self.fields['actual_start_date'].widget.attrs.pop('disabled', None)
            self.fields['started_at'].widget.attrs['readonly'] = True
            self.fields['started_at'].widget.attrs.pop('disabled', None)

    # --- Field-level cleans ---
    def clean_planned_weight_ton(self):
        val = self.cleaned_data.get('planned_weight_ton')
        # Skip validation if field is readonly (locked due to status)
        if 'planned_weight_ton' in self.fields and self.fields['planned_weight_ton'].widget.attrs.get('readonly'):
            return val
        status = self.data.get('status') or (self.instance.status if self.instance.pk else ProductionProgram.Status.DRAFT)
        if status != ProductionProgram.Status.DRAFT and (not val or val <= 0):
            raise forms.ValidationError('تناژ باید بزرگتر از صفر باشد.')
        return val

    def clean_predicted_start_datetime(self):
        """Parse datetime string and extract time component"""
        datetime_str = self.cleaned_data.get('predicted_start_datetime', '').strip()
        if not datetime_str:
            return None
        
        try:
            # Parse jalali datetime string (format: YYYY-MM-DD HH:MM)
            parts = datetime_str.split()
            if len(parts) >= 2:
                date_str = parts[0]
                time_str = parts[1]
                # Parse jalali date
                year, month, day = map(int, date_str.split('-'))
                jdate = jdatetime.date(year, month, day)
                # Convert to gregorian
                gdate = jdate.togregorian()
                # Parse time
                hour, minute = map(int, time_str.split(':'))
                from datetime import datetime, time
                time_obj = time(hour, minute)
                # Store time in predicted_start_time field
                self.cleaned_data['predicted_start_time'] = time_obj
                # Store date in execution_date if not set
                if not self.cleaned_data.get('execution_date'):
                    self.cleaned_data['execution_date'] = jdate
                return datetime_str
            else:
                raise forms.ValidationError('فرمت تاریخ و زمان نامعتبر است. فرمت صحیح: 1403-08-29 14:30')
        except (ValueError, AttributeError) as e:
            raise forms.ValidationError(f'فرمت تاریخ و زمان نامعتبر است: {str(e)}')

    def clean_predicted_end_datetime(self):
        """Parse datetime string and extract time component"""
        datetime_str = self.cleaned_data.get('predicted_end_datetime', '').strip()
        if not datetime_str:
            # Try to get from separate date and time fields
            end_date = self.cleaned_data.get('predicted_end_date')
            end_time = self.cleaned_data.get('predicted_end_time')
            if end_date and end_time:
                # Combine them
                datetime_str = f"{end_date.year:04d}-{end_date.month:02d}-{end_date.day:02d} {end_time.hour:02d}:{end_time.minute:02d}"
                return datetime_str
            return None
        
        try:
            # Parse jalali datetime string (format: YYYY-MM-DD HH:MM)
            parts = datetime_str.split()
            if len(parts) >= 2:
                date_str = parts[0]
                time_str = parts[1]
                # Parse jalali date
                year, month, day = map(int, date_str.split('-'))
                jdate = jdatetime.date(year, month, day)
                # Store date in predicted_end_date if not already set
                if not self.cleaned_data.get('predicted_end_date'):
                    self.cleaned_data['predicted_end_date'] = jdate
                # Parse time
                hour, minute = map(int, time_str.split(':'))
                from datetime import time
                time_obj = time(hour, minute)
                # Store time in predicted_end_time field
                self.cleaned_data['predicted_end_time'] = time_obj
                return datetime_str
            else:
                raise forms.ValidationError('فرمت تاریخ و زمان نامعتبر است. فرمت صحیح: 1403-08-29 18:30')
        except (ValueError, AttributeError) as e:
            raise forms.ValidationError(f'فرمت تاریخ و زمان نامعتبر است: {str(e)}')

    def clean(self):
        cleaned = super().clean()
        instance = getattr(self, 'instance', None)
        is_create = instance is None or not instance.pk
        status = cleaned.get('status') or (instance.status if instance and instance.pk else ProductionProgram.Status.DRAFT)
        
        # Required field validation for new programs (draft status)
        if is_create or status == ProductionProgram.Status.DRAFT:
            required_fields = {
                'product': 'محصول',
                'production_info': 'اطلاعات فرمول',
                'program_id': 'شناسه برنامه',
                'planned_weight_ton': 'تناژ برنامه',
                'packaging_type': 'نوع بسته بندی',
            }
            
            for field_name, field_label in required_fields.items():
                if field_name not in self.fields:
                    continue
                # Skip if field is readonly (shouldn't happen in draft, but check anyway)
                if self.fields[field_name].widget.attrs.get('readonly'):
                    continue
                
                value = cleaned.get(field_name)
                if not value or (isinstance(value, str) and not value.strip()):
                    self.add_error(field_name, f'{field_label} الزامی است.')
            
            # Validate datetime fields (check both date and time components)
            # For start: execution_date + predicted_start_time
            if not cleaned.get('execution_date'):
                self.add_error('execution_date', 'تاریخ شروع پیشبینی شده الزامی است.')
            if not cleaned.get('predicted_start_time'):
                self.add_error('predicted_start_time', 'زمان شروع پیشبینی شده الزامی است.')
            
            # For end: predicted_end_date + predicted_end_time
            if not cleaned.get('predicted_end_date'):
                self.add_error('predicted_end_date', 'تاریخ پایان پیشبینی شده الزامی است.')
            if not cleaned.get('predicted_end_time'):
                self.add_error('predicted_end_time', 'زمان پایان پیشبینی شده الزامی است.')
        
        # Time ordering validation (only validate if fields are not readonly)
        ps = cleaned.get('predicted_start_time')
        pe = cleaned.get('predicted_end_time')
        if ps and pe:
            # Compare times
            from datetime import datetime, date
            ps_dt = datetime.combine(date.today(), ps)
            pe_dt = datetime.combine(date.today(), pe)
            if pe_dt <= ps_dt:
                # Check if fields are not readonly before adding error
                if 'predicted_end_datetime' not in self.fields or not self.fields['predicted_end_datetime'].widget.attrs.get('readonly'):
                    self.add_error('predicted_end_datetime', 'زمان پایان باید بعد از زمان شروع باشد.')
        
        # For readonly decimal fields that might be empty, set them to None
        for field_name in ['planned_weight_ton', 'inventory_snapshot', 'net_unplanned_requirement']:
            if field_name in self.fields and self.fields[field_name].widget.attrs.get('readonly'):
                if cleaned.get(field_name) == '':
                    cleaned[field_name] = None
        
        return cleaned

    def save(self, commit=True):
        instance: ProductionProgram = super().save(commit=False)
        # Preserve original locked values if form disabled fields dropped from POST
        if instance.pk:
            # Re-fetch from DB for locked fields to avoid accidental overwrite to None
            orig = ProductionProgram.objects.get(pk=instance.pk)
            
            # List of all main fields that should be locked when not in draft
            main_field_names = [
                'production_info', 'product', 'program_id', 'planned_weight_ton', 'predicted_start_datetime',
                'predicted_end_datetime', 'predicted_end_date', 'execution_date', 'packaging_type', 'inventory_snapshot', 'net_unplanned_requirement', 'extra_description'
            ]
            
            # If status is not DRAFT, preserve all main fields from database
            if instance.status != ProductionProgram.Status.DRAFT:
                for attr in main_field_names:
                    # Restore the original value from DB regardless of form field state
                    current_val = getattr(instance, attr, None)
                    # If field is empty/None, restore from original
                    if not current_val:
                        setattr(instance, attr, getattr(orig, attr))
            
            # Also preserve actual_start_date and started_at when not in IN_PROGRESS or COMPLETED
            if instance.status not in [ProductionProgram.Status.IN_PROGRESS, ProductionProgram.Status.COMPLETED]:
                if not instance.actual_start_date:
                    instance.actual_start_date = getattr(orig, 'actual_start_date')
                if not instance.started_at:
                    instance.started_at = getattr(orig, 'started_at')
            
            # Also preserve completed_at when not COMPLETED
            if instance.status != ProductionProgram.Status.COMPLETED:
                if not instance.completed_at:
                    instance.completed_at = getattr(orig, 'completed_at')
        
        if commit:
            instance.save()
        return instance
