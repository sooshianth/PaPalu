from django import forms
from core.AllocationFolder.AllocationModel import Allocation


class ShippingAnnouncementForm(forms.Form):
    """فرم اعلام بار برای انتخاب تخصیص‌ها و شیوه اعلام بار"""
    
    allocation_numbers = forms.MultipleChoiceField(
        choices=[],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=True,
        label='تخصیص‌های انتخاب شده'
    )
    
    shipping_method = forms.ChoiceField(
        choices=Allocation.SHIPPING_METHOD_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        required=True,
        label='شیوه اعلام بار'
    )
    
    def __init__(self, *args, **kwargs):
        allocations = kwargs.pop('allocations', None)
        super().__init__(*args, **kwargs)
        
        if allocations:
            self.fields['allocation_numbers'].choices = [
                (alloc.allocation_number, f"{alloc.allocation_number} - {alloc.order.order_number if alloc.order else 'بدون سفارش'}")
                for alloc in allocations
            ]

