# -*- coding: utf-8 -*-
"""
توابع کمکی برای آپلود فایل با نام امن (فقط ASCII).
برای جلوگیری از خطای 404 با نام‌های فارسی/یونیکد در IIS و سرو کردن media.
"""
import os
import uuid
from datetime import datetime

# پسوندهای مجاز برای فایل‌های آپلودی (نام فایل همیشه با این‌ها ساخته می‌شود)
ALLOWED_EXTENSIONS = (
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.doc', '.docx', '.xls', '.xlsx', '.csv',
    '.zip', '.rar', '.txt', '.bin',
)


def safe_media_upload_to(prefix, date_include_day=False):
    """
    برمی‌گرداند تابع upload_to برای FileField/ImageField که نام فایل را فقط با
    کاراکترهای ASCII (UUID + پسوند) می‌سازد تا از خطای 404 با نام‌های فارسی/یونیکد
    در IIS جلوگیری شود.

    Args:
        prefix: پیشوند مسیر، مثلاً 'bill_of_lading' یا 'person_attachments'
        date_include_day: اگر True باشد مسیر شامل روز هم می‌شود: prefix/2026/02/14/
                          اگر False: prefix/2026/02/

    Returns:
        تابع (instance, filename) -> path برای upload_to
    """
    def upload_to(instance, filename):
        ext = (os.path.splitext(filename)[1] or '').lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = '.bin'
        safe_name = f"{uuid.uuid4().hex}{ext}"
        if date_include_day:
            subpath = datetime.now().strftime('%Y/%m/%d')
        else:
            subpath = datetime.now().strftime('%Y/%m')
        return f"{prefix}/{subpath}/{safe_name}"
    return upload_to


def safe_media_upload_to_flat(prefix):
    """
    مثل safe_media_upload_to ولی بدون زیرپوشه تاریخ؛ فقط prefix/uuid.ext
    برای مسیرهایی مثل products/ یا invoices/
    """
    def upload_to(instance, filename):
        ext = (os.path.splitext(filename)[1] or '').lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = '.bin'
        safe_name = f"{uuid.uuid4().hex}{ext}"
        return f"{prefix}/{safe_name}"
    return upload_to
