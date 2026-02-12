from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


def _convert_to_persian_digits(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    return str(text).translate(str.maketrans(english_digits, persian_digits))


def _to_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        return None


@register.filter(name='persian_number')
def persian_number(value, decimal_places=0):
    """فرمت عدد با جداکننده هزارگان «،» و ارقام فارسی"""
    if value is None:
        return '-'
    d = _to_decimal(value)
    if d is None:
        return str(value)
    if decimal_places > 0:
        quantizer = Decimal(10) ** -decimal_places
        formatted = f"{d.quantize(quantizer):,.{decimal_places}f}"
    else:
        formatted = f"{d.quantize(Decimal('1')):,.0f}"
    # جداکننده هزارگان انگلیسی را به «،» فارسی تبدیل کن
    formatted = formatted.replace(',', '،')
    return _convert_to_persian_digits(formatted)
