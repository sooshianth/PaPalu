from django.apps import AppConfig


class AccessConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'access'
    verbose_name = 'مدیریت دسترسی فیلدها'
    
    def ready(self):
        """
        این متد بعد از آماده شدن اپلیکیشن اجرا می‌شود
        مدل‌های Field Access حالا در core.RBACModel هستند
        """
        # Import models to ensure they are registered
        from core.RBACModel import FieldPermission, FieldChoice, UserFieldPermission

