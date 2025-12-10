from django import forms
from core.ProductFolder.ProductModel import Product


class CargoAnnouncementForm(forms.Form):
    """فرم اعلام بار مطابق قوانین و UI در تصویر.

    - شیوه اعلام بار: اجباری (ماشین مشتری / باربری)
    - اقلام انتخابی: در فیلد مخفی JSON توسط UI تامین می‌شود
    - توضیحات اختیاری
    """

    METHOD_CHOICES = [
        ("customer_truck", "ماشین مشتری"),
        ("carrier", "باربری")
    ]

    method = forms.ChoiceField(
        label="شیوه اعلام بار",
        choices=METHOD_CHOICES,
        widget=forms.RadioSelect
    )

    # For convenience allow adding a single quick row too (optional)
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        required=False,
        label="محصول"
    )
    quantity = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        label="مقدار (کیلوگرم)"
    )

    items_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        label="اقلام انتخابی (JSON)"
    )

    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="توضیحات"
    )

    def clean(self):
        cleaned = super().clean()
        items_json = cleaned.get("items_json")
        product = cleaned.get("product")
        quantity = cleaned.get("quantity")

        if not items_json and not (product and quantity):
            raise forms.ValidationError("حداقل یک قلم برای اعلام بار انتخاب کنید.")

        return cleaned
