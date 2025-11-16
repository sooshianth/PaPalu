"""
اسکریپت تست برای بررسی دسترسی فیلدها
این اسکریپت نشان می‌دهد که چگونه سیستم دسترسی فیلدها کار می‌کند
"""

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from core.RBACModel import user_has_field_access, get_accessible_fields
from core.PersonFolder import Person


def create_test_field_access_rules(username):
    """
    ایجاد قوانین تستی برای یک کاربر
    
    Args:
        username: نام کاربری
    """
    try:
        user = User.objects.get(username=username)
        person_ct = ContentType.objects.get_for_model(Person)
        
        print(f"\n🔧 ایجاد قوانین دسترسی برای کاربر: {username}")
        print("=" * 60)
        
        # حذف قوانین قبلی
        deleted_count = FieldAccessRule.objects.filter(user=user).delete()[0]
        if deleted_count > 0:
            print(f"✅ {deleted_count} قانون قبلی حذف شد")
        
        # ایجاد قوانین جدید - محدود کردن دسترسی به برخی فیلدها
        rules_to_create = [
            # فیلدهایی که کاربر نمی‌تواند ببیند (view)
            ('national_id', 'view', False, 'عدم مشاهده کد ملی'),
            ('accounting_code', 'view', False, 'عدم مشاهده کد حسابداری'),
            
            # فیلدهایی که کاربر نمی‌تواند ویرایش کند (edit)
            ('name', 'edit', False, 'عدم ویرایش نام'),
            ('nature', 'edit', False, 'عدم ویرایش نوع'),
            ('description', 'edit', False, 'عدم ویرایش توضیحات'),
        ]
        
        created_rules = []
        for field_name, access_type, allowed, description in rules_to_create:
            rule, created = FieldAccessRule.objects.get_or_create(
                user=user,
                content_type=person_ct,
                field_name=field_name,
                access_type=access_type,
                defaults={'allowed': allowed}
            )
            
            if created:
                created_rules.append(rule)
                status = "❌ غیرمجاز" if not allowed else "✅ مجاز"
                print(f"  {status} | {field_name} | {access_type} | {description}")
        
        print(f"\n✅ تعداد {len(created_rules)} قانون جدید ایجاد شد")
        print("=" * 60)
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ خطا: کاربر '{username}' یافت نشد")
        return False
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
        return False


def test_field_access(username):
    """
    تست دسترسی فیلدها برای یک کاربر
    
    Args:
        username: نام کاربری
    """
    try:
        user = User.objects.get(username=username)
        person_ct = ContentType.objects.get_for_model(Person)
        
        print(f"\n🔍 بررسی دسترسی فیلدها برای کاربر: {username}")
        print("=" * 60)
        
        # فیلدهای مورد آزمایش
        test_fields = [
            ('national_id', 'کد ملی'),
            ('name', 'نام'),
            ('nature', 'نوع'),
            ('accounting_code', 'کد حسابداری'),
            ('sales_expert', 'کارشناس فروش'),
            ('description', 'توضیحات'),
        ]
        
        print("\n📋 دسترسی مشاهده (view):")
        print("-" * 60)
        for field_name, field_label in test_fields:
            rule = FieldAccessRule.objects.filter(
                user=user,
                content_type=person_ct,
                field_name=field_name,
                access_type='view'
            ).first()
            
            if rule is None:
                status = "✅ مجاز (قانون تعریف نشده)"
                has_access = True
            else:
                has_access = rule.allowed
                status = "✅ مجاز" if has_access else "❌ غیرمجاز"
            
            print(f"  {status} | {field_label} ({field_name})")
        
        print("\n✏️  دسترسی ویرایش (edit):")
        print("-" * 60)
        for field_name, field_label in test_fields:
            rule = FieldAccessRule.objects.filter(
                user=user,
                content_type=person_ct,
                field_name=field_name,
                access_type='edit'
            ).first()
            
            if rule is None:
                status = "✅ مجاز (قانون تعریف نشده)"
                has_access = True
            else:
                has_access = rule.allowed
                status = "✅ مجاز" if has_access else "❌ غیرمجاز"
            
            print(f"  {status} | {field_label} ({field_name})")
        
        print("\n" + "=" * 60)
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ خطا: کاربر '{username}' یافت نشد")
        return False
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
        return False


def clear_field_access_rules(username):
    """
    حذف تمام قوانین دسترسی فیلد برای یک کاربر
    
    Args:
        username: نام کاربری
    """
    try:
        user = User.objects.get(username=username)
        
        print(f"\n🗑️  حذف قوانین دسترسی برای کاربر: {username}")
        print("=" * 60)
        
        deleted_count = FieldAccessRule.objects.filter(user=user).delete()[0]
        print(f"✅ {deleted_count} قانون حذف شد")
        print("=" * 60)
        
        return True
        
    except User.DoesNotExist:
        print(f"❌ خطا: کاربر '{username}' یافت نشد")
        return False
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
        return False


def show_all_rules():
    """
    نمایش تمام قوانین دسترسی فیلد موجود
    """
    print("\n📊 تمام قوانین دسترسی فیلد:")
    print("=" * 60)
    
    rules = FieldAccessRule.objects.all().order_by('user__username', 'content_type', 'field_name')
    
    if not rules.exists():
        print("هیچ قانونی یافت نشد!")
        print("=" * 60)
        return
    
    current_user = None
    for rule in rules:
        if current_user != rule.user.username:
            current_user = rule.user.username
            print(f"\n👤 کاربر: {current_user}")
            print("-" * 60)
        
        status = "✅ مجاز" if rule.allowed else "❌ غیرمجاز"
        model_name = rule.content_type.model
        print(f"  {status} | {model_name}.{rule.field_name} | {rule.get_access_type_display()}")
    
    print("\n" + "=" * 60)


# =============================================================================
# استفاده:
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 اسکریپت تست سیستم دسترسی فیلدها")
    print("=" * 60)
    
    # نمایش راهنما
    print("\n📖 راهنمای استفاده:")
    print("-" * 60)
    print("1. برای ایجاد قوانین تستی:")
    print("   >>> from sales.test_field_access import create_test_field_access_rules")
    print("   >>> create_test_field_access_rules('username')")
    print()
    print("2. برای تست دسترسی فیلدها:")
    print("   >>> from sales.test_field_access import test_field_access")
    print("   >>> test_field_access('username')")
    print()
    print("3. برای حذف قوانین:")
    print("   >>> from sales.test_field_access import clear_field_access_rules")
    print("   >>> clear_field_access_rules('username')")
    print()
    print("4. برای نمایش تمام قوانین:")
    print("   >>> from sales.test_field_access import show_all_rules")
    print("   >>> show_all_rules()")
    print("=" * 60 + "\n")

