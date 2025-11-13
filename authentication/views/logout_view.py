from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from authentication.models import UserPhoneNumber
import logging


# ایجاد لاگر برای logout
logger = logging.getLogger("authentication")

def get_client_ip(request):
    """
    دریافت IP کلاینت با پشتیبانی از proxy
    """
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')
    
    client_ip = direct_ip
    if forwarded_for:
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
    
    def is_local_ip(ip):
        if ip == 'Unknown':
            return False
        return (ip.startswith('192.168.') or 
               ip.startswith('10.') or 
               ip.startswith('172.') or 
               ip.startswith('127.') or
               ip == 'localhost')
    
    ip_type = "local" if is_local_ip(client_ip) else "external"
    
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
    
    return f"{client_ip}({ip_type}){proxy_info}"

@login_required
def logout_view(request):
    """
    خروج کاربر از سیستم با logging کامل
    """
    user = request.user
    client_ip = get_client_ip(request)
    username = user.username if user.is_authenticated else "Anonymous"
    user_phone = UserPhoneNumber.objects.filter(user=user).first()
    if user_phone:
        phone_number = user_phone.phone_number
    else:
        phone_number = "-"
    
    # بررسی آیا session ادمین بود
    was_admin_session = request.session.get('is_admin_session', False)
    admin_phone = request.session.get('admin_phone_number', '')
    
    # لاگ خروج
    if was_admin_session:
        logger.debug(f"{phone_number} !@# کاربر ادمین {username} (شماره: {admin_phone}) از سیستم خارج شد - IP: {client_ip}")
    else:
        logger.debug(f"{phone_number} !@# کاربر {username} از سیستم خارج شد - IP: {client_ip} - شماره تلفن: {phone_number}")

    # پاک کردن session های ادمین قبل از logout
    if was_admin_session:
        request.session.pop('is_admin_session', None)
        request.session.pop('admin_phone_number', None)
        request.session.pop('admin_access_allowed', None)
    
    # پاک کردن شماره تلفن ورود
    request.session.pop('logged_in_phone_number', None)

    # خروج از سیستم
    logout(request)
    
    # پیام موفقیت
    messages.success(request, "شما با موفقیت از سیستم خارج شدید")
    
    # هدایت به صفحه لاگین
    return redirect('unified_login')
