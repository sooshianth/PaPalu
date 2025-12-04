from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps
from django.contrib import messages


def is_admin(user):
    """
    تشخیص اینکه کاربر یک ادمین یا سوپر یوزر است
    """
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def admin_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص ادمین
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_admin(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط مدیران سیستم به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view
    
    if function:
        return actual_decorator(function)
    return actual_decorator

# دکوراتور پیشرفته برای دسترسی چند نقشی
def role_required(*roles, redirect_url='/', message='دسترسی محدود است'):
    """
    دکوراتور برای دسترسی چند نقشی
    مثال استفاده: @role_required('sales_agent', 'admin', redirect_url='/access-denied/', message='دسترسی محدود است')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            allowed = False
            
            for role in roles:
                if role == 'admin' and is_admin(request.user):
                    allowed = True
                    break

            if allowed:
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'شما دسترسی لازم برای این صفحه را ندارید'
                messages.error(request, error_message)
                return redirect(redirect_url)
                
        return _wrapped_view
    
    # این بررسی برای حالتی است که کاربر پارامتر message یا redirect_url را تعیین کرده باشد
    if len(roles) == 1 and callable(roles[0]):
        view_func = roles[0]
        roles = []
        return decorator(view_func)
    
    return decorator 