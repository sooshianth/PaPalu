# -*- coding: utf-8 -*-
"""
دستور مدیریتی برای بررسی تنظیمات FieldPermission

استفاده:
    python manage.py check_field_permissions
    python manage.py check_field_permissions --username=USERNAME
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.RBACModel import Role, UserFieldPermission, FieldPermission
from django.contrib.contenttypes.models import ContentType
from core.PersonFolder import Person


class Command(BaseCommand):
    help = 'Check Field Permission configurations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Check permissions for a specific user',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        
        self.stdout.write(self.style.SUCCESS('\n=== Field Permission System Status ===\n'))
        
        # بررسی وجود FieldPermission ها
        fps = FieldPermission.objects.all()
        self.stdout.write(f'Total FieldPermissions: {fps.count()}')
        
        for fp in fps:
            choices_count = fp.field_choices.count()
            denied_count = fp.field_choices.filter(allowed=False).count()
            
            self.stdout.write(f'\n📋 FieldPermission: {fp.name}')
            self.stdout.write(f'   Total Choices: {choices_count}')
            self.stdout.write(f'   Denied Fields: {denied_count}')
            
            # نمایش فیلدهای محدود شده
            denied = fp.field_choices.filter(allowed=False)
            if denied.exists():
                self.stdout.write('   Restrictions:')
                for choice in denied:
                    self.stdout.write(
                        f'     ✗ {choice.content_type.app_label}.{choice.content_type.model}.{choice.field_name} ({choice.access_type})'
                    )
        
        self.stdout.write(self.style.SUCCESS('\n=== Roles and Field Permissions ===\n'))
        
        roles = Role.objects.prefetch_related('field_permissions').all()
        for role in roles:
            fps = list(role.field_permissions.all())
            fp_names = [fp.name for fp in fps]
            user_count = role.users.count()
            
            if fp_names:
                self.stdout.write(self.style.SUCCESS(f'✓ Role: {role.name}'))
                self.stdout.write(f'   FieldPermissions: {", ".join(fp_names)}')
                self.stdout.write(f'   Users in role: {user_count}')
                if user_count > 0:
                    users = ', '.join([u.username for u in role.users.all()[:5]])
                    self.stdout.write(f'   Sample users: {users}')
            else:
                self.stdout.write(self.style.WARNING(f'⚠ Role: {role.name} (NO FieldPermission assigned)'))
                self.stdout.write(f'   Users in role: {user_count}')
        
        # اگر username داده شده، بررسی خاص برای آن کاربر
        if username:
            self.stdout.write(self.style.SUCCESS(f'\n=== Checking User: {username} ===\n'))
            
            try:
                user = User.objects.get(username=username)
                
                if user.is_superuser:
                    self.stdout.write(self.style.WARNING('⚠ This user is a SUPERUSER - all field restrictions are IGNORED!'))
                
                # بررسی UserFieldPermission
                try:
                    ufp = user.field_permission
                    if ufp.field_permission:
                        self.stdout.write(self.style.SUCCESS(f'✓ User has UserFieldPermission: {ufp.field_permission.name}'))
                        denied = ufp.field_permission.field_choices.filter(allowed=False)
                        if denied.exists():
                            self.stdout.write('   Restrictions:')
                            for choice in denied[:10]:
                                self.stdout.write(
                                    f'     ✗ {choice.content_type.model}.{choice.field_name} ({choice.access_type})'
                                )
                    else:
                        self.stdout.write(self.style.WARNING('⚠ User has UserFieldPermission entry but NO FieldPermission assigned'))
                except UserFieldPermission.DoesNotExist:
                    self.stdout.write(self.style.WARNING('⚠ User has NO UserFieldPermission'))
                
                # بررسی نقش‌های کاربر
                user_roles = user.roles.prefetch_related('field_permissions').all()
                if user_roles.exists():
                    self.stdout.write(f'\n✓ User has {user_roles.count()} role(s):')
                    for role in user_roles:
                        fps = list(role.field_permissions.all())
                        if fps:
                            fp_names = ', '.join(fp.name for fp in fps)
                            self.stdout.write(self.style.SUCCESS(f'   ✓ Role: {role.name} → FieldPermissions: {fp_names}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'   ⚠ Role: {role.name} → NO FieldPermission'))
                else:
                    self.stdout.write(self.style.WARNING('⚠ User has NO roles assigned'))
                
                # تست عملی
                self.stdout.write(self.style.SUCCESS('\n=== Practical Test ===\n'))
                self.stdout.write('Testing access to Person.name field:')
                
                from core.helpers import check_field_access_prefer_edit
                
                can_edit = check_field_access_prefer_edit(user, Person, 'name')
                can_view = check_field_access_prefer_edit(user, Person, 'name')
                
                if can_edit:
                    self.stdout.write(self.style.SUCCESS('   ✓ User CAN access Person.name (edit mode)'))
                else:
                    self.stdout.write(self.style.ERROR('   ✗ User CANNOT access Person.name (edit mode)'))
                
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'✗ User "{username}" not found'))
        
        # خلاصه و توصیه‌ها
        self.stdout.write(self.style.SUCCESS('\n=== Summary & Recommendations ===\n'))
        
        # بررسی کلی سیستم
        from django.db.models import Count
        roles_without_fp = Role.objects.annotate(fp_count=Count('field_permissions')).filter(fp_count=0).count()
        users_with_ufp = UserFieldPermission.objects.count()
        
        self.stdout.write(f'Roles without FieldPermission: {roles_without_fp}')
        self.stdout.write(f'Users with UserFieldPermission: {users_with_ufp}')
        
        if fps.count() > 0:
            self.stdout.write(self.style.SUCCESS('\n✓ Field Permissions are defined'))
            
            roles_with_fp = Role.objects.annotate(fp_count=Count('field_permissions')).filter(fp_count__gt=0).count()
            if roles_with_fp == 0 and users_with_ufp == 0:
                self.stdout.write(self.style.ERROR('\n✗ WARNING: No Role or User is connected to any FieldPermission!'))
                self.stdout.write(self.style.WARNING('   → Field restrictions will NOT work!'))
                self.stdout.write(self.style.WARNING('   → Please assign FieldPermission to Roles or Users in Django Admin'))
        else:
            self.stdout.write(self.style.WARNING('\n⚠ No FieldPermissions defined yet'))
        
        self.stdout.write('\n')

