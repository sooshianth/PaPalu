from django.db import models
from django.contrib.auth.models import User
from .TaskPermission import TaskPermission


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    task_permission = models.ForeignKey(TaskPermission, on_delete=models.SET_NULL, null=True)
    users = models.ManyToManyField(User, related_name='roles', blank=True)

    def __str__(self):
        return self.name


class UserTaskPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='task_permission')
    task_permission = models.ForeignKey(TaskPermission, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.user.username}"


def user_has_task(user, task_code):
    # Check roles
    for role in user.roles.all():
        if role.task_permission and task_code in role.task_permission.tasks:
            return True
    
    # Check user's own task permission
    try:
        if user.task_permission.task_permission and task_code in user.task_permission.task_permission.tasks:
            return True
    except UserTaskPermission.DoesNotExist:
        pass
    
    return False
