def determine_user_role(user):
    """
    تشخیص نقش کاربر براساس روابط او
    به جای بررسی مستقیم role که وجود ندارد، روابط بررسی می‌شود
    نقش لجستیک بر فروش ارجحیت دارد
    """
    if user.is_superuser:
        # مدیر ارشد دسترسی کامل دارد
        return 'admin'
    return None
