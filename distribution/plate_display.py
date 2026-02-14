# -*- coding: utf-8 -*-
"""
نمایش پلاک خودرو به سبک پلاک ایران برای استفاده در جداول توزیع.
"""
import re
from django.utils.html import format_html
from django.utils.safestring import mark_safe


def _to_persian_digits(text):
    """تبدیل اعداد انگلیسی به فارسی."""
    if not text:
        return text
    persian = '۰۱۲۳۴۵۶۷۸۹'
    english = '0123456789'
    return str(text).translate(str.maketrans(english, persian))


def render_iran_plate_html(plate_number):
    """
    تبدیل رشته پلاک (مثلاً 11|345ح12) به HTML شبیه پلاک ایران.
    فرمت: دو رقم کد منطقه | سه رقم + یک حرف فارسی + دو رقم کد ایران.
    خروجی: یک باکس شبیه پلاک با پس‌زمینه سفید، حاشیه، و بخش کد ایران در نوار سبز.
    """
    if not plate_number or not str(plate_number).strip():
        return format_html('<span style="color: var(--gray-400);">-</span>')

    raw = str(plate_number).strip()
    # نرمال‌سازی جداکننده
    raw = raw.replace(' ', '').replace('｜', '|')

    # فرمت استاندارد: 11|345ح12
    parts = raw.split('|')
    if len(parts) != 2:
        # اگر فرمت نبود، همان را با استایل ساده پلاک نشان بده
        persian = _to_persian_digits(raw)
        return format_html(
            '<span class="iran-plate-inline" style="'
            'display: inline-block; padding: 2px 6px; white-space: nowrap; '
            'background: #e9ecef; border: 1px solid #333; border-radius: 4px; '
            'font-weight: 700; font-size: 0.7rem; '
            'font-family: Vazirmatn, Tahoma, Segoe UI, Arial, sans-serif; '
            'font-variant-numeric: tabular-nums; color: #000; direction: rtl;">'
            '{}</span>',
            persian
        )

    part1 = parts[0].strip()   # 11 - کد منطقه
    middle = parts[1].strip()  # 345ح12

    # تجزیه بخش دوم: 3 رقم + 1 حرف فارسی + 2 رقم
    match = re.match(
        r'^(\d{3})([ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])(\d{2})$',
        middle,
        re.UNICODE
    )
    if not match:
        persian = _to_persian_digits(raw)
        return format_html(
            '<span class="iran-plate-inline" style="'
            'display: inline-block; padding: 2px 6px; white-space: nowrap; '
            'background: #e9ecef; border: 1px solid #333; border-radius: 4px; '
            'font-weight: 700; font-size: 0.7rem; color: #000; direction: rtl; '
            'font-family: Vazirmatn, Tahoma, Segoe UI, Arial, sans-serif;">{}</span>',
            persian
        )

    num3, letter, iran2 = match.group(1), match.group(2), match.group(3)
    p1 = _to_persian_digits(part1)
    p3 = _to_persian_digits(num3)
    p_iran = _to_persian_digits(iran2)

    # HTML پلاک ایران: همیشه یک سطر، همه اعداد مشکی
    return format_html(
        '<span class="iran-plate" style="'
        'display: inline-flex; align-items: stretch; white-space: nowrap; '
        'border: 1px solid #222; border-radius: 4px; overflow: hidden; '
        'box-shadow: 0 1px 2px rgba(0,0,0,0.12); '
        'font-weight: 700; font-size: 0.7rem; line-height: 1.1; '
        'font-family: Vazirmatn, Tahoma, Segoe UI, Arial, sans-serif; '
        'font-variant-numeric: tabular-nums; direction: rtl;">'
        '<span style="'
        'padding: 2px 5px; background: #dee2e6; color: #000; '
        'border-left: 1px solid #222; min-width: 1.4em; text-align: center;">'
        '{}</span>'
        '<span style="'
        'padding: 2px 5px; background: #f1f3f5; color: #000; '
        'letter-spacing: 0.5px;">'
        '{} {}</span>'
        '<span style="'
        'padding: 2px 5px; background: #f1f3f5; color: #000; '
        'min-width: 1.4em; text-align: center;">'
        '{}</span>'
        '</span>',
        p1,
        p3,
        letter,
        p_iran
    )
