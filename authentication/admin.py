from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.contrib.auth import login
from django.shortcuts import redirect
from .models import UserPhoneNumber

# Unregister the default User admin
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'login_as_user_button')
    actions = ['login_as_user']
    
    def login_as_user_button(self, obj):
        """نمایش دکمه ورود به عنوان کاربر"""
        if obj.pk:
            url = reverse('admin:login_as_user', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">ورود به عنوان این کاربر</a>',
                url
            )
        return "-"
    login_as_user_button.short_description = "ورود به سیستم"
    
    def login_as_user(self, request, queryset):
        """Action برای ورود به عنوان کاربر انتخاب شده"""
        if queryset.count() == 1:
            user = queryset.first()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            self.message_user(request, f'شما با موفقیت به عنوان {user.username} وارد شدید.')
            return HttpResponseRedirect('/CRM/')
        else:
            self.message_user(request, 'لطفاً فقط یک کاربر انتخاب کنید.', level='error')
    
    login_as_user.short_description = "ورود به عنوان کاربران انتخاب شده"
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('login-as-user/<int:user_id>/', self.admin_site.admin_view(self.login_as_user_view), name='login_as_user'),
        ]
        return custom_urls + urls
    
    def login_as_user_view(self, request, user_id):
        """View برای ورود مستقیم به عنوان کاربر"""
        try:
            user = User.objects.get(pk=user_id)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('/home/')
        except User.DoesNotExist:
            return redirect('/admin/auth/user/')

@admin.register(UserPhoneNumber)
class UserPhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_verified', 'created_at')
    search_fields = ('user__username', 'phone_number', 'user__first_name', 'user__last_name')
    list_filter = ('is_verified', 'user__is_active', 'user__is_staff', 'user__is_superuser')
    list_per_page = 25
    list_display_links = ('user', 'phone_number')
    list_select_related = ('user',)
    readonly_fields = ('created_at', 'updated_at')