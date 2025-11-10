from django.shortcuts import render
from .decorators import superuser_required


@superuser_required
def permissions_home_view(request):
    """Home view for permissions dashboard"""
    from django.contrib.auth.models import User
    from core.RBACModel import Role, TaskPermission
    
    task_permissions = TaskPermission.objects.all()
    roles = Role.objects.all()
    users = User.objects.all()
    
    context = {
        'task_permissions': task_permissions,
        'roles': roles,
        'users': users,
    }
    return render(request, 'perm_manager/permissions_home.html', context)

