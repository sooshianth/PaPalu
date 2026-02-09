# -*- coding: utf-8 -*-
"""
ابزارهای اعشار ثابت (fixed-point) برای جلوگیری از خطای ممیز شناور.
استفاده از Decimal به جای float برای مبالغ، وزن‌ها و هر داده‌ای که نیاز به دقت دارد.
"""
from decimal import Decimal, InvalidOperation


def to_decimal(value, default=None):
    """
    تبدیل امن به Decimal.
    value می‌تواند int, float, str, Decimal یا None باشد.
    در صورت خطا یا None، default برگردانده می‌شود (پیش‌فرض Decimal('0')).
    """
    if default is None:
        default = Decimal('0')
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        return default


def format_decimal(value, decimal_places=2):
    """
    فرمت Decimal برای نمایش با تعداد اعشار مشخص.
    برای استفاده در format_html و خروجی متنی.
    """
    d = to_decimal(value)
    if decimal_places <= 0:
        return f"{int(d.quantize(Decimal('1'))):,}"
    quantizer = Decimal(10) ** -decimal_places
    return f"{d.quantize(quantizer):,.{decimal_places}f}"
