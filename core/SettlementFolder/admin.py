from django.contrib import admin
from . import Settlement, TransactionDocument


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = ['id']


@admin.register(TransactionDocument)
class TransactionDocumentAdmin(admin.ModelAdmin):
    list_display = ['accounting_document_number', 'settlement']
    search_fields = ['accounting_document_number']
