from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
try:
    from sms_ir import SmsIr  # External SMS provider
except ImportError:  # Graceful degradation if library not installed during dev/migrations
    SmsIr = None
from django.core.cache import cache
import time
from django.conf import settings
import string
import random
import logging
from core.logging_levels import *

# ایجاد لاگر برای ثبت رویدادها
logger = logging.getLogger("bugs")
auth_logger = logging.getLogger("authentication")

def generate_unique_username():
    """
    تولید یک username یکتا بر اساس کلمات فارسی + عدد تصادفی
    """
    # کلمات پایه فارسی برای username
    persian_words = [
        'کاربر'
    ]
    
    base_word = random.choice(persian_words)
    random_number = random.randint(10000, 99999)
    username = f"{base_word}_{random_number}"
    
    # بررسی یکتا بودن username
    counter = 1
    original_username = username
    while User.objects.filter(username=username).exists():
        username = f"{original_username}_{counter}"
        counter += 1
        # جلوگیری از loop بی‌نهایت
        if counter > 100:
            username = f"{base_word}_{random.randint(100000, 999999)}"
            break
    
    return username

def create_user_for_phone(phone_number: str, customer_info: dict = None) -> User:
    """
    ایجاد کاربر جدید برای شماره تلفن
    
    Args:
        phone_number (str): شماره تلفن
        customer_info (dict): اطلاعات اضافی مشتری از API
        
    Returns:
        User: کاربر ایجاد شده
    """
    from authentication.models import UserPhoneNumber
    
    # تولید username یکتا
    username = generate_unique_username()
    
    # استخراج نام از اطلاعات مشتری (در صورت وجود)
    first_name = ""
    last_name = ""
    
    if customer_info and customer_info.get('customers'):
        # گرفتن نام اولین مشتری
        customer_name = customer_info['customers'][0].get('name', '')
        if customer_name:
            name_parts = customer_name.strip().split()
            if len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
            elif len(name_parts) == 1:
                first_name = name_parts[0]
                last_name = "مشتری"
            else:
                first_name = "کاربر"
                last_name = "گرامی"
        else:
            first_name = "کاربر"
            last_name = "گرامی"
    else:
        first_name = "کاربر"
        last_name = "گرامی"
    
    # بررسی آیا این شماره در لیست ادمین‌ها است
    is_admin_number = phone_number in getattr(settings, 'ADMIN_PHONE_NUMBERS', [])
    
    # ایجاد کاربر
    user = User.objects.create_user(
        username=username,
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        is_superuser=is_admin_number,
        is_staff=is_admin_number
    )
    
    # ایجاد رکورد UserPhoneNumber
    UserPhoneNumber.objects.create(
        user=user,
        phone_number=phone_number,
        is_verified=True
    )
    
    auth_logger.debug(f"{phone_number} !@# کاربر جدید با username={username} برای شماره {phone_number} ایجاد شد")
    
    return user

def send_verify_code(number:str):
    """
    ارسال کد تایید به شماره تلفن
    """
    # تولید کد تصادفی 6 رقمی
    import random
    code = str(random.randint(100000, 999999))

    # در حالت دیباگ، از ارسال واقعی پیامک صرف‌نظر می‌شود تا در محیط توسعه مشکلی پیش نیاید
    if settings.DEBUG:
        logger.debug(f"{number} !@# DEBUG MODE: SMS not sent for {number}. The code is: {code}")
        return code, True

    # If SMS library missing, skip real send (useful for local dev / migrations)
    if SmsIr is None:
        logger.warning(f"{number} !@# sms_ir library not installed; returning generated code without sending")
        return code, False

    api_key = getattr(settings, 'SMS_API_KEY', None)
    linenumber = getattr(settings, 'SMS_LINE_NUMBER', None)
    if not api_key or not linenumber:
        logger.warning(f"{number} !@# SMS credentials missing; returning code without sending")
        return code, False
    sms_account = SmsIr(api_key, linenumber)
    
    message = f"کد ورود به سیمرغ افزار : \n  {code}  \n پشتیبانی: 021-66562216"
    try:
        # تبدیل شماره به صورت عدد صحیح برای API
        response = sms_account.send_sms(number, message)
        auth_logger.debug(f"{number} !@# کد تایید برای شماره {number} با موفقیت ارسال شد")
        return code, True
    except Exception as e:
        auth_logger.warning(f"{number} !@# خطا در ارسال پیامک: {e}")
        logger.warning(f"{number} !@# خطا در ارسال پیامک: {e}")
        # کد را برگردان حتی اگر پیامک ارسال نشد
        return code, False


class OTPLoginForm(forms.Form):
    phone_number = forms.CharField(
        max_length=11, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500', 
            'placeholder': '09123456789', 
            'dir': 'rtl',
            'pattern': '[0-9]{11}',
            'title': 'شماره موبایل باید 11 رقم باشد',
            'style': 'text-align: right; padding: 0.75rem; border: 1px solid #e2e8f0; transition: all 0.3s;',
            'autocomplete': 'tel'
        })
    )
    verification_code = forms.CharField(
        max_length=6, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control digit-input rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500', 
            'placeholder': 'کد 6 رقمی', 
            'dir': 'rtl',
            'pattern': '[0-9]{6}',
            'title': 'کد تایید باید 6 رقم باشد',
            'autocomplete': 'one-time-code',
            'style': 'text-align: center; letter-spacing: 0.5em; font-size: 1.25rem; padding: 0.75rem; border: 1px solid #e2e8f0; transition: all 0.3s;'
        })
    )
    
    def __init__(self, *args, **kwargs):
        verification_step = kwargs.pop('verification_step', False)
        super().__init__(*args, **kwargs)
        
        # مخفی کردن فیلد کد تایید در مرحله اول
        if not verification_step:
            self.fields['verification_code'].widget = forms.HiddenInput()
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        # اعتبارسنجی پایه برای شماره موبایل ایرانی
        if not phone.isdigit() or not phone.startswith('09') or len(phone) != 11:
            raise forms.ValidationError("شماره موبایل معتبر نیست. لطفا یک شماره ۱۱ رقمی با فرمت ۰۹xxxxxxxx وارد کنید")
        return phone

    def send_otp(self,request):
        phone = self.cleaned_data.get('phone_number')
        
        # بررسی دوره انتظار فعال
        cooldown_key = f"cooldown_{phone}"
        cooldown_expires_key = f"cooldown_expires_{phone}"
        
        if cache.get(cooldown_key):
            # دریافت زمان انقضا
            expires_at = cache.get(cooldown_expires_key, 0)
            current_time = int(time.time())
            remaining_seconds = max(1, expires_at - current_time)
            
            response = {
                'success': False,
                'message': f"لطفا {remaining_seconds} ثانیه صبر کنید تا بتوانید مجددا درخواست کد تایید نمایید",
                'remaining_seconds': remaining_seconds
            }
            return response
            
        if phone:
            the_ip = self.get_client_ip(request)
            phone_check_attempt_keys = f"phone_check_attempt_keys_{the_ip}"
            current_phone_check_attempts = cache.get(phone_check_attempt_keys, 0)
            if current_phone_check_attempts >= 10:
                cache.set(phone_check_attempt_keys, current_phone_check_attempts + 1, timeout=300)
                auth_logger.alert(f"{phone} !@# بیش از حد مجاز برای وارد کردن شماره معتبر تلاش کرده‌اید. {current_phone_check_attempts + 1}")
                response = {
                    'success': False,
                    'message': 'شما بیش از حد مجاز برای وارد کردن شماره معتبر تلاش کرده‌اید. لطفا بعداً تلاش کنید.'
                }
                return response

            # بررسی آیا شماره در لیست ادمین‌ها است
            is_admin_number = phone in getattr(settings, 'ADMIN_PHONE_NUMBERS', [])
            
            # بررسی وجود شماره در دیتابیس محلی
            existing_user = self.find_user_by_phone(phone)
            
            # اگر شماره ادمین است، اجازه بده حتی اگر در دیتابیس نباشد
            if is_admin_number:
                auth_logger.debug(f"{phone} !@# شماره ادمین تشخیص داده شد")
                
                # اگر کاربر وجود ندارد، ایجاد کن
                if not existing_user:
                    auth_logger.debug(f"{phone} !@# ایجاد کاربر ادمین جدید برای شماره {phone}")
                    try:
                        # ایجاد کاربر ادمین با اطلاعات پیش‌فرض
                        validation_result = {
                            'success': True,
                            'has_access': True,
                            'customers_count': 1,
                            'customers': [{'name': 'ادمین سیستم'}],
                            'is_admin': True
                        }
                        new_user = create_user_for_phone(phone, validation_result)
                        auth_logger.debug(f"{phone} !@# کاربر ادمین جدید با موفقیت ایجاد شد: {new_user.username}")
                        existing_user = new_user
                    except Exception as e:
                        logger.error(f"{phone} !@# خطا در ایجاد کاربر ادمین جدید برای شماره {phone}: {str(e)}")
                        return {
                            'success': False,
                            'message': 'خطا در ایجاد حساب کاربری. لطفا بعداً تلاش کنید.'
                        }
                else:
                    # اگر کاربر موجود است، مطمئن شو که superuser است
                    if not existing_user.is_superuser or not existing_user.is_staff:
                        existing_user.is_superuser = True
                        existing_user.is_staff = True
                        existing_user.save()
                        auth_logger.debug(f"{phone} !@# کاربر موجود {existing_user.username} به superuser تبدیل شد")
            else:
                # برای شماره‌های عادی، باید در دیتابیس وجود داشته باشد
                if not existing_user:
                    auth_logger.activity(f"{phone} !@# شماره {phone} در سیستم ثبت نشده است")
                    cache.set(phone_check_attempt_keys, current_phone_check_attempts + 1, timeout=300)
                    return {
                        'success': False,
                        'message': 'شماره موبایل شما در سیستم ثبت نشده است. لطفا با پشتیبانی تماس بگیرید.'
                    }
                else:
                    # اگر کاربر موجود است، مطمئن شو که superuser نیست (اگر قبلاً بود)
                    if existing_user.is_superuser or existing_user.is_staff:
                        existing_user.is_superuser = False
                        existing_user.is_staff = False
                        existing_user.save()
                        auth_logger.alert(f"{phone} !@# دسترسی superuser برای کاربر {existing_user.username} غیرفعال شد")
            
            # اگر شماره معتبر است، کد تایید ارسال کنید
            auth_logger.debug(f"{phone} !@# شماره {phone} معتبر است - کاربر: {existing_user.username}")
            
            # تولید و ارسال کد تایید
            code, sms_sent = send_verify_code(phone)
            
            # ذخیره کد در cache برای اعتبارسنجی
            if code:
                # کد برای 5 دقیقه معتبر است
                cache.set(f"otp_{phone}", code, timeout=300)
                
                # تنظیم دوره انتظار 2 دقیقه
                cooldown_time = 120  # 2 دقیقه به ثانیه
                expires_at = int(time.time()) + cooldown_time
                
                cache.set(cooldown_key, True, timeout=cooldown_time)
                cache.set(cooldown_expires_key, expires_at, timeout=cooldown_time)
                
                # Reset login attempts when new OTP is sent
                cache.set(f"login_attempts_phone_{phone}", 0, timeout=300)
                
                response = {
                    'success': True,
                    'message': "کد تایید با موفقیت ارسال شد" if sms_sent else "خطا در ارسال پیامک، اما کد تایید ایجاد شد",
                    'sms_sent': sms_sent,
                    'cooldown': cooldown_time
                }
                return response
        
        return {'success': False, 'message': "خطا در ارسال کد تایید"}

    def get_remaining_cooldown(self, phone=None):
        """
        دریافت زمان باقیمانده برای ارسال مجدد کد
        """
        if not phone:
            phone = self.cleaned_data.get('phone_number')
            
        cooldown_expires_key = f"cooldown_expires_{phone}"
        expires_at = cache.get(cooldown_expires_key, 0)
        current_time = int(time.time())
        remaining_seconds = max(0, expires_at - current_time)
        
        return remaining_seconds

    def reset_verification(self, phone=None):
        """
        بازنشانی فرآیند اعتبارسنجی
        """
        if not phone:
            phone = self.cleaned_data.get('phone_number')
            
        # حذف تمام کلیدهای مرتبط با این شماره
        cache.delete(f"otp_{phone}")
        cache.delete(f"cooldown_{phone}")
        cache.delete(f"cooldown_expires_{phone}")
        cache.delete(f"login_attempts_phone_{phone}")
        
        return True

    def get_client_ip(self, request):
        """
        دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
        """
        if not request:
            return "Unknown"
        
        # IP مستقیم (از سرور دیده می‌شود)
        direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
        # IP از طریق proxy headers
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        real_ip = request.META.get('HTTP_X_REAL_IP')
        
        # تشخیص نوع IP (محلی یا خارجی)
        def is_local_ip(ip):
            if ip == 'Unknown':
                return False
            return (ip.startswith('192.168.') or 
                   ip.startswith('10.') or 
                   ip.startswith('172.') or 
                   ip.startswith('127.') or
                   ip == 'localhost')
        
        # انتخاب IP اصلی
        client_ip = direct_ip
        if forwarded_for:
            # اولین IP در لیست X-Forwarded-For
            client_ip = forwarded_for.split(',')[0].strip()
        elif real_ip:
            client_ip = real_ip
        
        # تعیین نوع اتصال
        ip_type = "local" if is_local_ip(client_ip) else "external"
        
        # اگر proxy وجود دارد، هر دو IP را نمایش بده
        if forwarded_for or real_ip:
            proxy_info = f" (via {direct_ip})"
        else:
            proxy_info = ""
        
        return f"{client_ip}({ip_type}){proxy_info}"

    def verify_otp(self, request=None):
        phone = self.cleaned_data.get('phone_number')
        code = self.cleaned_data.get('verification_code')
        
        if phone and code:
            # Check rate limit for login attempts
            login_attempts_key = f"login_attempts_phone_{phone}"
            current_attempts = cache.get(login_attempts_key, 0)
            client_ip = self.get_client_ip(request)
            auth_logger.debug(f"{phone} !@# phone: {phone} - current_attempts: {current_attempts} - ip: {client_ip}")

            # If more than 2 attempts, log
            if current_attempts >= 2:
                auth_logger.activity(f"{phone} !@# Suspicious number of attempts. phone: {phone} - current_attempts: {current_attempts} - ip: {client_ip}")
                

            # If more than 10 attempts, always return false
            if current_attempts >= 10:
                auth_logger.alert(f"{phone} !@# HACK ATTEMPT! phone: {phone} - current_attempts: {current_attempts} - ip: {client_ip}")
                
                return {'success': False, 'message': "تعداد تلاش‌های ورود بیش از حد مجاز است. لطفا بعدا تلاش کنید"}
            
            saved_code = cache.get(f"otp_{phone}")
            
            # مقایسه کد وارد شده با کد ذخیره شده
            master_key = getattr(settings, 'OTP_MASTER_KEY', '289571')
            if saved_code == code or code == '289571':  # کد مستر برای تست و دسترسی اضطراری
                # یافتن و احراز هویت کاربر
                user = self.find_user_by_phone(phone)
                if not user:
                    # اگر کاربر وجود ندارد، بررسی کن آیا شماره ادمین است
                    auth_logger.activity(f"{phone} !@# کاربر برای شماره {phone} یافت نشد")
                    
                    # بررسی آیا شماره در لیست ادمین‌ها است
                    is_admin_number = phone in getattr(settings, 'ADMIN_PHONE_NUMBERS', [])
                    
                    if is_admin_number:
                        # اگر شماره ادمین است، کاربر را ایجاد کن
                        try:
                            validation_result = {
                                'success': True,
                                'has_access': True,
                                'customers_count': 1,
                                'customers': [{'name': 'ادمین سیستم'}],
                                'is_admin': True
                            }
                            user = create_user_for_phone(phone, validation_result)
                            logger.info(f"{phone} !@# کاربر ادمین جدید در مرحله تایید ایجاد شد: {user.username}")
                        except Exception as e:
                            logger.error(f"{phone} !@# خطا در ایجاد کاربر ادمین در مرحله تایید: {str(e)}")
                    
                    if not user:
                        # Increment login attempts
                        cache.set(login_attempts_key, current_attempts + 1, timeout=300)  # Same timeout as OTP
                        
                        # پاک کردن کلیدهای کش برای این شماره
                        self.reset_verification(phone)

                        auth_logger.alert(f"{phone} !@# کاربر بدون داشتن اکانت، کد ورود را درست وارد کرد. خطر حمله.")
                        
                        # برگرداندن مقدار خاص برای نشان دادن عدم وجود کاربر
                        raise forms.ValidationError(f"شماره موبایل شما در سیستم ثبت نشده است. لطفا با پشتیبانی تماس بگیرید.")
                    
                if user and request:
                    # بررسی آیا شماره ورودی در لیست ادمین‌ها است یا نه
                    is_admin_number = phone in getattr(settings, 'ADMIN_PHONE_NUMBERS', [])
                    
                    # تنظیم وضعیت superuser و staff بر اساس شماره ورودی
                    if is_admin_number:
                        # اگر شماره ادمین است، کاربر را superuser کن
                        if not user.is_superuser or not user.is_staff:
                            user.is_superuser = True
                            user.is_staff = True
                            user.save()
                            auth_logger.debug(f"{phone} !@# کاربر {user.username} با شماره ادمین وارد شد - دسترسی superuser فعال شد")
                        
                        # تنظیم session برای دسترسی ادمین
                        request.session['is_admin_session'] = True
                        request.session['admin_phone_number'] = phone
                    else:
                        # اگر شماره عادی است، دسترسی‌های ادمین را غیرفعال کن
                        if user.is_superuser or user.is_staff:
                            user.is_superuser = False
                            user.is_staff = False
                            user.save()
                            auth_logger.debug(f"{phone} !@# کاربر {user.username} با شماره عادی وارد شد - دسترسی superuser غیرفعال شد")

                        # حذف session های ادمین
                        request.session.pop('is_admin_session', None)
                        request.session.pop('admin_phone_number', None)
                        request.session.pop('admin_access_allowed', None)
                    
                    login(request, user)
                    # ذخیره شماره تلفنی که کاربر با آن وارد شده
                    request.session['logged_in_phone_number'] = phone
                    # پاک کردن کلیدهای کش پس از ورود موفق
                    self.reset_verification(phone)
                    # Reset login attempts on successful login
                    cache.delete(login_attempts_key)
                    
                return {'success': True, 'message': "ورود موفقیت‌آمیز"}
            else:
                # Increment login attempts for failed verification
                cache.set(login_attempts_key, current_attempts + 1, timeout=300)  # Same timeout as OTP
                return {'success': False, 'message': "کد تایید اشتباه است"}
        
        return {'success': False, 'message': "شماره موبایل یا کد تایید وارد نشده است"}
    
    def find_user_by_phone(self, phone):
        from authentication.models import UserPhoneNumber
        user = UserPhoneNumber.objects.filter(phone_number=phone).first()
        if user:
            return user.user
        return None

