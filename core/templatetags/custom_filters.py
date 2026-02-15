# core/templatetags/custom_filters.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

def number_to_words(num):
    """
    تبدیل عدد به معادل فارسی
    """
    try:
        num = int(num)
    except (ValueError, TypeError):
        return "صفر"
    
    if num == 0:
        return "صفر"
    
    if num < 0:
        return f"منفی {number_to_words(abs(num))}"
    
    units = ["", "هزار", "میلیون", "میلیارد", "تریلیون", "کوادریلیون"]
    ones = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
    teens = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
    tens = ["", "ده", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
    hundreds = ["", "صد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]

    def convert_chunk(chunk):
        if chunk == 0:
            return ""
        words = []
        
        # صدها
        if chunk >= 100:
            words.append(hundreds[chunk // 100])
            chunk %= 100
        
        # ده‌ها و یکان
        if chunk >= 20:
            words.append(tens[chunk // 10])
            chunk %= 10
        elif chunk >= 10:
            words.append(teens[chunk - 10])
            chunk = 0
        
        # یکان
        if chunk > 0:
            words.append(ones[chunk])
            
        return " و ".join(words)

    words = []
    chunk_index = 0
    
    while num > 0 and chunk_index < len(units):
        chunk = num % 1000
        if chunk != 0:
            chunk_words = convert_chunk(chunk)
            if chunk_index > 0 and units[chunk_index]:
                chunk_words += " " + units[chunk_index]
            words.append(chunk_words)
        num = num // 1000
        chunk_index += 1

    if not words:
        return "صفر"
        
    return " و ".join(reversed(words))

@register.filter
def to_persian_words(value):
    try:
        num = int(value)//10
        return number_to_words(num) + " تومان"
    except (ValueError, TypeError):
        return value

@register.filter
def to_persian_words_weight(value):
    try:
        num = int(value)//1000
        return number_to_words(num) + " تن"
    except (ValueError, TypeError):
        return value

@register.filter
def format_weight(value):
    """
    فرمت کامل وزن کیلوگرمی با کاما + وزن تنی با حروف
    مثال: 47,823 کیلوگرم (چهل و هفت تن و هشتصد و بیست و سه کیلوگرم)
    """
    try:
        num = int(value)
        
        # اگر مقدار صفر است
        if num == 0:
            return mark_safe("<span class='fledger-weight-display'>۰ کیلوگرم<br><small>(صفر)</small></span>")
        
        # تشخیص منفی بودن
        if num < 0:
            return mark_safe("<span class='fledger-weight-display text-danger'>مقدار نامعتبر</span>")
        
        # فرمت با کاما
        formatted_kg = f"{num:,}"
        # تبدیل اعداد به فارسی
        formatted_kg = formatted_kg.replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")
        
        # تبدیل به تن (تقسیم بر 1000)
        ton_amount = num // 1000
        remaining_kg = num % 1000
        
        # ساختن متن فارسی
        if ton_amount == 0:
            # فقط کیلوگرم دارم (کمتر از یک تن)
            weight_words = number_to_words(remaining_kg) + " کیلوگرم"
        elif remaining_kg == 0:
            # فقط تن دارم (عدد گرد)
            weight_words = number_to_words(ton_amount) + " تن"
        else:
            # هم تن هم کیلوگرم دارم
            ton_words = number_to_words(ton_amount)
            kg_words = number_to_words(remaining_kg)
            weight_words = f"{ton_words} تن و {kg_words} کیلوگرم"
        
        return mark_safe(f"<span class='fledger-weight-display'>{formatted_kg} کیلوگرم<br><small>({weight_words})</small></span>")
    except (ValueError, TypeError, ZeroDivisionError):
        return value

@register.filter
def add_commas(value):
    """
    اضافه کردن کاما به مبالغ ریالی برای خوانایی بهتر با اعداد فارسی
    """
    try:
        num = int(value)
        formatted = f"{num:,}"
        # تبدیل اعداد به فارسی
        formatted = formatted.replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")
        return formatted
    except (ValueError, TypeError):
        return value

@register.filter
def format_rial_amount(value):
    """
    فرمت کامل مبلغ ریالی با کاما + مبلغ تومانی با حروف
    مثال: 1,500,000 ریال (یکصد و پنجاه هزار تومان)
    """
    try:
        num = int(value)
        
        # اگر مقدار صفر است
        if num == 0:
            return mark_safe("<span class='fledger-amount-display'>۰ ریال<br><small class='text-muted'>(صفر تومان)</small></span>")
        
        # تشخیص منفی بودن
        is_negative = num < 0
        abs_num = abs(num)
        
        # فرمت با کاما (استفاده از abs برای جلوگیری از دو تا منفی)
        formatted_rial = f"{abs_num:,}"
        # تبدیل اعداد به فارسی
        formatted_rial = formatted_rial.replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")
        
        # تبدیل به تومان (تقسیم بر 10)
        toman_amount = abs_num // 10
        
        if toman_amount == 0:
            toman_words = "صفر"
        else:
            toman_words = number_to_words(toman_amount)
        
        # اگر مبلغ منفی است، علامت منفی را اضافه کن
        if is_negative:
            formatted_rial = f"-{formatted_rial}"
            toman_words = f"منفی {toman_words}"
        
        return mark_safe(f"<span class='fledger-amount-display'>{formatted_rial} ریال<br><small class='text-muted'>({toman_words} تومان)</small></span>")
    except (ValueError, TypeError, ZeroDivisionError):
        return value

@register.filter
def format_toman_amount(value):
    """
    فرمت مبلغ تومانی با کاما + حروف
    مثال: 150,000 تومان (یکصد و پنجاه هزار تومان)
    """
    try:
        num = int(value)
        formatted_toman = f"{num:,}"
        toman_words = number_to_words(num)
        
        return mark_safe(f"{formatted_toman} تومان<br><small class='text-muted'>({toman_words} تومان)</small>")
    except (ValueError, TypeError):
        return value

@register.filter
def split(value, arg):
    """
    فیلتر برای جدا کردن یک رشته با یک جداکننده مشخص
    
    مثال استفاده:
    {{ "محمد,علی,رضا"|split:"," }}
    
    این فیلتر رشته را به لیستی از مقادیر تبدیل می‌کند.
    """
    return value.split(arg)

@register.filter
def to_persian_digits(value):
    return str(value).replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")

@register.filter
def to_persian_digits_with_commas(value):
    """
    تبدیل عدد به اعداد فارسی با کاماهای سه‌تایی
    مثال: 231028 -> ۲۳۱,۰۲۸
    """
    try:
        num = int(value)
        formatted = f"{num:,}"
        # تبدیل اعداد به فارسی
        formatted = formatted.replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")
        return formatted
    except (ValueError, TypeError):
        return str(value).replace("0", "۰").replace("1", "۱").replace("2", "۲").replace("3", "۳").replace("4", "۴").replace("5", "۵").replace("6", "۶").replace("7", "۷").replace("8", "۸").replace("9", "۹")

@register.filter
def sum_attribute(queryset, attribute):
    return sum(getattr(obj, attribute) for obj in queryset) if queryset else 0

@register.filter
def average(queryset, attribute):
    if not queryset or not queryset.exists():
        return 0
    total = sum(getattr(obj, attribute) for obj in queryset)
    return total / queryset.count() if queryset.count() > 0 else 0


@register.filter
def length(value):
    """
    Returns the length of a list or string.
    """
    try:
        return len(value)
    except (ValueError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """
    ضرب دو عدد در template
    مثال: {{ 5|mul:3 }} -> 15
    """
    try:
        from decimal import Decimal
        return Decimal(str(value)) * Decimal(str(arg))
    except (ValueError, TypeError):
        return Decimal('0')


# نام ماه‌های شمسی (مطابق تقویم جلالی در کامپوننت)
JALALI_MONTH_NAMES = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]


@register.filter
def jalali_date_display(value):
    """
    نمایش تاریخ شمسی به صورت «روز ماه سال» مثلاً 15 بهمن 1404
    value: jdatetime.date یا None
    """
    if value is None:
        return '—'
    try:
        import jdatetime
        if isinstance(value, jdatetime.date):
            jd = value
        else:
            return str(value)
        if jd.month < 1 or jd.month > 12:
            return str(value)
        month_name = JALALI_MONTH_NAMES[jd.month - 1]
        day = jd.day
        year = jd.year
        return f"{day} {month_name} {year}"
    except (AttributeError, TypeError, IndexError):
        return str(value)


@register.filter
def jalali_datetime_display(value, time_arg=None):
    """
    نمایش تاریخ و زمان شمسی به صورت «روز ماه سال HH:MM» مثلاً 15 بهمن 1404 14:49
    value: jdatetime.date یا None
    time_arg: زمان (time object یا str) اختیاری
    """
    base = jalali_date_display(value)
    if base == '—':
        return base
    if time_arg is None:
        return base
    try:
        if hasattr(time_arg, 'hour') and hasattr(time_arg, 'minute'):
            hour, minute = time_arg.hour, time_arg.minute
        elif isinstance(time_arg, str) and ':' in time_arg:
            parts = time_arg.split(':')
            hour = int(parts[0]) if parts else 0
            minute = int(parts[1]) if len(parts) > 1 else 0
        else:
            return base
        return f"{base} {hour:02d}:{minute:02d}"
    except (TypeError, ValueError):
        return base


@register.filter
def jdate_to_gregorian(value):
    """
    تبدیل jdatetime.date به رشته تاریخ میلادی YYYY-MM-DD برای data-gdate در datepicker
    """
    if value is None:
        return ''
    try:
        import jdatetime
        if isinstance(value, jdatetime.date):
            g = value.togregorian()
            return g.strftime('%Y-%m-%d')
        return ''
    except (AttributeError, TypeError):
        return ''


@register.filter
def jdatetime_to_gregorian(value, time_arg=None):
    """
    ترکیب تاریخ شمسی و زمان به رشته میلادی YYYY-MM-DD HH:MM برای data-gdate در datepicker با زمان
    """
    date_str = jdate_to_gregorian(value)
    if not date_str:
        return ''
    if time_arg is None:
        return date_str + ' 00:00'
    try:
        hour = getattr(time_arg, 'hour', 0)
        minute = getattr(time_arg, 'minute', 0)
        return f"{date_str} {hour:02d}:{minute:02d}"
    except (TypeError, ValueError):
        return date_str + ' 00:00' 