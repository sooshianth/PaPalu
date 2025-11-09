from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.RBACModel import TaskPermission, TaskChoices
import json


def superuser_required(view_func):
    """Decorator to require superuser access"""
    return user_passes_test(lambda u: u.is_superuser)(view_func)


@superuser_required
def task_permissions_view(request):
    """View for managing TaskPermissions"""
    task_permissions = TaskPermission.objects.all().order_by('name')
    task_choices = [(code, label) for code, label in TaskChoices.choices]
    
    context = {
        'task_permissions': task_permissions,
        'task_choices': task_choices,
        'active_page': 'taskpermissions'
    }
    return render(request, 'PermissionManager/task_permissions.html', context)


@superuser_required
@require_http_methods(["POST"])
def save_task_permissions(request):
    """API endpoint to save task permission changes"""
    try:
        data = json.loads(request.body)
        valid_task_codes = [code for code, _ in TaskChoices.choices]
        
        for perm_data in data:
            perm_id = perm_data.get('id')
            tasks = perm_data.get('tasks', [])
            
            # Validate permission ID
            if not perm_id or not isinstance(perm_id, int):
                continue
            
            # Validate tasks - only allow valid TaskChoices
            if not isinstance(tasks, list):
                continue
            
            validated_tasks = [task for task in tasks if task in valid_task_codes]
            
            try:
                perm = TaskPermission.objects.get(id=perm_id)
                perm.tasks = validated_tasks
                perm.save()
            except TaskPermission.DoesNotExist:
                continue
        
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def add_task_permission(request):
    """API endpoint to add a new task permission"""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        # Validate name
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)
        
        if len(name) > 100:
            return JsonResponse({'status': 'error', 'message': 'Name too long (max 100 characters)'}, status=400)
        
        # Check for dangerous characters (basic validation)
        if any(char in name for char in ['<', '>', '"', "'"]):
            return JsonResponse({'status': 'error', 'message': 'Invalid characters in name'}, status=400)
        
        if TaskPermission.objects.filter(name=name).exists():
            return JsonResponse({'status': 'error', 'message': 'Name already exists'}, status=400)
        
        perm = TaskPermission.objects.create(name=name, tasks=[])
        
        return JsonResponse({
            'status': 'success',
            'id': perm.id,
            'name': perm.name
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def delete_task_permission(request):
    """API endpoint to delete a task permission"""
    try:
        data = json.loads(request.body)
        perm_id = data.get('id')
        
        # Validate ID
        if not perm_id or not isinstance(perm_id, int):
            return JsonResponse({'status': 'error', 'message': 'Valid ID is required'}, status=400)
        
        perm = TaskPermission.objects.get(id=perm_id)
        perm.delete()
        
        return JsonResponse({'status': 'success'})
    except TaskPermission.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Permission not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)


@superuser_required
def roles_view(request):
    """View for managing Roles"""
    from core.RBACModel import Role
    
    roles = Role.objects.all().select_related('task_permission').order_by('name')
    task_permissions = TaskPermission.objects.all().order_by('name')
    
    context = {
        'roles': roles,
        'task_permissions': task_permissions,
        'active_page': 'roles'
    }
    return render(request, 'PermissionManager/roles.html', context)


@superuser_required
def users_view(request):
    """View for managing Users"""
    from django.contrib.auth.models import User
    from core.RBACModel import Role, UserTaskPermission
    
    users = User.objects.all().prefetch_related('roles', 'task_permission').order_by('username')
    roles = Role.objects.all().order_by('name')
    task_permissions = TaskPermission.objects.all().order_by('name')
    
    # Get user roles and task permissions
    users_data = []
    for user in users:
        user_roles = list(user.roles.all())
        try:
            user_task_perm = user.task_permission
            user_task_perm_id = user_task_perm.task_permission.id if user_task_perm.task_permission else None
        except UserTaskPermission.DoesNotExist:
            user_task_perm_id = None
        
        users_data.append({
            'user': user,
            'roles': user_roles,
            'task_permission_id': user_task_perm_id
        })
    
    context = {
        'users_data': users_data,
        'all_roles': roles,
        'task_permissions': task_permissions,
        'active_page': 'users'
    }
    return render(request, 'PermissionManager/users.html', context)


@superuser_required
@require_http_methods(["POST"])
def add_role(request):
    """API endpoint to add a new role"""
    from core.RBACModel import Role
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        task_permission_id = data.get('task_permission_id')
        
        # Validate name
        if not name:
            return JsonResponse({'status': 'error', 'message': 'Name is required'}, status=400)
        
        if len(name) > 50:
            return JsonResponse({'status': 'error', 'message': 'Name too long (max 50 characters)'}, status=400)
        
        # Check for dangerous characters
        if any(char in name for char in ['<', '>', '"', "'"]):
            return JsonResponse({'status': 'error', 'message': 'Invalid characters in name'}, status=400)
        
        if Role.objects.filter(name=name).exists():
            return JsonResponse({'status': 'error', 'message': 'Name already exists'}, status=400)
        
        # Validate task permission
        task_permission = None
        if task_permission_id:
            try:
                task_permission = TaskPermission.objects.get(id=int(task_permission_id))
            except (TaskPermission.DoesNotExist, ValueError):
                return JsonResponse({'status': 'error', 'message': 'Invalid task permission'}, status=400)
        
        role = Role.objects.create(
            name=name,
            task_permission=task_permission,
            description=description if description else None
        )
        
        return JsonResponse({
            'status': 'success',
            'id': role.id,
            'name': role.name,
            'description': role.description or ''
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def update_role(request):
    """API endpoint to update role task permission or description"""
    from core.RBACModel import Role
    
    try:
        data = json.loads(request.body)
        role_id = data.get('id')
        task_permission_id = data.get('task_permission_id')
        description = data.get('description', '').strip()
        
        # Validate ID
        if not role_id or not isinstance(role_id, int):
            return JsonResponse({'status': 'error', 'message': 'Valid ID is required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Role not found'}, status=404)
        
        # Update task permission if provided
        if task_permission_id is not None:
            if task_permission_id == '':
                role.task_permission = None
            else:
                try:
                    task_permission = TaskPermission.objects.get(id=int(task_permission_id))
                    role.task_permission = task_permission
                except (TaskPermission.DoesNotExist, ValueError):
                    return JsonResponse({'status': 'error', 'message': 'Invalid task permission'}, status=400)
        
        # Update description if provided
        if 'description' in data:
            role.description = description if description else None
        
        role.save()
        
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def delete_role(request):
    """API endpoint to delete a role"""
    from core.RBACModel import Role
    
    try:
        data = json.loads(request.body)
        role_id = data.get('id')
        
        # Validate ID
        if not role_id or not isinstance(role_id, int):
            return JsonResponse({'status': 'error', 'message': 'Valid ID is required'}, status=400)
        
        role = Role.objects.get(id=role_id)
        role.delete()
        
        return JsonResponse({'status': 'success'})
    except Role.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Role not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def save_user_assignments(request):
    """API endpoint to save user role and task permission assignments"""
    from django.contrib.auth.models import User
    from core.RBACModel import Role, UserTaskPermission
    
    try:
        data = json.loads(request.body)
        users_data = data.get('users', [])
        
        if not isinstance(users_data, list):
            return JsonResponse({'status': 'error', 'message': 'Invalid data format'}, status=400)
        
        for user_data in users_data:
            user_id = user_data.get('user_id')
            role_ids = user_data.get('role_ids', [])
            task_permission_id = user_data.get('task_permission_id')
            
            # Validate user_id
            if not user_id or not isinstance(user_id, int):
                return JsonResponse({'status': 'error', 'message': 'Valid user ID is required'}, status=400)
            
            # Validate role_ids
            if not isinstance(role_ids, list) or not all(isinstance(rid, int) for rid in role_ids):
                return JsonResponse({'status': 'error', 'message': 'Valid role IDs are required'}, status=400)
            
            # Validate task_permission_id
            if task_permission_id is not None and not isinstance(task_permission_id, int):
                return JsonResponse({'status': 'error', 'message': 'Valid task permission ID is required'}, status=400)
            
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
                # Remove special permission if None selected
                UserTaskPermission.objects.filter(user=user).delete()
        
        return JsonResponse({'status': 'success'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'User not found'}, status=404)
    except Role.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Role not found'}, status=404)
    except TaskPermission.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task permission not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=400)
