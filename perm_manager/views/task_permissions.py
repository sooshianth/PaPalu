from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.RBACModel import TaskPermission, TaskChoices
from .decorators import superuser_required
import json


@superuser_required
def task_permissions_view(request):
    """View for managing TaskPermissions"""
    task_permissions = TaskPermission.objects.all().order_by('name')
    
    # Group tasks by category for display
    grouped_tasks = {}
    for code, label in TaskChoices.choices:
        category = code.split('.')[0] if '.' in code else 'general'
        if category not in grouped_tasks:
            grouped_tasks[category] = []
        grouped_tasks[category].append((code, label))
    
    # Sort categories using the order defined in TaskChoices
    # First add categories in the defined order with display names
    grouped_choices = []
    ordered_category_ids = set()
    
    for cat_id, cat_display in TaskChoices.CATEGORY_ORDER:
        if cat_id in grouped_tasks:
            grouped_choices.append((cat_display, grouped_tasks[cat_id]))
            ordered_category_ids.add(cat_id)
    
    # Then add any remaining categories not in the order (at the end)
    remaining_categories = sorted([cat for cat in grouped_tasks.keys() if cat not in ordered_category_ids])
    grouped_choices.extend([(cat.capitalize(), grouped_tasks[cat]) for cat in remaining_categories])
    
    context = {
        'task_permissions': task_permissions,
        'grouped_choices': grouped_choices,
        'active_page': 'taskpermissions'
    }
    return render(request, 'perm_manager/task_permissions.html', context)


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

