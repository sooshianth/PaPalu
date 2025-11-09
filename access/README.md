# سیستم مدیریت دسترسی فیلدها

این ماژول یک سیستم ساده و کاربردی برای کنترل دسترسی کاربران به فیلدهای مختلف مدل‌ها در جنگو فراهم می‌کند.

## ویژگی‌ها

- کنترل دسترسی در سه سطح: مشاهده (view)، ویرایش (edit)، حذف (delete)
- قابلیت تعریف قوانین دسترسی برای هر کاربر، هر مدل و هر فیلد
- API ساده برای بررسی دسترسی‌ها
- توابع کمکی برای استفاده آسان در View ها و Form ها
- پنل ادمین کامل برای مدیریت قوانین
- اعتبارسنجی خودکار وجود فیلد در مدل

## نصب

1. اپلیکیشن `access` از قبل در `INSTALLED_APPS` در فایل `settings.py` اضافه شده است:

```python
INSTALLED_APPS = [
    ...
    'access',
]
```

2. Migration ها را اجرا کنید:

```cmd
python manage.py makemigrations access
python manage.py migrate access
```

## استفاده پایه

### 1. بررسی دسترسی به یک فیلد

```python
from access.models import FieldAccessRule
from django.contrib.auth.models import User

user = User.objects.get(username='john')
person = Person.objects.first()

# بررسی دسترسی مشاهده
if FieldAccessRule.has_field_access(user, person, 'email', 'view'):
    print(person.email)
else:
    print("دسترسی ندارید")
```

### 2. گرفتن لیست فیلدهای قابل دسترسی

```python
from access.models import FieldAccessRule

# فیلدهایی که کاربر می‌تواند ببیند
viewable_fields = FieldAccessRule.get_accessible_fields(user, Person, 'view')

# فیلدهایی که کاربر می‌تواند ویرایش کند
editable_fields = FieldAccessRule.get_accessible_fields(user, Person, 'edit')
```

### 3. استفاده از توابع کمکی

```python
from access.helpers import (
    get_field_value_safe,
    set_field_value_safe,
    can_edit_field
)

# گرفتن مقدار با بررسی دسترسی
email = get_field_value_safe(user, person, 'email', default='دسترسی ندارید')

# تنظیم مقدار با بررسی دسترسی
if set_field_value_safe(user, person, 'phone', '09123456789'):
    person.save()
    print("ذخیره شد")
```

### 4. استفاده در View

```python
from django.shortcuts import render
from access.helpers import get_model_dict_with_access

def person_detail(request, person_id):
    person = Person.objects.get(pk=person_id)
    person_data = get_model_dict_with_access(request.user, person, 'view')
    return render(request, 'person_detail.html', {'person_data': person_data})
```

### 5. استفاده در Form

```python
from django import forms
from access.helpers import filter_fields_by_access

class PersonForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and self.instance:
            all_fields = list(self.fields.keys())
            editable_fields = filter_fields_by_access(
                self.user, self.instance, all_fields, 'edit'
            )
            
            for field_name in all_fields:
                if field_name not in editable_fields:
                    del self.fields[field_name]
```

## ایجاد قوانین دسترسی

### از طریق پنل ادمین

1. وارد پنل ادمین شوید
2. به بخش "قوانین دسترسی فیلدها" بروید
3. روی "افزودن قانون دسترسی فیلد" کلیک کنید
4. فیلدها را پر کنید و ذخیره کنید

### از طریق کد

```python
from access.models import FieldAccessRule
from django.contrib.contenttypes.models import ContentType

user = User.objects.get(username='john')
person_ct = ContentType.objects.get_for_model(Person)

# جلوگیری از مشاهده فیلد email
FieldAccessRule.objects.create(
    user=user,
    content_type=person_ct,
    field_name='email',
    access_type='view',
    allowed=False
)
```

## مفاهیم مهم

### انواع دسترسی (access_type)

- `view`: دسترسی مشاهده فیلد
- `edit`: دسترسی ویرایش فیلد
- `delete`: دسترسی حذف فیلد

### رفتار پیش‌فرض

- اگر قانونی برای یک فیلد تعریف نشده باشد، به طور پیش‌فرض **دسترسی داده می‌شود**
- سوپریوزرها (superuser) همیشه به همه فیلدها دسترسی دارند

### مثال کاربردی

فرض کنید می‌خواهید:
- کاربران عادی نتوانند فیلد `salary` را ببینند
- کاربران عادی نتوانند فیلد `role` را ویرایش کنند

```python
user = User.objects.get(username='normal_user')
employee_ct = ContentType.objects.get_for_model(Employee)

# مخفی کردن حقوق
FieldAccessRule.objects.create(
    user=user,
    content_type=employee_ct,
    field_name='salary',
    access_type='view',
    allowed=False
)

# غیرقابل ویرایش کردن نقش
FieldAccessRule.objects.create(
    user=user,
    content_type=employee_ct,
    field_name='role',
    access_type='edit',
    allowed=False
)
```

## فایل‌های پروژه

- `models/FieldAccessUserModel.py`: مدل اصلی و متدهای آن
- `admin.py`: پنل ادمین
- `helpers.py`: توابع کمکی
- `tests.py`: تست‌ها
- `usage_example.py`: مثال‌های کاربردی

## تست

برای اجرای تست‌ها:

```cmd
python manage.py test access
```

## نکات مهم

1. همیشه قبل از دسترسی به فیلد، دسترسی کاربر را بررسی کنید
2. از توابع کمکی استفاده کنید تا کد تمیزتری داشته باشید
3. سوپریوزرها همیشه دسترسی کامل دارند
4. رفتار پیش‌فرض: اگر قانونی نباشد، دسترسی داده می‌شود

