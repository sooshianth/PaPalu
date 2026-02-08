from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from .TaskPermission import TaskPermission
from .FieldPermission import FieldPermission


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    users = models.ManyToManyField(User, related_name='roles', blank=True)

    class Meta:
        verbose_name = 'RBAC | نقش'
        verbose_name_plural = 'RBAC | نقش‌ها'

    def __str__(self):
        return self.name
    
    def get_all_tasks(self):
        """
        تمام task های مرتبط با این نقش را از تمام TaskPermission های آن برمی‌گرداند
        """
        all_tasks = []
        for task_perm in self.task_permissions.all():
            if task_perm.tasks:
                all_tasks.extend(task_perm.tasks)
        return list(set(all_tasks))  # حذف موارد تکراری


class UserTaskPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='task_permission')
    task_permission = models.ForeignKey(TaskPermission, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'RBAC | مجوز دسترسی تسک برای کاربر'
        verbose_name_plural = 'RBAC | مجوزهای دسترسی تسک برای کاربران'

    def __str__(self):
        return f"{self.user.username}"


class UserFieldPermission(models.Model):
    """
    مجوز دسترسی فیلد برای کاربر
    هر کاربر می‌تواند یک مجوز دسترسی فیلد اختصاصی داشته باشد
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='field_permission',
        verbose_name='کاربر'
    )
    field_permission = models.ForeignKey(
        FieldPermission,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='مجوز دسترسی فیلد'
    )

    class Meta:
        verbose_name = 'RBAC | مجوز دسترسی فیلد کاربر'
        verbose_name_plural = 'RBAC | مجوزهای دسترسی فیلد کاربران'

    def __str__(self):
        return f"{self.user.username} - Field Permission"


def user_has_task(user, task_code):
    # Handle None or anonymous user
    if not user or not user.is_authenticated:
        return False

    # Superuser has access to everything
    if user.is_superuser:
        return True
    
    # Check roles - now checking all task_permissions for each role
    for role in user.roles.all():
        for task_perm in role.task_permissions.all():
            if task_perm.tasks and task_code in task_perm.tasks:
                return True
    
    # Check user's own task permission
    try:
        user_perm = user.task_permission
        if user_perm and user_perm.task_permission and user_perm.task_permission.tasks and task_code in user_perm.task_permission.tasks:
            return True
    except UserTaskPermission.DoesNotExist:
        pass
    except AttributeError:
        pass
    
    return False


def user_has_field_access(user, model_instance, field_name, access_type='view'):
    """
    بررسی اینکه آیا کاربر به فیلد خاصی دسترسی دارد یا نه
    
    Args:
        user: شیء کاربر
        model_instance: نمونه‌ای از مدل که می‌خواهیم بررسی کنیم
        field_name: نام فیلد
        access_type: نوع دسترسی (view, edit)
    
    Returns:
        True اگر کاربر دسترسی دارد، در غیر این صورت False
    """
    # Handle None or anonymous user
    if not user or not user.is_authenticated:
        return False
    
    # Superuser has access to everything
    if user.is_superuser:
        return True
    
    content_type = ContentType.objects.get_for_model(model_instance)
    
    # Check user's own field permission
    try:
        user_perm = user.field_permission
        if user_perm and user_perm.field_permission:
            field_choices = user_perm.field_permission.field_choices.filter(
                content_type=content_type,
                field_name=field_name,
                access_type=access_type
            )
            for choice in field_choices:
                if not choice.allowed:
                    return False
                return True
    except UserFieldPermission.DoesNotExist:
        pass
    except AttributeError:
        pass
    
    # Check roles - all field_permissions of each role
    for role in user.roles.all():
        for field_perm in role.field_permissions.all():
            field_choices = field_perm.field_choices.filter(
                content_type=content_type,
                field_name=field_name,
                access_type=access_type
            )
            for choice in field_choices:
                if not choice.allowed:
                    return False
                return True
    
    # اگر قانونی تعریف نشده، به طور پیش‌فرض دسترسی داده می‌شود
    return True


def get_accessible_fields(user, model_class, access_type='view'):
    """
    لیست فیلدهایی که کاربر به آن‌ها دسترسی دارد را برمی‌گرداند
    
    Args:
        user: شیء کاربر
        model_class: کلاس مدل
        access_type: نوع دسترسی (view, edit)
    
    Returns:
        لیست نام فیلدها
    """
    # Handle None or anonymous user
    if not user or not user.is_authenticated:
        return []
    
    # Superuser has access to everything
    if user.is_superuser:
        return [f.name for f in model_class._meta.get_fields()]
    
    content_type = ContentType.objects.get_for_model(model_class)
    
    # گرفتن همه فیلدها
    all_fields = [f.name for f in model_class._meta.get_fields()]
    denied_fields = set()
    
    # Check user's own field permission
    try:
        user_perm = user.field_permission
        if user_perm and user_perm.field_permission:
            field_choices = user_perm.field_permission.field_choices.filter(
                content_type=content_type,
                access_type=access_type
            )
            for choice in field_choices:
                if not choice.allowed:
                    denied_fields.add(choice.field_name)
    except UserFieldPermission.DoesNotExist:
        pass
    except AttributeError:
        pass
    
    # Check roles - all field_permissions of each role
    for role in user.roles.all():
        for field_perm in role.field_permissions.all():
            field_choices = field_perm.field_choices.filter(
                content_type=content_type,
                access_type=access_type
            )
            for choice in field_choices:
                if not choice.allowed:
                    denied_fields.add(choice.field_name)
    
    # فیلدهایی که قانون برایشان تعریف نشده، به طور پیش‌فرض قابل دسترسی هستند
    return [field for field in all_fields if field not in denied_fields]


def user_can_access_field(user, model_class, field_name, access_type='view'):
    """
    بررسی اینکه آیا کاربر به فیلد خاصی از یک مدل دسترسی دارد یا نه
    این تابع با model class به جای instance کار می‌کند
    
    Args:
        user: شیء کاربر
        model_class: کلاس مدل
        field_name: نام فیلد
        access_type: نوع دسترسی (view, edit)
    
    Returns:
        True اگر کاربر دسترسی دارد، در غیر این صورت False
    """
    # Handle None or anonymous user
    if not user or not user.is_authenticated:
        return False
    
    # Superuser has access to everything
    if user.is_superuser:
        return True
    
    content_type = ContentType.objects.get_for_model(model_class)
    
    # متغیر برای نگهداری اینکه آیا حداقل یک FieldPermission برای این کاربر تعریف شده
    has_any_field_permission = False
    # متغیر برای نگهداری اینکه آیا قانونی برای این فیلد خاص وجود دارد
    found_rule_for_this_field = False
    
    # Check user's own field permission
    try:
        user_perm = user.field_permission
        if user_perm and user_perm.field_permission:
            has_any_field_permission = True
            
            # بررسی آیا قانونی برای این access_type وجود دارد
            field_choices = user_perm.field_permission.field_choices.filter(
                content_type=content_type,
                field_name=field_name,
                access_type=access_type
            )
            
            if field_choices.exists():
                found_rule_for_this_field = True
                # اگر حتی یکی allowed=False باشد، دسترسی ندارد
                for choice in field_choices:
                    if not choice.allowed:
                        return False
                # اگر همه allowed=True باشند، دسترسی دارد
                return True
    except UserFieldPermission.DoesNotExist:
        pass
    except AttributeError:
        pass
    
    # Check roles - all field_permissions of each role
    for role in user.roles.all():
        for field_perm in role.field_permissions.all():
            has_any_field_permission = True
            
            # بررسی آیا قانونی برای این access_type وجود دارد
            field_choices = field_perm.field_choices.filter(
                content_type=content_type,
                field_name=field_name,
                access_type=access_type
            )
            
            if field_choices.exists():
                found_rule_for_this_field = True
                # اگر حتی یکی allowed=False باشد، دسترسی ندارد
                for choice in field_choices:
                    if not choice.allowed:
                        return False
                # اگر همه allowed=True باشند، دسترسی دارد
                return True
    
    # اگر قانونی برای این فیلد خاص پیدا شد و به اینجا رسیدیم، یعنی همه allowed=True بودند
    if found_rule_for_this_field:
        return True
    
    # اگر هیچ FieldPermission ای برای کاربر تعریف نشده، به طور پیش‌فرض دسترسی داده می‌شود
    if not has_any_field_permission:
        return True
    
    # اگر FieldPermission تعریف شده ولی قانونی برای این فیلد خاص نیست،
    # به طور پیش‌فرض دسترسی داده می‌شود (فیلدهای غیرمدیریت شده)
    return True
