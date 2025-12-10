from django.contrib import admin
from .CompanyInfoModel import CompanyInfo


@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    """
    پنل ادمین برای اطلاعات شرکت
    """
    list_display = ['name', 'national_id', 'registration_number', 'economic_code', 'phone_number', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['name', 'national_id', 'registration_number', 'economic_code']
    
    fieldsets = (
        ('اطلاعات پایه', {
            'fields': ('name', 'national_id', 'registration_number', 'economic_code')
        }),
        ('اطلاعات تماس', {
            'fields': ('phone_number', 'fax_number', 'email', 'website')
        }),
        ('آدرس', {
            'fields': ('address', 'postal_code')
        }),
        ('اطلاعات مالیاتی', {
            'fields': ('tax_province', 'tax_city', 'tax_address', 'tax_postal_code')
        }),
        ('ملاحظات', {
            'fields': ('proforma_notes', 'invoice_notes'),
            'description': 'این ملاحظات به صورت پیش‌فرض در فرم‌های صدور پیش فاکتور و فاکتور نمایش داده می‌شوند'
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def has_add_permission(self, request):
        """
        فقط اگر رکوردی وجود نداشته باشد، اجازه اضافه کردن بده
        """
        if CompanyInfo.objects.exists():
            return False
        return super().has_add_permission(request)
    
    def has_delete_permission(self, request, obj=None):
        """
        اجازه حذف نده (چون singleton است)
        """
        return False

