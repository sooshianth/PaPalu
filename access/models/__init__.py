# تمام مدل‌های مربوط به Field Access حالا در core.RBACModel هستند
# برای سازگاری با قبل، آن‌ها را اینجا import می‌کنیم
from core.RBACModel import FieldPermission, FieldChoice, UserFieldPermission
from core.RBACModel import user_has_field_access, user_can_access_field, get_accessible_fields


# Backward compatibility: ایجاد یک کلاس Proxy برای FieldAccessRule
# این کلاس برای سازگاری با کدهای قدیمی است و نباید در کدهای جدید استفاده شود
class FieldAccessRule:
    """
    DEPRECATED: این کلاس فقط برای سازگاری با کدهای قبلی است
    لطفا از user_has_field_access، user_can_access_field، و get_accessible_fields استفاده کنید
    """
    
    @staticmethod
    def has_field_access(user, model_instance, field_name, access_type='view'):
        """
        DEPRECATED: استفاده از user_has_field_access به جای این متد توصیه می‌شود
        """
        return user_has_field_access(user, model_instance, field_name, access_type)
    
    @staticmethod
    def get_accessible_fields(user, model_class, access_type='view'):
        """
        DEPRECATED: استفاده از get_accessible_fields به جای این متد توصیه می‌شود
        """
        return get_accessible_fields(user, model_class, access_type)


__all__ = ['FieldPermission', 'FieldChoice', 'UserFieldPermission', 'FieldAccessRule']

