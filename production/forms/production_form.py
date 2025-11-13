from django import forms
from core.ProductionFolder.ProductionProgramModel import ProductionProgram


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
    formula_id = forms.CharField(
        max_length=100,
        required=False,
        label='شناسه فرمول',
        widget=forms.TextInput(attrs={'class': 'form-control', 'dir': 'ltr'})
    )
    planned_weight_ton = forms.DecimalField(
        max_digits=12, decimal_places=3,
        required=False,
        label='تناژ برنامه (تن)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    predicted_start_time = forms.DateTimeField(
        required=False,
        label='شروع پیشبینی شده',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    predicted_end_time = forms.DateTimeField(
        required=False,
        label='پایان پیشبینی شده',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    execution_date = forms.DateField(
        required=False,
        label='تاریخ اجرای برنامه',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
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
    started_at = forms.DateTimeField(
        required=False,
        label='زمان شروع واقعی',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    completed_at = forms.DateTimeField(
        required=False,
        label='زمان تکمیل',
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    status = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = ProductionProgram
        fields = [
            'production_info', 'product', 'formula_id', 'planned_weight_ton',
            'predicted_start_time', 'predicted_end_time', 'execution_date', 'packaging_type', 'extra_description',
            'inventory_snapshot', 'net_unplanned_requirement', 'produced_weight_ton',
            'started_at', 'completed_at', 'status'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the current status
        instance: ProductionProgram | None = getattr(self, 'instance', None)
        status = instance.status if instance and instance.pk else ProductionProgram.Status.DRAFT

        # All main fields (cannot edit when confirmed)
        main_field_names = [
            'production_info', 'product', 'formula_id', 'planned_weight_ton',
            'predicted_start_time', 'predicted_end_time', 'execution_date', 'packaging_type',
            'inventory_snapshot', 'net_unplanned_requirement', 'extra_description'
        ]

        if status == ProductionProgram.Status.DRAFT:
            # In draft: make snapshot fields readonly
            for name in ['inventory_snapshot', 'net_unplanned_requirement']:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
            # Hide time fields in draft
            self.fields['started_at'].widget = forms.HiddenInput()
            self.fields['completed_at'].widget = forms.HiddenInput()

        # Lock/hide main fields when status is confirmed or higher
        elif status == ProductionProgram.Status.CONFIRMED:
            # Can't edit anything, only view
            for name in main_field_names:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    self.fields[name].widget.attrs['disabled'] = True
            # For time fields, only use readonly (no disabled) so values get sent in POST
            for name in ['started_at', 'completed_at']:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    # Do NOT set disabled for these fields

        elif status == ProductionProgram.Status.IN_PROGRESS:
            # Lock main planning fields
            for name in main_field_names:
                if name in self.fields:
                    self.fields[name].widget.attrs['readonly'] = True
                    self.fields[name].widget.attrs['disabled'] = True
            # Can edit started_at
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
            # Lock started_at but show it (readonly but not disabled)
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

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status') or (self.instance.status if self.instance.pk else ProductionProgram.Status.DRAFT)
        
        # No mandatory validation for now as per user request
        
        # Time ordering (only validate if fields are not readonly)
        ps = cleaned.get('predicted_start_time')
        pe = cleaned.get('predicted_end_time')
        if ps and pe and pe <= ps:
            # Check if fields are not readonly before adding error
            if 'predicted_end_time' not in self.fields or not self.fields['predicted_end_time'].widget.attrs.get('readonly'):
                self.add_error('predicted_end_time', 'باید بعد از زمان شروع باشد.')
        
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
                'production_info', 'product', 'formula_id', 'planned_weight_ton', 'predicted_start_time',
                'predicted_end_time', 'execution_date', 'packaging_type', 'inventory_snapshot', 'net_unplanned_requirement', 'extra_description'
            ]
            
            # If status is not DRAFT, preserve all main fields from database
            if instance.status != ProductionProgram.Status.DRAFT:
                for attr in main_field_names:
                    # Restore the original value from DB regardless of form field state
                    current_val = getattr(instance, attr, None)
                    # If field is empty/None, restore from original
                    if not current_val:
                        setattr(instance, attr, getattr(orig, attr))
            
            # Also preserve started_at when not in IN_PROGRESS or COMPLETED
            if instance.status not in [ProductionProgram.Status.IN_PROGRESS, ProductionProgram.Status.COMPLETED]:
                if not instance.started_at:  # only if not explicitly set
                    instance.started_at = getattr(orig, 'started_at')
            
            # Also preserve completed_at when not COMPLETED
            if instance.status != ProductionProgram.Status.COMPLETED:
                if not instance.completed_at:  # only if not explicitly set
                    instance.completed_at = getattr(orig, 'completed_at')
        
        if commit:
            instance.save()
        return instance
