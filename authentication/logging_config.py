"""
سیستم Logging برای اپلیکیشن Authentication
شامل سطوح سفارشی و تنظیمات لاگینگ
"""

import logging
import os
from pathlib import Path
from django.conf import settings


# تعریف سطوح سفارشی Logging
ACTIVITY_LEVEL = 25  # بین INFO (20) و WARNING (30)
ALERT_LEVEL = 35  # بین WARNING (30) و ERROR (40)

logging.addLevelName(ACTIVITY_LEVEL, "ACTIVITY")
logging.addLevelName(ALERT_LEVEL, "ALERT")


def activity(self, message, *args, **kwargs):
    """
    لاگ فعالیت‌های مهم کاربران
    مثال: تلاش برای ورود با شماره غیرمجاز
    """
    if self.isEnabledFor(ACTIVITY_LEVEL):
        self._log(ACTIVITY_LEVEL, message, args, **kwargs)


def alert(self, message, *args, **kwargs):
    """
    لاگ هشدارهای امنیتی
    مثال: تلاش‌های هک یا فعالیت‌های مشکوک
    """
    if self.isEnabledFor(ALERT_LEVEL):
        self._log(ALERT_LEVEL, message, args, **kwargs)


# اضافه کردن متدهای سفارشی به Logger
logging.Logger.activity = activity
logging.Logger.alert = alert


class AuthenticationFormatter(logging.Formatter):
    """
    Formatter سفارشی برای لاگ‌های Authentication
    فرمت: [تاریخ ساعت] [سطح] [شماره تلفن] پیام
    """
    
    def format(self, record):
        # استخراج شماره تلفن از پیام (اگر با فرمت !@# باشد)
        message = record.getMessage()
        
        if '!@#' in message:
            parts = message.split('!@#', 1)
            phone = parts[0].strip()
            actual_message = parts[1].strip() if len(parts) > 1 else message
            
            # ساخت پیام فرمت شده
            formatted_message = f"[{phone}] {actual_message}"
        else:
            formatted_message = message
        
        # ساخت رکورد جدید با پیام فرمت شده
        record.msg = formatted_message
        record.args = ()
        
        return super().format(record)


def setup_authentication_logging():
    """
    تنظیم logging برای اپلیکیشن authentication
    """
    # مسیر پوشه لاگ‌ها
    log_dir = Path(settings.BASE_DIR) / 'logs' / 'authentication'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # مسیر فایل‌های لاگ
    auth_log_file = log_dir / 'auth.log'
    activity_log_file = log_dir / 'activity.log'
    alert_log_file = log_dir / 'alert.log'
    error_log_file = log_dir / 'error.log'
    
    # دریافت logger
    logger = logging.getLogger('auth_form')
    logger.setLevel(logging.DEBUG)
    
    # پاک کردن handlers قبلی (در صورت وجود)
    logger.handlers = []
    
    # Formatter سفارشی
    formatter = AuthenticationFormatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler برای تمام لاگ‌ها
    all_handler = logging.FileHandler(auth_log_file, encoding='utf-8')
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(formatter)
    logger.addHandler(all_handler)
    
    # Handler برای فعالیت‌ها (ACTIVITY level)
    activity_handler = logging.FileHandler(activity_log_file, encoding='utf-8')
    activity_handler.setLevel(ACTIVITY_LEVEL)
    activity_handler.setFormatter(formatter)
    activity_handler.addFilter(lambda record: record.levelno == ACTIVITY_LEVEL)
    logger.addHandler(activity_handler)
    
    # Handler برای هشدارها (ALERT level)
    alert_handler = logging.FileHandler(alert_log_file, encoding='utf-8')
    alert_handler.setLevel(ALERT_LEVEL)
    alert_handler.setFormatter(formatter)
    alert_handler.addFilter(lambda record: record.levelno == ALERT_LEVEL)
    logger.addHandler(alert_handler)
    
    # Handler برای خطاها (ERROR و بالاتر)
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # Handler برای نمایش در Console (فقط در حالت DEBUG)
    if settings.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


# ایجاد logger پیش‌فرض برای authentication
def get_auth_logger(name='auth_form'):
    """
    دریافت logger برای authentication
    
    Args:
        name: نام logger (پیش‌فرض: auth_form)
    
    Returns:
        logging.Logger
    """
    return logging.getLogger(name)

