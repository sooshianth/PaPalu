from django.contrib import admin
from django.core.exceptions import ValidationError
from . import (
    Person, PhoneNumber, DeliveryAddress, BankAccount, FinancialBanking,
    PaymentPreference, PurchasePreference, Representative, SocialNetwork, Attachment
)
from .PersonModel import ActivityField


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['national_id', 'name', 'type', 'nature', 'accounting_code', 'sales_expert', 'warehouse']
    list_filter = ['type', 'nature', 'activity_fields', 'warehouse']
    search_fields = ['national_id', 'name', 'accounting_code', 'registration_number']
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('national_id', 'name', 'type', 'nature', 'accounting_code')
        }),
        ('اطلاعات تکمیلی', {
            'fields': ('registration_number', 'birth_date', 'activity_fields', 'sales_expert', 'introducer')
        }),
        ('انبار', {
            'fields': ('warehouse',),
            'description': 'برای مشتریان، نوع انبار باید مصرف‌کننده باشد'
        }),
        ('توضیحات', {
            'fields': ('description',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """اعتبارسنجی: اگر شخص مشتری است، نوع انبار باید consumer باشد"""
        if obj.type == 'customer' and obj.warehouse:
            if obj.warehouse.warehouse_type != 'consumer':
                raise ValidationError(
                    'برای مشتریان، نوع انبار باید "مصرف‌کننده" باشد. '
                    f'انبار انتخاب شده از نوع "{obj.warehouse.get_warehouse_type_display()}" است.'
                )
        super().save_model(request, obj, form, change)


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ['number', 'phone_type', 'is_primary']
    list_filter = ['phone_type', 'is_primary']
    search_fields = ['number']


@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ['postal_code', 'recipient_name']
    search_fields = ['postal_code', 'recipient_name']


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(FinancialBanking)
class FinancialBankingAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(PaymentPreference)
class PaymentPreferenceAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(PurchasePreference)
class PurchasePreferenceAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(Representative)
class RepresentativeAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(SocialNetwork)
class SocialNetworkAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(ActivityField)
class ActivityFieldAdmin(admin.ModelAdmin):
    list_display = ['code', '__str__']
    search_fields = ['code']
