from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from core.RBACModel import FieldPermission, FieldChoice
from .decorators import superuser_required
import json


@superuser_required
def field_permissions_view(request):
    """View for managing FieldPermissions"""
    field_permissions = FieldPermission.objects.prefetch_related('field_choices').order_by('name')
    
    # Get all models and their fields
    content_types = ContentType.objects.all().order_by('app_label', 'model')
    
    # Build a list of (model, fields) for display
    model_fields = []
    for ct in content_types:
        model_class = ct.model_class()
        if model_class:
            fields = []
            for f in model_class._meta.get_fields():
                # Skip auto-created fields and many-to-many
                if not f.auto_created and not f.many_to_many:
                    field_label = f.verbose_name if hasattr(f, 'verbose_name') and f.verbose_name else f.name
                    fields.append({
                        'name': f.name,
                        'label': field_label,
                        'content_type_id': ct.id
                    })
            
            if fields:
                model_fields.append({
                    'app_label': ct.app_label,
                    'model_name': ct.model,
                    'display_name': f"{ct.app_label}.{ct.model}",
                    'content_type_id': ct.id,
                    'fields': sorted(fields, key=lambda x: x['label'])
                })
    
    # Build a map of existing field choices for each permission
    # Structure: {perm_id: {f"{ct_id}_{field_name}_{access_type}": allowed}}
    perm_field_map = {}
    for perm in field_permissions:
        perm_field_map[str(perm.id)] = {}
        for choice in perm.field_choices.all():
            key = f"{choice.content_type_id}_{choice.field_name}_{choice.access_type}"
            perm_field_map[str(perm.id)][key] = choice.allowed
    
    context = {
        'field_permissions': field_permissions,
        'model_fields': model_fields,
        'perm_field_map': json.dumps(perm_field_map),
        'access_types': ['view', 'edit'],
        'active_page': 'fieldpermissions'
    }
    return render(request, 'perm_manager/field_permissions.html', context)


@superuser_required
@require_http_methods(["POST"])
def save_field_permissions(request):
    """API endpoint to save field permission changes"""
    try:
        data = json.loads(request.body)
        
        for perm_data in data:
            perm_id = perm_data.get('id')
            choices = perm_data.get('choices', [])
            
            # Validate permission ID
            if not perm_id or not isinstance(perm_id, int):
                continue
            
            # Validate choices
            if not isinstance(choices, list):
                continue
            
            try:
                perm = FieldPermission.objects.get(id=perm_id)
                
                # Delete existing choices
                perm.field_choices.all().delete()
                
                # Create new choices
                with transaction.atomic():
                    for choice_data in choices:
                        content_type_id = choice_data.get('content_type_id')
                        field_name = choice_data.get('field_name')
                        access_type = choice_data.get('access_type')
                        allowed = choice_data.get('allowed', True)
                        
                        if not all([content_type_id, field_name, access_type]):
                            continue
                        
                        # Validate content type
                        try:
                            ct = ContentType.objects.get(id=int(content_type_id))
                        except ContentType.DoesNotExist:
                            continue
                        
                        # Validate access type
                        if access_type not in ['view', 'edit']:
                            continue
                        
                        # Create the choice
                        FieldChoice.objects.create(
                            field_permission=perm,
                            content_type=ct,
                            field_name=field_name,
                            access_type=access_type,
                            allowed=allowed
                        )
            except FieldPermission.DoesNotExist:
                continue
        
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@superuser_required
@require_http_methods(["POST"])
def add_field_permission(request):
    """API endpoint to add a new field permission"""
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        
        # Validate name
        if not name:
            return JsonResponse({'status': 'error', 'message': 'نام الزامی است'}, status=400)
        
        if len(name) > 100:
            return JsonResponse({'status': 'error', 'message': 'نام خیلی طولانی است (حداکثر ۱۰۰ کاراکتر)'}, status=400)
        
        # Check for dangerous characters
        if any(char in name for char in ['<', '>', '"', "'"]):
            return JsonResponse({'status': 'error', 'message': 'نام حاوی کاراکترهای نامعتبر است'}, status=400)
        
        if FieldPermission.objects.filter(name=name).exists():
            return JsonResponse({'status': 'error', 'message': 'این نام قبلاً استفاده شده است'}, status=400)
        
        perm = FieldPermission.objects.create(name=name)
        
        return JsonResponse({
            'status': 'success',
            'id': perm.id,
            'name': perm.name
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON نامعتبر'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'خطای سرور'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def delete_field_permission(request):
    """API endpoint to delete a field permission"""
    try:
        data = json.loads(request.body)
        perm_id = data.get('id')
        
        # Validate ID
        if not perm_id or not isinstance(perm_id, int):
            return JsonResponse({'status': 'error', 'message': 'شناسه معتبر الزامی است'}, status=400)
        
        perm = FieldPermission.objects.get(id=perm_id)
        perm.delete()
        
        return JsonResponse({'status': 'success'})
    except FieldPermission.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'مجوز یافت نشد'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON نامعتبر'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'خطای سرور'}, status=400)
