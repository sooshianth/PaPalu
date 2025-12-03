
from pathlib import Path
from dotenv import load_dotenv
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')



# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-3vlymx-erfjbe&*g(z)8)q1o*!!nr%l@v&nvejmmwuuhm!qh6i')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS','localhost').split(',')

# Session timeout configuration
SESSION_COOKIE_AGE = 1200  # 20 minutes in seconds
SESSION_SAVE_EVERY_REQUEST = False  # Changed to False to reduce database writes and memory usage
SESSION_EXPIRE_AT_BROWSER_CLOSE = True


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'django_jalali',
    'django_tables2',
    
    # Local apps
    'core.apps.CoreConfig',
    'authentication.apps.AuthenticationConfig',
    'perm_manager.apps.PermManagerConfig',
    'accounting.apps.AccountingConfig',
    'distribution.apps.DistributionConfig',
    'production.apps.ProductionConfig',
    'sales.apps.SalesConfig',
    'warehousing.apps.WarehousingConfig',
    'supply.apps.SupplyConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom middlewares
    'config.middleware.SessionTimeoutMiddleware',
    'config.middleware.RestrictAdminAccessMiddleware',
    'config.middleware.LogContextMiddleware',
    'config.middleware.SecurityLoggingMiddleware',
    'config.middleware.LoginAttemptMiddleware',
    'config.middleware.AdminSessionManagementMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 10,  # Wait up to 10 seconds before 'database is locked'
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA busy_timeout=10000;'
        }
    }
}

# Cache configuration - using LocMemCache for better performance and less memory usage
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'papalu-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,  # Limit cache size to prevent memory bloat
        }
    }
}


AUTH_PASSWORD_VALIDATORS = [
]


LANGUAGE_CODE = 'fa-ir'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication settings
LOGIN_URL = '/authentication/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# شماره‌های تلفن ادمین‌ها (برای دسترسی superuser)
# می‌توانید این لیست را در فایل .env تنظیم کنید
# مثال در .env: ADMIN_PHONE_NUMBERS=09123456789,09987654321
admin_phones_str = os.getenv('ADMIN_PHONE_NUMBERS', '')
ADMIN_PHONE_NUMBERS = [phone.strip() for phone in admin_phones_str.split(',') if phone.strip()] if admin_phones_str else []

# تنظیمات SMS برای ارسال کد تایید
SMS_API_KEY = os.getenv('SMS_API_KEY', '')
SMS_LINE_NUMBER = os.getenv('SMS_LINE_NUMBER', '')

# کد مستر برای ورود (برای تست و دسترسی اضطراری)
# اگر این کد وارد شود، بدون نیاز به OTP می‌توان وارد شد
OTP_MASTER_KEY = os.getenv('OTP_MASTER_KEY', '')

# ایجاد پوشه logs در صورت عدم وجود
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} !@# {asctime} !@# {filename} !@# {funcName} !@# {process:d} !@# {thread:d} !@# {username} !@# {log_ip} !@# {download_size} !@# {upload_size} !@# {message} !@# {user_phone}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'message_only': {
            'format': '{message}',
            'style': '{',
        },
        'security': {
            'format': '{levelname} !@# {asctime} !@# {user_id} !@# {username} !@# {action} !@# {method} !@# {endpoint} !@# {ip_address} !@# {user_agent} !@# {payload_summary} !@# {status_code} !@# {duration_ms} !@# {message} !@# {user_phone}',
            'style': '{',
        },
        'auth': {
            'format': '{levelname} !@# {asctime} !@# {user_id} !@# {username} !@# {action} !@# {ip_address} !@# {user_agent} !@# {message} !@# {user_phone}',
            'style': '{',
        },
        'bugs': {
            'format': '{levelname} !@# {asctime} !@# {filename} !@# {funcName} !@# {lineno} !@# {process:d} !@# {thread:d} !@# {username} !@# {log_ip} !@# {message}',
            'style': '{',
        },
        'django_errors': {
            'format': '{levelname} !@# {asctime} !@# {filename} !@# {funcName} !@# {pathname} !@# {lineno} !@# {message}',
            'style': '{',
        },
        'audit': {
            'format': '{levelname} !@# {asctime} !@# {user_id} !@# {username} !@# {action} !@# {method} !@# {endpoint} !@# {ip_address} !@# {user_agent} !@# {message} !@# {user_phone}',
            'style': '{',
        },
    },
    'filters': {
        'exclude_runserver_and_http_protocol': {
            '()': 'core.logging_filters.ExcludeRunserverAndHttpProtocol',
        },
        'userinfo': {
            '()': 'core.logging_filters.LogUserInfoFilter',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'message_only',
            'filters': ['exclude_runserver_and_http_protocol', 'userinfo'],
        },
        'django_errors_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'django_errors',
            'encoding': 'utf-8',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'formatter': 'security',
            'encoding': 'utf-8',
            'filters': ['userinfo'],
        },
        'auth_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'auth.log'),
            'formatter': 'auth',
            'encoding': 'utf-8',
            'filters': ['userinfo'],
        },
        'bugs_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'bugs.log'),
            'formatter': 'bugs',
            'encoding': 'utf-8',
            'filters': ['userinfo'],
        },
        'audit_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'audit.log'),
            'formatter': 'audit',
            'encoding': 'utf-8',
            'filters': ['userinfo'],
        },
        'circular_buffer': {
            'level': 'DEBUG', 
            'class': 'core.logging_filters.CircularBufferHandler',
            'capacity': 10000,
            'formatter': 'verbose',
            # Add userinfo filter so formatter fields like {username} are always present
            'filters': ['userinfo'],
        },
        'null': {
            'class': 'logging.NullHandler',  # Ignores messages
        },
    },
    'loggers': {
        'http_protocol': {
            'handlers': ['null'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django': {
            'handlers': ['console', 'django_errors_file', 'circular_buffer'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'django_errors_file', 'circular_buffer'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console', 'django_errors_file', 'circular_buffer'], 
            'level': 'ERROR',
            'propagate': False,
        },
        'security': {
            'handlers': ['console', 'security_file', 'circular_buffer'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'authentication': {
            'handlers': ['console', 'auth_file', 'circular_buffer'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'audit': {
            'handlers': ['console', 'audit_file', 'circular_buffer'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'bugs': {
            'handlers': ['console', 'bugs_file', 'circular_buffer'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Security settings
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Rate limiting configuration
MAX_REQUESTS_PER_MINUTE = 100
