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
    
    roles = Role.objects.all().prefetch_related('task_permissions', 'field_permissions').order_by('name')
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
        task_permission_ids = data.get('task_permission_ids', [])
        field_permission_ids = data.get('field_permission_ids', [])
        
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
        
        role = Role.objects.create(
            name=name,
            description=description if description else None
        )
        
        # اضافه کردن TaskPermission ها به Role (چند-به-چند؛ یک مجوز می‌تواند به چند نقش داده شود)
        if task_permission_ids and isinstance(task_permission_ids, list):
            pks = []
            for tp_id in task_permission_ids:
                try:
                    pks.append(int(tp_id))
                except (ValueError, TypeError):
                    pass
            if pks:
                role.task_permissions.set(TaskPermission.objects.filter(id__in=pks))
        
        # اضافه کردن FieldPermission ها به Role (چند-به-چند؛ مشابه TaskPermission)
        if field_permission_ids and isinstance(field_permission_ids, list):
            fp_pks = []
            for fp_id in field_permission_ids:
                try:
                    fp_pks.append(int(fp_id))
                except (ValueError, TypeError):
                    pass
            if fp_pks:
                role.field_permissions.set(FieldPermission.objects.filter(id__in=fp_pks))
        
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
        task_permission_ids = data.get('task_permission_ids')
        field_permission_ids = data.get('field_permission_ids')
        description = data.get('description', '').strip()
        
        # Validate ID
        if not role_id or not isinstance(role_id, int):
            return JsonResponse({'status': 'error', 'message': 'Valid ID is required'}, status=400)
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Role not found'}, status=404)
        
        # به‌روزرسانی مجوزهای وظیفه (چند-به-چند؛ یک مجوز می‌تواند به چند نقش داده شود)
        if task_permission_ids is not None and isinstance(task_permission_ids, list):
            pks = []
            for tp_id in task_permission_ids:
                if tp_id is None or tp_id == '':
                    continue
                try:
                    pks.append(int(tp_id))
                except (ValueError, TypeError):
                    pass
            role.task_permissions.set(TaskPermission.objects.filter(id__in=pks))
        
        # به‌روزرسانی مجوزهای فیلد (چند-به-چند؛ مشابه TaskPermission)
        if field_permission_ids is not None:
            if isinstance(field_permission_ids, list):
                fp_pks = []
                for fp_id in field_permission_ids:
                    if fp_id is not None and fp_id != '':
                        try:
                            fp_pks.append(int(fp_id))
                        except (ValueError, TypeError):
                            pass
                role.field_permissions.set(FieldPermission.objects.filter(id__in=fp_pks))
        
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

