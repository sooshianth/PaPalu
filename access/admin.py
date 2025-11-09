from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from .models import FieldAccessRule


@admin.register(FieldAccessRule)
class FieldAccessRuleAdmin(admin.ModelAdmin):
    list_display = [
        'user', 
        'content_type', 
        'field_name', 
        'access_type', 
        'allowed',
        'created_at'
    ]
    
    list_filter = [
        'access_type', 
        'allowed', 
        'content_type',
        'created_at'
    ]
    
    search_fields = [
        'user__username', 
        'user__email',
        'field_name'
    ]
    
    autocomplete_fields = ['user']
    
    fieldsets = (
        ('اطلاعات کاربر و مدل', {
            'fields': ('user', 'content_type', 'field_name')
        }),
        ('تنظیمات دسترسی', {
            'fields': ('access_type', 'allowed')
        }),
        ('اطلاعات زمانی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'content_type')
    
    class Media:
        css = {
            'all': ('admin/css/forms.css',)
        }
