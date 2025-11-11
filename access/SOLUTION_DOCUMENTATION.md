# راه‌حل مشکل ContentType و FieldAccessRule

## مشکل اولیه

مدل `FieldAccessRule` از `ContentType` برای ارجاع به مدل‌های مختلف استفاده می‌کند. مشکل این بود که Django همه مدل‌های سیستم را در `ContentType` ثبت نمی‌کرد و در نتیجه نمی‌توانستیم به همه مدل‌ها foreign key بزنیم.

## راه‌حل پیاده‌سازی شده

### 1. ثبت خودکار مدل‌ها در AppConfig

#### فایل `core/apps.py`
```python
class CoreConfig(AppConfig):
    def ready(self):
        # Import all models to ensure they are registered with ContentType
        # Product models
        from .ProductFolder import (
            Product, ProductionInfo, BOM, QualityControl, ProductSales
        )
        from .ProductFolder.ProductModel import PhysicalShape
        
        # Person models
        from .PersonFolder import (
            Person, PhoneNumber, PurchasePreference, ...
        )
        
        # و بقیه مدل‌ها...
```

**توضیح**: متد `ready()` بعد از آماده شدن اپلیکیشن اجرا می‌شود و همه مدل‌ها را import می‌کند تا Django آن‌ها را بشناسد.

#### فایل `access/apps.py`
```python
class AccessConfig(AppConfig):
    def ready(self):
        from .models.FieldAccessUserModel import FieldAccessRule
```

### 2. Management Command برای ثبت دستی مدل‌ها

#### فایل `core/management/commands/register_models.py`

یک command ساخته شد که همه مدل‌های core را در جدول `ContentType` ثبت می‌کند:

```bash
python manage.py register_models
```

این command:
- همه مدل‌های core را import می‌کند
- برای هر مدل یک رکورد در `ContentType` ایجاد می‌کند
- نتیجه را نمایش می‌دهد

### 3. ساده‌سازی __init__.py

فایل‌های `__init__.py` را خالی نگه داشتیم تا مشکل circular import ایجاد نشود:

```python
# core/__init__.py
default_app_config = 'core.apps.CoreConfig'

# access/__init__.py  
default_app_config = 'access.apps.AccessConfig'
```

## نحوه استفاده

### 1. ثبت اولیه مدل‌ها

بعد از راه‌اندازی پروژه، یک بار این command را اجرا کنید:

```bash
python manage.py register_models
```

خروجی:
```
Registering core models in ContentType...
  + Registered: productioninfo
  + Registered: bom
  + Registered: person
  ...
Total models registered: 44
Done! All core models are now registered in ContentType.
```

### 2. استفاده از FieldAccessRule در Django Admin

حالا می‌توانید در پنل ادمین Django:

1. وارد بخش "قوانین دسترسی فیلدها" شوید
2. یک قانون جدید ایجاد کنید
3. در فیلد "نوع مدل" می‌توانید **هر یک از ۴۶ مدل core** را انتخاب کنید:
   - Product
   - Person
   - Order
   - Allocation
   - Transport
   - Warehouse
   - و ۴۰ مدل دیگر...

### 3. استفاده برنامه‌نویسی

```python
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from access.models import FieldAccessRule
from core.ProductFolder.ProductModel import Product

# گرفتن ContentType برای مدل Product
product_ct = ContentType.objects.get_for_model(Product)

# ایجاد قانون دسترسی
rule = FieldAccessRule.objects.create(
    user=some_user,
    content_type=product_ct,
    field_name='name',
    access_type='edit',
    allowed=False
)

# بررسی دسترسی
product_instance = Product.objects.first()
has_access = FieldAccessRule.has_field_access(
    user=some_user,
    model_instance=product_instance,
    field_name='name',
    access_type='edit'
)

# گرفتن فیلدهای قابل دسترسی
accessible_fields = FieldAccessRule.get_accessible_fields(
    user=some_user,
    model_class=Product,
    access_type='view'
)
```

### 4. تست سیستم

برای تست کامل سیستم:

```bash
python test_field_access.py
```

این اسکریپت:
- تمام مدل‌های ثبت شده را نمایش می‌دهد
- یک کاربر تست ایجاد می‌کند
- قوانین دسترسی برای چند مدل ایجاد می‌کند
- نتایج را نمایش می‌دهد

## مدل‌های ثبت شده

در حال حاضر ۴۶ مدل از اپلیکیشن `core` در ContentType ثبت شده‌اند:

**محصولات (6 مدل)**:
- Product, PhysicalShape, ProductionInfo, BOM, QualityControl, ProductSales

**اشخاص (10 مدل)**:
- Person, PhoneNumber, PurchasePreference, PaymentPreference, Attachment, SocialNetwork, FinancialBanking, BankAccount, Representative, DeliveryAddress

**سفارشات (5 مدل)**:
- Order, OrderItem, ApprovalInfo, DocumentRelation, OrderDocument

**تخصیص (3 مدل)**:
- Allocation, AllocationProductInfo, AllocationSchedulingInfo

**حمل و نقل (5 مدل)**:
- Transport, ProductInfo, TruckInfo, Fare, LoadingScheduleInfo

**انبار (4 مدل)**:
- Inventory, InventoryProduct, Warehouse, DefaultItem

**مواد اولیه (5 مدل)**:
- Supplier, QualityParameter, RawMaterialPurchaseInfo, RawMaterialQualityControl, RawMaterial

**ورود به انبار (3 مدل)**:
- StockEntry, SourceStock, TargetStock

**تسویه (2 مدل)**:
- Settlement, TransactionDocument

**RBAC (3 مدل)**:
- TaskPermission, Role, UserTaskPermission

## مزایای این راه‌حل

1. ✅ **مقیاس‌پذیری**: هر مدل جدیدی که اضافه کنید، به صورت خودکار در ContentType ثبت می‌شود (فقط باید در `apps.py` import شود)

2. ✅ **عدم نیاز به Hard-Coding**: نیازی نیست برای هر مدل یک ForeignKey جداگانه بنویسید

3. ✅ **استفاده از قابلیت‌های Django**: از سیستم ContentType داخلی Django استفاده می‌کند

4. ✅ **سازگاری با Django Admin**: در پنل ادمین به صورت خودکار dropdown با تمام مدل‌ها نمایش داده می‌شود

5. ✅ **عملکرد بهینه**: از query های بهینه شده Django استفاده می‌کند

## نکات مهم

1. **یک بار اجرا کنید**: command `register_models` را فقط یک بار بعد از راه‌اندازی یا بعد از اضافه کردن مدل‌های جدید اجرا کنید

2. **Migration ها**: اگر مدل جدیدی اضافه کردید، حتماً migration بسازید و اجرا کنید

3. **Import در apps.py**: هر مدل جدید باید در متد `ready()` فایل `apps.py` import شود

4. **Circular Import**: از import کردن مدل‌ها در `__init__.py` خودداری کنید (مشکل circular import ایجاد می‌شود)

## عیب‌یابی

### مشکل: مدل جدید من در ContentType نیست

**راه‌حل**:
1. مدل را در `core/apps.py` متد `ready()` import کنید
2. `register_models` command را دوباره اجرا کنید
3. سرور Django را restart کنید

### مشکل: خطای "Apps aren't loaded yet"

**راه‌حل**:
- مدل‌ها را در `__init__.py` import نکنید
- فقط در `apps.py` متد `ready()` import کنید

### مشکل: مدل در Admin نمایش داده نمی‌شود

**راه‌حل**:
- مطمئن شوید مدل در `admin.py` ثبت شده است
- `register_models` را اجرا کنید

## تماس و پشتیبانی

برای مشکلات یا سوالات، به فایل‌های زیر مراجعه کنید:
- `access/README.md` - مستندات اصلی
- `access/usage_example.py` - مثال‌های استفاده
- `test_field_access.py` - تست سیستم

