from django import template

register = template.Library()


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


@register.filter(name='persian_number')
def persian_number(value, decimal_places=0):
    """فرمت کردن عدد با کاما و تبدیل به فارسی (اعشار ثابت)"""
    if value is None:
        return '-'
    try:
        from decimal import Decimal
        d = Decimal(str(value))
        if decimal_places > 0:
            quantizer = Decimal(10) ** -decimal_places
            formatted = f"{d.quantize(quantizer):,.{decimal_places}f}"
        else:
            formatted = f"{d.quantize(Decimal('1')):,.0f}"
        # جداکننده هزارگان به «،» و ارقام به فارسی
        return convert_to_persian_numbers(formatted.replace(',', '،'))
    except (ValueError, TypeError):
        return str(value)

