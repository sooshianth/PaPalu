from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


def convert_to_persian_numbers(text):
    """تبدیل اعداد انگلیسی به فارسی"""
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    translation_table = str.maketrans(english_digits, persian_digits)
    return str(text).translate(translation_table)


@register.filter(name='persian_digits')
def persian_digits(value):
    """تبدیل ارقام انگلیسی به فارسی در هر متنی (مثلاً پلاک)"""
    if value is None or value == '':
        return value
    return convert_to_persian_numbers(str(value))


def _to_decimal(value):
    """تبدیل امن به Decimal برای نمایش بدون خطای ممیز شناور"""
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
    """فرمت کردن عدد با کاما و تبدیل به فارسی (اعشار ثابت)"""
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
    # جداکننده هزارگان به «،» و ارقام به فارسی
    return convert_to_persian_numbers(formatted.replace(',', '،'))


@register.filter(name='rials_to_tomans')
def rials_to_tomans(value):
    """تبدیل ریال به تومان و فرمت با اعداد فارسی (اعشار ثابت)"""
    if value is None:
        return '-'
    d = _to_decimal(value)
    if d is None:
        return str(value)
    tomans = (d / Decimal('10')).quantize(Decimal('1'))
    return convert_to_persian_numbers(f"{tomans:,.0f}".replace(',', '،'))


@register.filter(name='number_to_words_persian')
def number_to_words_persian(value):
    """تبدیل عدد به حروف فارسی"""
    if value is None:
        return ''
    d = _to_decimal(value)
    if d is None:
        return str(value)
    try:
        num = int(d.quantize(Decimal('1')))
        
        if num == 0:
            return 'صفر'
        
        if num < 0:
            return 'منفی ' + number_to_words_persian(abs(num))
        
        # واحدهای یک رقمی
        ones = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
        
        # دهگان
        tens = ['', '', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود']
        
        # اعداد 10 تا 19
        teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده']
        
        # صدگان
        hundreds = ['', 'یکصد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد']
        
        # مقیاس‌ها
        scales = [
            (1000000000000, 'تریلیون'),  # تریلیون
            (1000000000, 'میلیارد'),     # میلیارد
            (1000000, 'میلیون'),         # میلیون
            (1000, 'هزار'),               # هزار
        ]
        
        def convert_less_than_thousand(n):
            """تبدیل اعداد کمتر از 1000 به حروف"""
            if n == 0:
                return ''
            elif n < 10:
                return ones[n]
            elif n < 20:
                return teens[n - 10]
            elif n < 100:
                ten = n // 10
                one = n % 10
                if one == 0:
                    return tens[ten]
                else:
                    return tens[ten] + ' و ' + ones[one]
            else:  # n < 1000
                hundred = n // 100
                remainder = n % 100
                result = hundreds[hundred]
                if remainder > 0:
                    result += ' و ' + convert_less_than_thousand(remainder)
                return result
        
        # تبدیل عدد کامل
        result = []
        
        for scale_value, scale_name in scales:
            if num >= scale_value:
                scale_count = num // scale_value
                result.append(convert_less_than_thousand(scale_count) + ' ' + scale_name)
                num = num % scale_value
        
        # باقیمانده (کمتر از 1000)
        if num > 0:
            result.append(convert_less_than_thousand(num))
        
        return ' و '.join(result)
        
    except (ValueError, TypeError):
        return str(value)

