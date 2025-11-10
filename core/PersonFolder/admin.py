from django.contrib import admin
from . import (
    Person, PhoneNumber, DeliveryAddress, BankAccount, FinancialBanking,
    PaymentPreference, PurchasePreference, Representative, SocialNetwork, Attachment
)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['national_id', 'name', 'type', 'nature', 'accounting_code', 'sales_expert']
    list_filter = ['type', 'nature', 'user_type']
    search_fields = ['national_id', 'name', 'accounting_code', 'registration_number']
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('national_id', 'name', 'type', 'nature', 'accounting_code')
        }),
        ('اطلاعات تکمیلی', {
            'fields': ('registration_number', 'birth_date', 'user_type', 'sales_expert', 'introducer')
        }),
        ('توضیحات', {
            'fields': ('description',)
        }),
    )


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
