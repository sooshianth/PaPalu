from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.RBACModel import TaskPermission
from .decorators import superuser_required
import json


@superuser_required
def users_view(request):
    """View for managing Users"""
    from django.contrib.auth.models import User
    from core.RBACModel import Role, UserTaskPermission, FieldPermission, UserFieldPermission
    
    users = User.objects.all().prefetch_related('roles', 'task_permission', 'field_permission').order_by('username')
    roles = Role.objects.all().order_by('name')
    task_permissions = TaskPermission.objects.all().order_by('name')
    field_permissions = FieldPermission.objects.all().order_by('name')
    
    # Get user roles and permissions
    users_data = []
    for user in users:
        user_roles = list(user.roles.all())
        
        try:
            user_task_perm = user.task_permission
            user_task_perm_id = user_task_perm.task_permission.id if user_task_perm.task_permission else None
        except UserTaskPermission.DoesNotExist:
            user_task_perm_id = None
        
        try:
            user_field_perm = user.field_permission
            user_field_perm_id = user_field_perm.field_permission.id if user_field_perm.field_permission else None
        except UserFieldPermission.DoesNotExist:
            user_field_perm_id = None
        
        users_data.append({
            'user': user,
            'roles': user_roles,
            'task_permission_id': user_task_perm_id,
            'field_permission_id': user_field_perm_id
        })
    
    context = {
        'users_data': users_data,
        'all_roles': roles,
        'task_permissions': task_permissions,
        'field_permissions': field_permissions,
        'active_page': 'users'
    }
    return render(request, 'perm_manager/users.html', context)


@superuser_required
@require_http_methods(["POST"])
def save_user_assignments(request):
    """API endpoint to save user role and permission assignments"""
    from django.contrib.auth.models import User
    from core.RBACModel import Role, UserTaskPermission, FieldPermission, UserFieldPermission
    
    try:
        data = json.loads(request.body)
        users_data = data.get('users', [])
        
        if not isinstance(users_data, list):
            return JsonResponse({'status': 'error', 'message': 'Invalid data format'}, status=400)
        
        for user_data in users_data:
            user_id = user_data.get('user_id')
            role_ids = user_data.get('role_ids', [])
            task_permission_id = user_data.get('task_permission_id')
            field_permission_id = user_data.get('field_permission_id')
            
            # Validate user_id
            if not user_id or not isinstance(user_id, int):
                return JsonResponse({'status': 'error', 'message': 'Valid user ID is required'}, status=400)
            
            # Validate role_ids
            if not isinstance(role_ids, list) or not all(isinstance(rid, int) for rid in role_ids):
                return JsonResponse({'status': 'error', 'message': 'Valid role IDs are required'}, status=400)
            
            # Validate task_permission_id
            if task_permission_id is not None and not isinstance(task_permission_id, int):
                return JsonResponse({'status': 'error', 'message': 'Valid task permission ID is required'}, status=400)
            
            # Validate field_permission_id
            if field_permission_id is not None and not isinstance(field_permission_id, int):
                return JsonResponse({'status': 'error', 'message': 'Valid field permission ID is required'}, status=400)
            
            user = User.objects.get(id=user_id)
            
            # Update roles
            user.roles.clear()
            for role_id in role_ids:
                role = Role.objects.get(id=role_id)
                user.roles.add(role)
            
            # Update special task permission
            if task_permission_id:
                task_perm = TaskPermission.objects.get(id=task_permission_id)
                UserTaskPermission.objects.update_or_create(
                    user=user,
                    defaults={'task_permission': task_perm}
                )
            else:
                UserTaskPermission.objects.filter(user=user).delete()
            
            # Update special field permission
            if field_permission_id:
                field_perm = FieldPermission.objects.get(id=field_permission_id)
                UserFieldPermission.objects.update_or_create(
                    user=user,
                    defaults={'field_permission': field_perm}
                )
            else:
                UserFieldPermission.objects.filter(user=user).delete()
        
        return JsonResponse({'status': 'success'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    except Role.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Role not found'}, status=404)
    except TaskPermission.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task permission not found'}, status=404)
    except FieldPermission.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Field permission not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)

