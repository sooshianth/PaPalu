from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db.models import Sum, Q
from django.db import OperationalError
from django.http import JsonResponse
import logging
from core.logging_levels import *
from production.forms.program_form import ProductionProgramForm
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.ProductFolder.BOMModel import BOM
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.RawMaterialFolder.RawMaterialModel import RawMaterial

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def _get_dashboard_context():
    """Helper: gathers dashboard data for inventory, flow status, and allocations."""
    audit_logger.debug("جمع‌آوری داده‌های داشبورد برنامه تولید")
    try:
        # Get raw materials from BOM with their related RawMaterial data
        raw_materials_in_bom = BOM.objects.select_related('raw_material').values_list('raw_material_id', flat=True).distinct()
        raw_material_inventory = []
        for rm_id in raw_materials_in_bom:
            if rm_id:
                try:
                    raw_material = RawMaterial.objects.get(id=rm_id)
                    raw_material_inventory.append({
                        'raw_material_id': raw_material.raw_material_id or '-',
                        'raw_material': raw_material.name or '-',
                        'unit_used': raw_material.primary_unit or '-',
                        'current_inventory': 0
                    })
                except RawMaterial.DoesNotExist:
                    pass

        product_flow_status = []
        production_infos = ProductionInfo.objects.select_related('product').all()
        db_issue = False
        for prod_info in production_infos:
            try:
                planned_inventory = ProductionProgram.objects.filter(
                    production_info=prod_info,
                    status=ProductionProgram.Status.CONFIRMED
                ).aggregate(total=Sum('planned_weight_ton'))['total'] or 0
            except OperationalError:
                planned_inventory = 0
                db_issue = True
                bug_logger.warning("خطای عملیاتی هنگام محاسبه موجودی برنامه‌ریزی شده")

            inventory = 0
            logistic_confirmed = 0
            net_unplanned = logistic_confirmed - (inventory + planned_inventory)

            product_flow_status.append({
                'product': prod_info.product.name if prod_info.product else '-',
                'program_id': prod_info.formula_id or '-',
                'inventory': inventory,
                'planned_inventory': planned_inventory,
                'net_unplanned_requirement': net_unplanned,
                'status': 'نیازمند برنامه‌ریزی' if net_unplanned > 0 else 'کافی'
            })

        product_flow_status.sort(key=lambda x: x['net_unplanned_requirement'], reverse=True)
        allocations = []
        return {
            'raw_material_inventory': raw_material_inventory,
            'product_flow_status': product_flow_status,
            'allocations': allocations,
            'db_integrity_issue': db_issue,
        }
    except Exception as e:
        bug_logger.error(f"Dashboard context error: {e}")
        return {'raw_material_inventory': [], 'product_flow_status': [], 'allocations': [], 'db_integrity_issue': False}


def create_program_view(request):
    """ایجاد / پیش نویس / تایید برنامه تولید"""
    audit_logger.info("دسترسی به ایجاد برنامه تولید")
    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            bug_logger.debug(f"POST action={action}")
            bug_logger.debug(f"Date fields received - start_date: {request.POST.get('predicted_start_date')}, start_time: {request.POST.get('predicted_start_time')}, end_date: {request.POST.get('predicted_end_date')}, end_time: {request.POST.get('predicted_end_time')}")
            # Create mutable copy and set status based on action BEFORE validation
            post_data = request.POST.copy()
            if action == 'confirm':
                post_data['status'] = ProductionProgram.Status.CONFIRMED
            elif action == 'start':
                post_data['status'] = ProductionProgram.Status.IN_PROGRESS
            elif action == 'complete':
                post_data['status'] = ProductionProgram.Status.COMPLETED
            else:
                post_data['status'] = ProductionProgram.Status.DRAFT
            
            form = ProductionProgramForm(post_data)
            if form.is_valid():
                instance = form.save(commit=False)
                # Status already set from form data
                instance.save()
                bug_logger.info(f"برنامه با موفقیت ذخیره شد. ID={instance.id}, Status={instance.status}")
                messages.success(request, 'برنامه ذخیره شد.')
                # AJAX-friendly JSON
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                    return JsonResponse({
                        'ok': True,
                        'id': instance.id,
                        'status': instance.status,
                        'detail_url': reverse('production:program_edit', args=[instance.id])
                    })
                return redirect(reverse('production:program_edit', args=[instance.id]))
            else:
                bug_logger.warning(f"فرم نامعتبر است. Errors: {form.errors.as_json()}")
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept',''):
                    return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        else:
            form = ProductionProgramForm()

        context = {'form': form, 'mode': 'create'}
        context.update(_get_dashboard_context())
        return render(request, 'program_form.html', context)
    except Exception as e:
        bug_logger.error(f"Create program error: {e}")
        messages.error(request, 'خطا در ثبت برنامه.')
        context = {'form': ProductionProgramForm(), 'mode': 'create'}
        context.update(_get_dashboard_context())
        return render(request, 'program_form.html', context)


def edit_program_view(request, program_id):
    audit_logger.info("دسترسی به ویرایش برنامه تولید")
    program = get_object_or_404(ProductionProgram, id=program_id)
    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            form = ProductionProgramForm(request.POST, instance=program)
            if form.is_valid():
                instance = form.save(commit=False)
                if action == 'confirm' and instance.status == ProductionProgram.Status.DRAFT:
                    instance.status = ProductionProgram.Status.CONFIRMED
                elif action == 'start' and instance.status == ProductionProgram.Status.CONFIRMED:
                    instance.status = ProductionProgram.Status.IN_PROGRESS
                elif action == 'complete' and instance.status == ProductionProgram.Status.IN_PROGRESS:
                    instance.status = ProductionProgram.Status.COMPLETED
                instance.save()
                messages.success(request, 'برنامه به‌روز شد.')
                return redirect(reverse('production:program_edit', args=[instance.id]))
        else:
            form = ProductionProgramForm(instance=program)

        context = {'form': form, 'program': program, 'mode': 'edit'}
        context.update(_get_dashboard_context())
        return render(request, 'program_form.html', context)
    except Exception as e:
        bug_logger.error(f"Edit program error: {e}")
        messages.error(request, 'خطا در بروزرسانی برنامه.')
        context = {'form': ProductionProgramForm(instance=program), 'program': program, 'mode': 'edit'}
        context.update(_get_dashboard_context())
        return render(request, 'program_form.html', context)


def program_list_view(request):
    audit_logger.info("نمایش لیست برنامه‌های تولید")
    try:
        programs = ProductionProgram.objects.all().select_related('product', 'production_info')
        bug_logger.debug(f"Programs list count={programs.count()}")
        return render(request, 'program_list.html', {'programs': programs})
    except Exception as e:
        bug_logger.error(f"List programs error: {e}")
        return render(request, 'program_list.html', {'programs': []})


def program_drafts_view(request):
    """Redirect to main program list - drafts are shown there with status"""
    audit_logger.info("ریدایرکت از صفحه پیش‌نویس به لیست اصلی")
    return redirect(reverse('production:program_list'))
