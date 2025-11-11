from django.apps import AppConfig


class AccessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'access'
    verbose_name = 'مدیریت دسترسی فیلدها'
    
    def ready(self):
        """
        این متد بعد از آماده شدن اپلیکیشن اجرا می‌شود
        و مطمئن می‌شود که مدل‌های access در ContentType ثبت شوند
        """
        # Import models to ensure they are registered
        from .models.FieldAccessUserModel import FieldAccessRule

