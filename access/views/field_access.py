from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from access.models import FieldAccessRule

import io

try:
    # openpyxl is used for reading/writing .xlsx files
    import openpyxl
except Exception:  # pragma: no cover
    openpyxl = None

from django.apps import apps
from core.RBACModel import user_has_task, TaskChoices

@login_required
def field_access_bulk_upload_view(request):
    """
    صفحه آپلود فایل اکسل برای ایجاد/به‌روزرسانی دسته‌ای قوانین FieldAccessRule
    """
    # Access control via RBAC task or staff/superuser
    if not (request.user.is_staff or request.user.is_superuser or user_has_task(request.user, TaskChoices.ACCESS_FIELD_ACCESS_BULK_UPLOAD)):
        messages.error(request, _('دسترسی لازم برای این بخش را ندارید'))
        return redirect('home')

    # Build models and fields guide
    models_info = []
    for model in apps.get_models():
        try:
            model_meta = model._meta
            app_label = model_meta.app_label
            model_name = model_meta.object_name
            # Filter to concrete field names (exclude reverse/auto)
            field_names = []
            for f in model_meta.get_fields():
                if getattr(f, 'auto_created', False) and not getattr(f, 'concrete', False):
                    continue
                if getattr(f, 'many_to_many', False) and getattr(f, 'auto_created', False):
                    continue
                # Prefer actual field attribute name
                name = getattr(f, 'name', None) or getattr(f, 'attname', None)
                if name and name not in field_names:
                    field_names.append(name)
            field_names.sort()
            models_info.append({
                'app_label': app_label,
                'model_name': model_name,
                'fields': field_names
            })
        except Exception:
            continue
    # Sort by app then model
    models_info.sort(key=lambda x: (x['app_label'], x['model_name']))

    context = {
        'template_url': reverse('access:field_access_template'),
        'post_url': reverse('access:field_access_bulk_upload'),
        'requires_openpyxl': openpyxl is None,
        'excel_columns': [
            ('username', 'نام کاربری دقیق در سیستم (الزامی)'),
            ('app_label', 'نام اپ مدل (مثال: core، sales، access) (الزامی)'),
            ('model', 'نام کلاس مدل به صورت CamelCase (مثال: PersonModel) (الزامی)'),
            ('field_name', 'نام دقیق فیلد در مدل (مثال: email, price) (الزامی)'),
            ('access_type', 'نوع دسترسی: view | edit | delete (الزامی)'),
            ('allowed', 'True/False یا 1/0 (پیش‌فرض: True)'),
        ],
        'models_info': models_info,
    }

    if request.method == 'GET':
        return render(request, 'access/field_access_bulk_upload.html', context)

    # POST: handle upload
    upload_file = request.FILES.get('file')
    if not upload_file:
        messages.error(request, _('لطفاً فایل اکسل را انتخاب کنید'))
        return redirect('access:field_access_bulk_upload')

    if openpyxl is None:
        messages.error(request, _('ماژول openpyxl نصب نیست. لطفاً مدیر سیستم پکیج openpyxl را نصب کند.'))
        return redirect('access:field_access_bulk_upload')

    if not (upload_file.name.endswith('.xlsx') or upload_file.name.endswith('.xlsm')):
        messages.error(request, _('تنها فایل‌های Excel با پسوند .xlsx یا .xlsm پذیرفته می‌شوند'))
        return redirect('access:field_access_bulk_upload')

    try:
        wb = openpyxl.load_workbook(upload_file, data_only=True)
        ws = wb.active
    except Exception as e:
        messages.error(request, _('خواندن فایل اکسل ناموفق بود: ') + str(e))
        return redirect('access:field_access_bulk_upload')

    # Expect a header row
    headers = [str(c.value).strip() if c.value is not None else '' for c in next(ws.iter_rows(min_row=1, max_row=1))[0:]]
    required = ['username', 'app_label', 'model', 'field_name', 'access_type']
    missing = [h for h in required if h not in headers]
    if missing:
        messages.error(request, _('ستون‌های الزامی یافت نشد: ') + ', '.join(missing))
        return redirect('access:field_access_bulk_upload')

    # Column index map
    idx = {h: headers.index(h) for h in headers}

    created_count = 0
    updated_count = 0
    errors = []

    # Iterate rows
    for r in ws.iter_rows(min_row=2, values_only=True):
        if all(v in (None, '') for v in r or []):
            continue
        try:
            username = str(r[idx['username']]).strip() if r[idx['username']] is not None else ''
            app_label = str(r[idx['app_label']]).strip() if r[idx['app_label']] is not None else ''
            model_name = str(r[idx['model']]).strip() if r[idx['model']] is not None else ''
            field_name = str(r[idx['field_name']]).strip() if r[idx['field_name']] is not None else ''
            access_type = str(r[idx['access_type']]).strip().lower() if r[idx['access_type']] is not None else ''
            allowed = True
            if 'allowed' in idx and r[idx['allowed']] is not None:
                val = str(r[idx['allowed']]).strip().lower()
                allowed = val in ('true', '1', 'yes', 'y')

            if not username or not app_label or not model_name or not field_name or access_type not in ('view', 'edit', 'delete'):
                raise ValueError('داده‌های سطر ناقص یا نامعتبر است')

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(username=username).first()
            if not user:
                raise ValueError(f'کاربر "{username}" یافت نشد')

            # Resolve ContentType by app_label + model class name
            ct = ContentType.objects.filter(app_label=app_label.lower(), model=model_name.lower()).first()
            if not ct:
                # Some projects register model as lower-cased class name without "Model" suffix
                ct = ContentType.objects.filter(app_label=app_label.lower(), model=model_name.replace('Model', '').lower()).first()
            if not ct:
                raise ValueError(f'ContentType برای {app_label}.{model_name} یافت نشد')

            # Upsert rule
            obj, created = FieldAccessRule.objects.update_or_create(
                user=user,
                content_type=ct,
                field_name=field_name,
                access_type=access_type,
                defaults={'allowed': allowed},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        except Exception as e:
            errors.append(str(e))

    if created_count or updated_count:
        messages.success(
            request,
            _('پردازش شد: ') + f'{created_count} ایجاد، {updated_count} به‌روزرسانی'
        )
    if errors:
        messages.warning(request, _('برخی سطرها با خطا مواجه شدند:') + ' ' + ' | '.join(errors[:10]) + (' ...' if len(errors) > 10 else ''))

    return redirect('access:field_access_bulk_upload')


@login_required
def download_field_access_template(request):
    """
    تولید و دانلود فایل نمونه اکسل برای بارگذاری دسته‌ای
    """
    if not (request.user.is_staff or request.user.is_superuser or user_has_task(request.user, TaskChoices.ACCESS_FIELD_ACCESS_BULK_UPLOAD)):
        return HttpResponseBadRequest(_('دسترسی ندارید.'))
    if openpyxl is None:
        return HttpResponseBadRequest(_('ماژول openpyxl نصب نیست.'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'FieldAccessRules'
    headers = ['username', 'app_label', 'model', 'field_name', 'access_type', 'allowed']
    ws.append(headers)
    # Example rows
    ws.append(['admin', 'core', 'PersonModel', 'email', 'view', 'True'])
    ws.append(['admin', 'sales', 'OrderModel', 'total_price', 'edit', 'False'])

    # Auto width
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for c in col:
            try:
                max_len = max(max_len, len(str(c.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = max(12, max_len + 2)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="field_access_template.xlsx"'
    return response


