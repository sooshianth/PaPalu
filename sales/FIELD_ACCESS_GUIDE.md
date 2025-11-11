# راهنمای سیستم دسترسی فیلدها

## مشکل قبلی و راه‌حل

### مشکل
قبلاً در `customer_views.py`، منطق بررسی دسترسی فیلدها **اشتباه** بود:

```python
# ❌ کد اشتباه قبلی:
has_access = FieldAccessRule.objects.filter(
    user=user,
    content_type=content_type,
    field_name=model_field_name,
    access_type='edit',
    allowed=False
).exists()

accessible_fields[form_field_name] = not has_access
```

**چرا اشتباه بود؟**
- اگر قانونی با `allowed=False` وجود داشت، `has_access = True` و سپس `accessible_fields = False` ✅
- اما اگر قانونی با `allowed=False` **وجود نداشت**، `has_access = False` و سپس `accessible_fields = True` ❌

این یعنی **حتی اگر قانون دسترسی تعریف شده بود، اگر `allowed=True` بود، نادیده گرفته می‌شد!**

### راه‌حل
کد جدید و صحیح:

```python
# ✅ کد صحیح جدید:
rule = FieldAccessRule.objects.filter(
    user=user,
    content_type=content_type,
    field_name=model_field_name,
    access_type='edit'
).first()

if rule is None:
    # اگر هیچ قانونی تعریف نشده، دسترسی داده می‌شود
    accessible_fields[form_field_name] = True
else:
    # اگر قانون وجود دارد، مقدار allowed را بررسی می‌کنیم
    accessible_fields[form_field_name] = rule.allowed
```

## نحوه کار سیستم

### 1. مدل FieldAccessRule

```python
class FieldAccessRule(models.Model):
    user = models.ForeignKey(User)           # کاربر
    content_type = models.ForeignKey(ContentType)  # مدل (مثلاً Person)
    field_name = models.CharField()          # نام فیلد (مثلاً 'name')
    access_type = models.CharField()         # نوع دسترسی: 'view', 'edit', 'delete'
    allowed = models.BooleanField()          # مجاز؟ True/False
```

### 2. منطق دسترسی

**قانون کلی:**
- اگر **هیچ قانونی** برای فیلد تعریف نشده → دسترسی **مجاز است** ✅
- اگر قانون با `allowed=True` → دسترسی **مجاز است** ✅
- اگر قانون با `allowed=False` → دسترسی **غیرمجاز است** ❌

### 3. انواع دسترسی

1. **`view`**: مشاهده فیلد (در لیست‌ها و جزئیات)
2. **`edit`**: ویرایش فیلد (در فرم‌های ایجاد و ویرایش)
3. **`delete`**: حذف فیلد (در عملیات حذف)

## مثال‌های کاربردی

### مثال 1: محدود کردن مشاهده کد ملی

```python
from access.models.FieldAccessUserModel import FieldAccessRule
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from core.PersonFolder import Person

user = User.objects.get(username='john')
person_ct = ContentType.objects.get_for_model(Person)

# این کاربر نمی‌تواند کد ملی را ببیند
FieldAccessRule.objects.create(
    user=user,
    content_type=person_ct,
    field_name='national_id',
    access_type='view',
    allowed=False
)
```

### مثال 2: محدود کردن ویرایش نام

```python
# این کاربر نمی‌تواند نام را ویرایش کند
FieldAccessRule.objects.create(
    user=user,
    content_type=person_ct,
    field_name='name',
    access_type='edit',
    allowed=False
)
```

### مثال 3: استفاده در View

```python
from access.models.FieldAccessUserModel import FieldAccessRule

def my_view(request):
    user = request.user
    person = Person.objects.first()
    
    # بررسی دسترسی به یک فیلد خاص
    has_access = FieldAccessRule.has_field_access(user, person, 'national_id', 'view')
    
    if has_access:
        print(person.national_id)
    else:
        print("دسترسی ندارید")
```

## تست کردن

برای تست کردن سیستم:

```python
# 1. وارد Django shell شوید
python manage.py shell

# 2. import کنید
from sales.test_field_access import *

# 3. ایجاد قوانین تستی
create_test_field_access_rules('username')

# 4. تست دسترسی
test_field_access('username')

# 5. نمایش تمام قوانین
show_all_rules()

# 6. حذف قوانین
clear_field_access_rules('username')
```

## تغییرات انجام شده

### 1. در `customer_views.py`

#### الف) تابع `get_accessible_form_fields`
- **قبل**: منطق اشتباه با `allowed=False` و `not has_access`
- **حالا**: منطق صحیح با بررسی مستقیم `rule.allowed`

#### ب) تابع `get_accessible_customer_fields` (جدید)
- برای بررسی دسترسی به فیلدهای لیست مشتریان
- نوع دسترسی: `view` (نه `edit`)

#### ج) تابع `customer_list_view`
- اضافه شدن `accessible_fields` به context

### 2. در `customer_list.html`

- **قبل**: همه فیلدها بدون بررسی نمایش داده می‌شدند
- **حالا**: فقط فیلدهایی که کاربر دسترسی دارد نمایش داده می‌شوند

```django
{% if accessible_fields.national_id %}
<td>{{ customer.national_id }}</td>
{% endif %}
```

## نکات مهم

1. **Superuser**: همیشه به همه فیلدها دسترسی دارد
2. **Default**: اگر قانونی تعریف نشده، دسترسی مجاز است
3. **Performance**: استفاده از `.first()` به جای `.exists()` + `.get()`
4. **Consistency**: همیشه از همان منطق استفاده کنید

## خطاهای رایج

### ❌ اشتباه 1: استفاده از `filter(..., allowed=False).exists()`

```python
# ❌ اشتباه:
has_no_access = FieldAccessRule.objects.filter(
    user=user,
    field_name='name',
    access_type='view',
    allowed=False
).exists()

if not has_no_access:
    # این اشتباه است!
```

### ✅ صحیح:

```python
# ✅ صحیح:
rule = FieldAccessRule.objects.filter(
    user=user,
    field_name='name',
    access_type='view'
).first()

has_access = True if rule is None else rule.allowed
```

### ❌ اشتباه 2: فراموش کردن بررسی در Template

```django
<!-- ❌ اشتباه: -->
<td>{{ customer.national_id }}</td>
```

### ✅ صحیح:

```django
<!-- ✅ صحیح: -->
{% if accessible_fields.national_id %}
<td>{{ customer.national_id }}</td>
{% endif %}
```

## پشتیبانی

اگر سوالی دارید یا مشکلی پیش آمد:
1. فایل `test_field_access.py` را اجرا کنید
2. `show_all_rules()` را فراخوانی کنید
3. قوانین را بررسی کنید و مطمئن شوید که صحیح تعریف شده‌اند

