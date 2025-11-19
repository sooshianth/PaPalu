"""
نمونه‌های استفاده از سیستم دسترسی فیلدها

این فایل شامل مثال‌هایی از نحوه استفاده از سیستم کنترل دسترسی فیلدها است.
"""

# ===== مثال 1: بررسی دسترسی به یک فیلد خاص =====
"""
from access.models import FieldAccessRule
from django.contrib.auth.models import User
from core.PersonFolder.PersonModel import Person  # مثال

user = User.objects.get(username='john')
person = Person.objects.first()

# بررسی دسترسی مشاهده
has_access = FieldAccessRule.has_field_access(user, person, 'email', 'view')
if has_access:
    print(person.email)
else:
    print("دسترسی ندارید")
"""


# ===== مثال 2: گرفتن لیست فیلدهای قابل دسترسی =====
"""
from access.models import FieldAccessRule
from django.contrib.auth.models import User
from core.PersonFolder.PersonModel import Person

user = User.objects.get(username='john')

# فیلدهایی که کاربر می‌تواند ببیند
viewable_fields = FieldAccessRule.get_accessible_fields(user, Person, 'view')
print(f"فیلدهای قابل مشاهده: {viewable_fields}")

# فیلدهایی که کاربر می‌تواند ویرایش کند
editable_fields = FieldAccessRule.get_accessible_fields(user, Person, 'edit')
print(f"فیلدهای قابل ویرایش: {editable_fields}")
"""


# ===== مثال 3: استفاده از توابع کمکی =====
"""
from access.helpers import (
    get_field_value_safe,
    set_field_value_safe,
    can_edit_field,
    get_model_dict_with_access
)
from django.contrib.auth.models import User
from core.PersonFolder.PersonModel import Person

user = User.objects.get(username='john')
person = Person.objects.first()

# گرفتن مقدار یک فیلد با بررسی دسترسی
email = get_field_value_safe(user, person, 'email', default='دسترسی ندارید')
print(f"Email: {email}")

# تنظیم مقدار یک فیلد با بررسی دسترسی
success = set_field_value_safe(user, person, 'phone', '09123456789')
if success:
    person.save()
    print("تغییرات ذخیره شد")
else:
    print("شما دسترسی ویرایش این فیلد را ندارید")

# بررسی اینکه آیا می‌تواند ویرایش کند
if can_edit_field(user, person, 'first_name'):
    print("می‌توانید نام را ویرایش کنید")

# تبدیل مدل به دیکشنری با توجه به دسترسی
person_dict = get_model_dict_with_access(user, person, 'view')
print(person_dict)
"""


# ===== مثال 4: استفاده در یک View =====
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from access.helpers import get_model_dict_with_access
from core.PersonFolder.PersonModel import Person

@login_required
def person_detail(request, person_id):
    person = Person.objects.get(pk=person_id)
    
    # فقط فیلدهایی که کاربر دسترسی دارد را نمایش بده
    person_data = get_model_dict_with_access(request.user, person, 'view')
    
    return render(request, 'person_detail.html', {
        'person_data': person_data
    })
"""


# ===== مثال 5: فیلتر کردن فیلدها در یک فرم =====
"""
from django import forms
from access.helpers import filter_fields_by_access
from core.PersonFolder.PersonModel import Person

class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and self.instance:
            # فقط فیلدهایی که کاربر می‌تواند ویرایش کند را نمایش بده
            all_fields = list(self.fields.keys())
            editable_fields = filter_fields_by_access(
                self.user, 
                self.instance, 
                all_fields, 
                'edit'
            )
            
            # فیلدهای غیرقابل ویرایش را حذف کن
            for field_name in all_fields:
                if field_name not in editable_fields:
                    del self.fields[field_name]

# استفاده در view:
# form = PersonForm(instance=person, user=request.user)
"""


# ===== مثال 6: ایجاد قانون دسترسی از طریق کد =====
"""
from access.models import FieldAccessRule
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from core.PersonFolder.PersonModel import Person

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

# جلوگیری از ویرایش فیلد phone
FieldAccessRule.objects.create(
    user=user,
    content_type=person_ct,
    field_name='phone',
    access_type='edit',
    allowed=False
)

# اجازه حذف فیلد address
FieldAccessRule.objects.create(
    user=user,
    content_type=person_ct,
    field_name='address',
    access_type='delete',
    allowed=True
)
"""


# ===== مثال 7: ایجاد قوانین دسترسی برای چندین فیلد =====
"""
from access.models import FieldAccessRule
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from core.PersonFolder.PersonModel import Person

user = User.objects.get(username='john')
person_ct = ContentType.objects.get_for_model(Person)

# فیلدهای حساس که نباید دیده شوند
sensitive_fields = ['password', 'credit_card', 'ssn']

for field in sensitive_fields:
    FieldAccessRule.objects.get_or_create(
        user=user,
        content_type=person_ct,
        field_name=field,
        access_type='view',
        defaults={'allowed': False}
    )
"""

