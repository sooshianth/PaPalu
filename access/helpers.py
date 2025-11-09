"""
توابع کمکی برای کار با سیستم دسترسی فیلدها
"""

from .models import FieldAccessRule


def filter_fields_by_access(user, model_instance, fields_list, access_type='view'):
    """
    فیلتر کردن لیست فیلدها بر اساس دسترسی کاربر
    
    Args:
        user: شیء کاربر
        model_instance: نمونه‌ای از مدل
        fields_list: لیست نام فیلدها
        access_type: نوع دسترسی (view, edit, delete)
    
    Returns:
        لیست فیلدهایی که کاربر به آن‌ها دسترسی دارد
    """
    if user.is_superuser:
        return fields_list
    
    accessible_fields = []
    for field in fields_list:
        if FieldAccessRule.has_field_access(user, model_instance, field, access_type):
            accessible_fields.append(field)
    
    return accessible_fields


def get_field_value_safe(user, model_instance, field_name, default=None):
    """
    گرفتن مقدار یک فیلد با بررسی دسترسی کاربر
    
    Args:
        user: شیء کاربر
        model_instance: نمونه‌ای از مدل
        field_name: نام فیلد
        default: مقدار پیش‌فرض در صورت عدم دسترسی
    
    Returns:
        مقدار فیلد یا مقدار پیش‌فرض
    """
    if FieldAccessRule.has_field_access(user, model_instance, field_name, 'view'):
        return getattr(model_instance, field_name, default)
    return default


def can_edit_field(user, model_instance, field_name):
    """
    بررسی اینکه آیا کاربر می‌تواند فیلد را ویرایش کند
    
    Args:
        user: شیء کاربر
        model_instance: نمونه‌ای از مدل
        field_name: نام فیلد
    
    Returns:
        True یا False
    """
    return FieldAccessRule.has_field_access(user, model_instance, field_name, 'edit')


def set_field_value_safe(user, model_instance, field_name, value):
    """
    تنظیم مقدار یک فیلد با بررسی دسترسی کاربر
    
    Args:
        user: شیء کاربر
        model_instance: نمونه‌ای از مدل
        field_name: نام فیلد
        value: مقدار جدید
    
    Returns:
        True اگر موفق بود، False اگر دسترسی نداشت
    """
    if can_edit_field(user, model_instance, field_name):
        setattr(model_instance, field_name, value)
        return True
    return False


def get_model_dict_with_access(user, model_instance, access_type='view'):
    """
    تبدیل مدل به دیکشنری با توجه به دسترسی کاربر
    
    Args:
        user: شیء کاربر
        model_instance: نمونه‌ای از مدل
        access_type: نوع دسترسی (view, edit, delete)
    
    Returns:
        دیکشنری از فیلدها و مقادیرشان
    """
    accessible_fields = FieldAccessRule.get_accessible_fields(
        user, 
        model_instance.__class__, 
        access_type
    )
    
    result = {}
    for field in accessible_fields:
        try:
            value = getattr(model_instance, field)
            # تبدیل مقادیر غیرقابل سریال به string
            if hasattr(value, 'pk'):
                result[field] = value.pk
            else:
                result[field] = value
        except Exception:
            continue
    
    return result

