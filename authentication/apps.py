from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'
    verbose_name = 'احراز هویت و ورود'
    
    def ready(self):
        """
        تنظیمات اولیه هنگام بارگذاری اپلیکیشن
        """
        # تنظیم logging
        from .logging_config import setup_authentication_logging
        setup_authentication_logging()
