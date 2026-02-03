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


@register.filter(name='rials_to_tomans')
def rials_to_tomans(value):
    """تبدیل ریال به تومان و فرمت با اعداد فارسی"""
    if value is None:
        return '-'
    try:
        # تبدیل به float و تقسیم بر 10
        num_float = float(value) / 10
        # فرمت با کاما
        formatted = f"{num_float:,.0f}"
        # تبدیل به فارسی
        return convert_to_persian_numbers(formatted)
    except (ValueError, TypeError):
        return str(value)


@register.filter(name='number_to_words_persian')
def number_to_words_persian(value):
    """تبدیل عدد به حروف فارسی"""
    if value is None:
        return ''
    
    try:
        # تبدیل به عدد صحیح (حذف اعشار)
        num = int(float(value))
        
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

