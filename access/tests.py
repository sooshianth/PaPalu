from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from .models import FieldAccessRule


class FieldAccessRuleTestCase(TestCase):
    """تست‌های مربوط به سیستم دسترسی فیلدها"""
    
    def setUp(self):
        """راه‌اندازی داده‌های تست"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        self.user_ct = ContentType.objects.get_for_model(User)
    
    def test_create_field_access_rule(self):
        """تست ایجاد قانون دسترسی"""
        rule = FieldAccessRule.objects.create(
            user=self.user,
            content_type=self.user_ct,
            field_name='email',
            access_type='view',
            allowed=True
        )
        self.assertEqual(rule.user, self.user)
        self.assertEqual(rule.field_name, 'email')
        self.assertTrue(rule.allowed)
    
    def test_unique_constraint(self):
        """تست محدودیت unique_together"""
        FieldAccessRule.objects.create(
            user=self.user,
            content_type=self.user_ct,
            field_name='email',
            access_type='view',
            allowed=True
        )
        
        # تلاش برای ایجاد قانون تکراری
        with self.assertRaises(Exception):
            FieldAccessRule.objects.create(
                user=self.user,
                content_type=self.user_ct,
                field_name='email',
                access_type='view',
                allowed=False
            )
    
    def test_has_field_access_allowed(self):
        """تست بررسی دسترسی مجاز"""
        FieldAccessRule.objects.create(
            user=self.user,
            content_type=self.user_ct,
            field_name='email',
            access_type='view',
            allowed=True
        )
        
        has_access = FieldAccessRule.has_field_access(
            self.user, self.user, 'email', 'view'
        )
        self.assertTrue(has_access)
    
    def test_has_field_access_denied(self):
        """تست بررسی دسترسی غیرمجاز"""
        FieldAccessRule.objects.create(
            user=self.user,
            content_type=self.user_ct,
            field_name='password',
            access_type='view',
            allowed=False
        )
        
        has_access = FieldAccessRule.has_field_access(
            self.user, self.user, 'password', 'view'
        )
        self.assertFalse(has_access)
    
    def test_superuser_has_all_access(self):
        """تست اینکه سوپریوزر به همه چیز دسترسی دارد"""
        FieldAccessRule.objects.create(
            user=self.superuser,
            content_type=self.user_ct,
            field_name='password',
            access_type='view',
            allowed=False
        )
        
        has_access = FieldAccessRule.has_field_access(
            self.superuser, self.user, 'password', 'view'
        )
        self.assertTrue(has_access)
    
    def test_default_access_when_no_rule(self):
        """تست دسترسی پیش‌فرض زمانی که قانونی تعریف نشده"""
        has_access = FieldAccessRule.has_field_access(
            self.user, self.user, 'username', 'view'
        )
        # به طور پیش‌فرض دسترسی داده می‌شود
        self.assertTrue(has_access)
    
    def test_get_accessible_fields(self):
        """تست گرفتن لیست فیلدهای قابل دسترسی"""
        # محدود کردن دسترسی به فیلد password
        FieldAccessRule.objects.create(
            user=self.user,
            content_type=self.user_ct,
            field_name='password',
            access_type='view',
            allowed=False
        )
        
        accessible_fields = FieldAccessRule.get_accessible_fields(
            self.user, User, 'view'
        )
        
        self.assertIn('username', accessible_fields)
        self.assertIn('email', accessible_fields)
        self.assertNotIn('password', accessible_fields)
    
    def test_string_representation(self):
        """تست نمایش رشته‌ای مدل"""
        rule = FieldAccessRule.objects.create(
            user=self.user,
            content_type=self.user_ct,
            field_name='email',
            access_type='edit',
            allowed=True
        )
        
        expected = f"testuser - user - email - ویرایش (مجاز)"
        self.assertEqual(str(rule), expected)

