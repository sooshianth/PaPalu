# -*- coding: utf-8 -*-
"""
توابع کمکی برای آپلود فایل با نام امن (فقط ASCII).
برای جلوگیری از خطای 404 با نام‌های فارسی/یونیکد در IIS و سرو کردن media.
"""
import os
import uuid
from datetime import datetime

from django.utils.deconstruct import deconstructible

# پسوندهای مجاز برای فایل‌های آپلودی (نام فایل همیشه با این‌ها ساخته می‌شود)
ALLOWED_EXTENSIONS = (
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.doc', '.docx', '.xls', '.xlsx', '.csv',
    '.zip', '.rar', '.txt', '.bin',
)


@deconstructible
class SafeMediaUploadTo:
    """
    کلاس قابل سریال‌سازی برای upload_to که نام فایل را فقط با کاراکترهای ASCII
    (UUID + پسوند) می‌سازد. برای استفاده در مایگریشن‌های Django.
    """
    def __init__(self, prefix, date_include_day=False):
        self.prefix = prefix
        self.date_include_day = date_include_day

    def __call__(self, instance, filename):
        ext = (os.path.splitext(filename)[1] or '').lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = '.bin'
        safe_name = f"{uuid.uuid4().hex}{ext}"
        if self.date_include_day:
            subpath = datetime.now().strftime('%Y/%m/%d')
        else:
            subpath = datetime.now().strftime('%Y/%m')
        return f"{self.prefix}/{subpath}/{safe_name}"


@deconstructible
class SafeMediaUploadToFlat:
    """
    مثل SafeMediaUploadTo ولی بدون زیرپوشه تاریخ؛ فقط prefix/uuid.ext
    """
    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self, instance, filename):
        ext = (os.path.splitext(filename)[1] or '').lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = '.bin'
        safe_name = f"{uuid.uuid4().hex}{ext}"
        return f"{self.prefix}/{safe_name}"


# نام‌های قدیمی برای سازگاری با کد فعلی (همان کلاس‌ها با نام تابع)
def safe_media_upload_to(prefix, date_include_day=False):
    return SafeMediaUploadTo(prefix, date_include_day=date_include_day)


def safe_media_upload_to_flat(prefix):
    return SafeMediaUploadToFlat(prefix)
