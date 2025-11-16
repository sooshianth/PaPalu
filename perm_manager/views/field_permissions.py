from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from core.RBACModel import FieldPermission, FieldChoice, ManagedField
from .decorators import superuser_required
import json


@superuser_required
def field_permissions_view(request):
    """View for managing FieldPermissions"""
    field_permissions = FieldPermission.objects.prefetch_related('field_choices').order_by('name')
    
    # لیست کامل مدل‌ها و فیلدهایشان برای UI «افزودن فیلد» (در بالا به صورت انتخابی، نه در جدول اصلی)
    content_types = ContentType.objects.all().order_by('app_label', 'model')
    
    all_model_fields = []
    for ct in content_types:
        model_class = ct.model_class()
        if model_class:
            fields = []
            for f in model_class._meta.get_fields():
                # Skip auto-created fields and many-to-many
                if not f.auto_created and not f.many_to_many:
                    field_label = f.verbose_name if hasattr(f, 'verbose_name') and f.verbose_name else f.name
                    # تبدیل به string برای JSON serialization
                    field_label = str(field_label)
                    fields.append({
                        'name': f.name,
                        'label': field_label,
                        'content_type_id': ct.id
                    })
            
            if fields:
                all_model_fields.append({
                    'app_label': ct.app_label,
                    'model_name': ct.model,
                    'display_name': f"{ct.app_label}.{ct.model}",
                    'verbose_name': str(getattr(model_class._meta, 'verbose_name', ct.model)),
                    'content_type_id': ct.id,
                    'fields': sorted(fields, key=lambda x: x['label'])
                })
    
    # فقط فیلدهایی که به‌طور صریح در ManagedField ثبت شده‌اند در جدول اصلی نمایش داده می‌شوند
    managed_fields_qs = ManagedField.objects.select_related('content_type').all().order_by(
        'content_type__app_label', 'content_type__model', 'field_name'
    )

    # گروه‌بندی ManagedField ها به ساختار مشابه model_fields قبلی برای استفاده در تمپلیت
    model_fields = []
    current_ct_id = None
    current_entry = None
    for mf in managed_fields_qs:
        ct = mf.content_type
        if current_ct_id != ct.id:
            # ورودی جدید برای این مدل
            current_entry = {
                'app_label': ct.app_label,
                'model_name': ct.model,
                'display_name': f"{ct.app_label}.{ct.model}",
                'content_type_id': ct.id,
                'fields': []
            }
            model_fields.append(current_entry)
            current_ct_id = ct.id

        current_entry['fields'].append({
            'name': mf.field_name,
            'label': mf.field_label,
            'content_type_id': ct.id
        })
    
    # Build a map of existing field choices برای هر Permission
    # در این صفحه ما فقط «محدودیت‌ها» را نشان می‌دهیم، یعنی فیلدهایی که allowed=False هستند
    # Structure: {perm_id: {f"{ct_id}_{field_name}_{access_type}": True}}
    perm_field_map = {}
    for perm in field_permissions:
        perm_field_map[str(perm.id)] = {}
        # فقط فیلدهایی که به‌طور صریح «ممنوع» شده‌اند (allowed=False) را در نقشه می‌آوریم
        for choice in perm.field_choices.filter(allowed=False):
            key = f"{choice.content_type_id}_{choice.field_name}_{choice.access_type}"
            # در Front فقط وجود داشتن کلید یعنی «ممنوع است»، پس مقدار صرفاً True می‌گذاریم
            perm_field_map[str(perm.id)][key] = True
    
    context = {
        'field_permissions': field_permissions,
        # فیلدهایی که در جدول اصلی نمایش داده می‌شوند
        'model_fields': model_fields,
        # همه مدل‌ها و فیلدها برای UI افزودن فیلد (در تمپلیت برای ساخت select و در JS)
        'all_model_fields': all_model_fields,
        'all_model_fields_json': json.dumps(all_model_fields),
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
                
                # در این پیاده‌سازی، ما این صفحه را به عنوان «لیست ممنوعیت‌ها» در نظر می‌گیریم.
                # بنابراین ابتدا همه انتخاب‌های قبلی را پاک می‌کنیم و سپس فقط فیلدهایی را
                # دوباره می‌سازیم که در UI با ضربدر (checkbox فعال) انتخاب شده‌اند؛
                # این‌ها همه allowed=False خواهند بود.
                perm.field_choices.all().delete()
                
                # Create new choices
                with transaction.atomic():
                    for choice_data in choices:
                        content_type_id = choice_data.get('content_type_id')
                        field_name = choice_data.get('field_name')
                        access_type = choice_data.get('access_type')
                        # در این صفحه هر چیزی که ذخیره می‌کنیم به معنی «ممنوع» است
                        allowed = False
                        
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
                        
                        # Create the choice به‌عنوان یک قانون ممنوعیت
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


@superuser_required
@require_http_methods(["POST"])
def add_managed_field(request):
    """
    API برای افزودن یک فیلد به لیست فیلدهای قابل مدیریت (ManagedField)
    انتظار JSON به شکل:
    {
        "content_type_id": 1,
        "field_name": "price",
        "field_label": "قیمت"
    }
    """
    try:
        data = json.loads(request.body)
        content_type_id = data.get('content_type_id')
        field_name = (data.get('field_name') or '').strip()
        field_label = (data.get('field_label') or '').strip()

        if not content_type_id or not field_name:
            return JsonResponse({'status': 'error', 'message': 'مدل و نام فیلد الزامی است'}, status=400)

        try:
            ct = ContentType.objects.get(id=int(content_type_id))
        except (ValueError, ContentType.DoesNotExist):
            return JsonResponse({'status': 'error', 'message': 'مدل نامعتبر است'}, status=400)

        # بررسی اینکه آیا فیلد در مدل وجود دارد
        model_class = ct.model_class()
        if not model_class:
            return JsonResponse({'status': 'error', 'message': 'مدل یافت نشد'}, status=400)

        try:
            f = model_class._meta.get_field(field_name)
        except Exception:
            # لیست فیلدهای موجود برای نمایش به کاربر
            available_fields = [field.name for field in model_class._meta.get_fields() if not field.auto_created and not field.many_to_many]
            return JsonResponse({
                'status': 'error', 
                'message': f'فیلد "{field_name}" در مدل "{ct.model}" وجود ندارد. فیلدهای موجود: {", ".join(available_fields[:10])}'
            }, status=400)

        # اگر label خالی بود، از خود مدل بخوانیم
        if not field_label:
            field_label = str(getattr(f, 'verbose_name', field_name) or field_name)

        mf, created = ManagedField.objects.get_or_create(
            content_type=ct,
            field_name=field_name,
            defaults={'field_label': field_label}
        )

        if not created:
            # اگر از قبل وجود دارد، برچسب را به‌روزرسانی می‌کنیم
            if field_label and mf.field_label != field_label:
                mf.field_label = field_label
                mf.save(update_fields=['field_label'])
            return JsonResponse({
                'status': 'info',
                'message': 'این فیلد قبلاً اضافه شده بود',
                'id': mf.id,
                'content_type_id': mf.content_type_id,
                'field_name': mf.field_name,
                'field_label': mf.field_label,
            })

        return JsonResponse({
            'status': 'success',
            'message': 'فیلد با موفقیت اضافه شد',
            'id': mf.id,
            'content_type_id': mf.content_type_id,
            'field_name': mf.field_name,
            'field_label': mf.field_label,
        })
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON نامعتبر'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'خطای سرور: {str(e)}'}, status=400)


@superuser_required
@require_http_methods(["POST"])
def delete_managed_field(request):
    """
    API برای حذف یک فیلد از لیست فیلدهای قابل مدیریت (ManagedField)
    انتظار JSON به شکل:
    {
        "id": 1
    }
    """
    try:
        data = json.loads(request.body)
        mf_id = data.get('id')

        if not mf_id or not isinstance(mf_id, int):
            return JsonResponse({'status': 'error', 'message': 'شناسه معتبر الزامی است'}, status=400)

        mf = ManagedField.objects.get(id=mf_id)
        mf.delete()

        return JsonResponse({'status': 'success'})
    except ManagedField.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'فیلد یافت نشد'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON نامعتبر'}, status=400)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'خطای سرور'}, status=400)
