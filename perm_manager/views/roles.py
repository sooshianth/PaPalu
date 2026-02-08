from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.RBACModel import TaskPermission
from .decorators import superuser_required
import json


@superuser_required
def roles_view(request):
    """View for managing Roles"""
    from core.RBACModel import Role, FieldPermission
    
    roles = Role.objects.all().prefetch_related('task_permissions', 'field_permission').order_by('name')
    task_permissions = TaskPermission.objects.all().order_by('name')
    field_permissions = FieldPermission.objects.all().order_by('name')
    
    context = {
        'roles': roles,
        'task_permissions': task_permissions,
        'field_permissions': field_permissions,
        'active_page': 'roles'
    }
    return render(request, 'perm_manager/roles.html', context)


@superuser_required
@require_http_methods(["POST"])
def add_role(request):
    """API endpoint to add a new role"""
    from core.RBACModel import Role, FieldPermission
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        task_permission_ids = data.get('task_permission_ids', [])  # حالا آرایه‌ای از IDها می‌گیریم
        field_permission_id = data.get('field_permission_id')
        
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
        
        # Validate field permission
        field_permission = None
        if field_permission_id:
            try:
                field_permission = FieldPermission.objects.get(id=int(field_permission_id))
            except (FieldPermission.DoesNotExist, ValueError):
                return JsonResponse({'status': 'error', 'message': 'Invalid field permission'}, status=400)
        
        role = Role.objects.create(
            name=name,
            field_permission=field_permission,
            description=description if description else None
        )
        
        # اضافه کردن TaskPermission ها به Role
        if task_permission_ids and isinstance(task_permission_ids, list):
            for tp_id in task_permission_ids:
                try:
                    task_perm = TaskPermission.objects.get(id=int(tp_id))
                    task_perm.role = role
                    task_perm.save()
                except (TaskPermission.DoesNotExist, ValueError):
                    pass  # در صورت نامعتبر بودن، نادیده می‌گیریم
        
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
    """API endpoint to update role permissions or description"""
    from core.RBACModel import Role, FieldPermission
    
    try:
        data = json.loads(request.body)
        role_id = data.get('id')
        task_permission_ids = data.get('task_permission_ids')  # حالا آرایه‌ای از IDها می‌گیریم
        field_permission_id = data.get('field_permission_id')
        description = data.get('description', '').strip()
        
        # Validate ID
        if not role_id or not isinstance(role_id, int):
            return JsonResponse({'status': 'error', 'message': 'Valid ID is required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Role not found'}, status=404)
        
        # Update task permissions if provided
        if task_permission_ids is not None:
            # ابتدا تمام TaskPermission های قبلی این Role را پاک می‌کنیم
            TaskPermission.objects.filter(role=role).update(role=None)
            
            # حالا TaskPermission های جدید را اضافه می‌کنیم
            if isinstance(task_permission_ids, list):
                for tp_id in task_permission_ids:
                    if tp_id:  # اگر خالی نباشد
                        try:
                            task_perm = TaskPermission.objects.get(id=int(tp_id))
                            task_perm.role = role
                            task_perm.save()
                        except (TaskPermission.DoesNotExist, ValueError):
                            pass  # در صورت نامعتبر بودن، نادیده می‌گیریم
        
        # Update field permission if provided
        if field_permission_id is not None:
            if field_permission_id == '':
                role.field_permission = None
            else:
                try:
                    field_permission = FieldPermission.objects.get(id=int(field_permission_id))
                    role.field_permission = field_permission
                except (FieldPermission.DoesNotExist, ValueError):
                    return JsonResponse({'status': 'error', 'message': 'Invalid field permission'}, status=400)
        
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

