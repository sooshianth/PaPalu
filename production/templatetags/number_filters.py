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
    """فرمت کردن عدد با کاما و تبدیل به فارسی"""
    if value is None:
        return '-'
    try:
        # تبدیل به float
        num_float = float(value)
        # فرمت با کاما
        if decimal_places > 0:
            formatted = f"{num_float:,.{decimal_places}f}"
        else:
            formatted = f"{num_float:,.0f}"
        # تبدیل به فارسی
        return convert_to_persian_numbers(formatted)
    except (ValueError, TypeError):
        return str(value)

