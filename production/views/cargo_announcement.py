from django.shortcuts import render
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum
import logging
from core.logging_levels import *

from production.forms.cargo_announcement_form import CargoAnnouncementForm
from core.ProductFolder.ProductModel import Product
from core.ProductFolder.ProductionInfoModel import ProductionInfo
from core.AllocationFolder.AllocationModel import Allocation
from core.AllocationFolder.AllocationProductInfoModel import AllocationProductInfo
from core.ProductionFolder.ProductionProgramModel import ProductionProgram

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


@require_http_methods(["GET", "POST"])
def cargo_announcement_view(request):
    """اعلام بار: انتخاب اقلام و شیوه اعلام بار و ثبت درخواست.

    فعلاً بدون ذخیره‌سازی مدل پایدار؛ فقط لاگ و پیام موفقیت. در آینده می‌توان به مدل core متصل کرد.
    """
    audit_logger.info("دسترسی به صفحه اعلام بار")
    context = {}

    # Datasources for tables (placeholders/aggregations)
    try:
        products = Product.objects.all().values("id", "name", "code")
        # Inventory placeholder (نیاز به اتصال به انبار در آینده)
        inventory_rows = [
            {"product_code": p["code"], "product_name": p["name"], "inventory": 0, "unit": "تن"}
            for p in products
        ]

        # Production info table (to show focus on requested products/formulas)
        prod_infos = ProductionInfo.objects.select_related("product").values("id", "formula_id", "product__name")
        info_rows = [
            {"formula_id": pi["formula_id"], "product": pi["product__name"] or "-"}
            for pi in prod_infos
        ]

        # Allocations list table: summarize allocations with first product info + total quantity
        allocations = Allocation.objects.select_related("order").prefetch_related("product_infos").all()[:200]
        allocation_rows = []
        for a in allocations:
            try:
                product_infos = list(a.product_infos.select_related("product").all())
                if product_infos:
                    first_pi = product_infos[0]
                    first_product_name = getattr(first_pi.product, "name", "-")
                    total_qty = sum([pi.quantity or 0 for pi in product_infos])
                    unit = first_pi.unit or "-"
                else:
                    first_product_name = "-"
                    total_qty = 0
                    unit = "-"
                allocation_rows.append({
                    "number": a.allocation_number,
                    "status": a.get_allocation_status_display() if a.allocation_status else "نامشخص",
                    "priority": a.allocation_priority if a.allocation_priority is not None else "-",
                    "product": first_product_name,
                    "total_qty": total_qty,
                    "unit": unit,
                })
            except Exception as inner_e:
                bug_logger.warning(f"Allocation row build failed for {getattr(a,'allocation_number','?')}: {inner_e}")
        bug_logger.debug(f"Built {len(allocation_rows)} allocation rows for cargo announcement page")

        # Production programs (only confirmed or in-progress)
        programs_qs = ProductionProgram.objects.select_related("product", "production_info").filter(
            status__in=["confirmed", "in_progress"]
        )[:300]
        program_rows = []
        found_statuses = []
        for p in programs_qs:
            try:
                found_statuses.append(p.status)
                product_name = p.product.name if p.product else (p.production_info.product.name if p.production_info and p.production_info.product else "-")
                formula = p.production_info.formula_id if p.production_info else p.program_id or "-"
                program_rows.append({
                    "id": p.id,
                    "product": product_name or "-",
                    "formula": formula or "-",
                    "planned": p.planned_weight_ton or 0,
                    "exec_date": p.execution_date,
                    "status": p.get_status_display(),
                })
            except Exception as inner_e:
                bug_logger.warning(f"Program row build failed for id={getattr(p,'id','?')}: {inner_e}")
        bug_logger.debug(f"Built {len(program_rows)} program rows for cargo announcement page; statuses={found_statuses}")
    except Exception as e:
        bug_logger.warning(f"Cargo announcement datasource error: {e}")
        inventory_rows, info_rows, allocation_rows, program_rows = [], [], [], []

    if request.method == "POST":
        form = CargoAnnouncementForm(request.POST)
        if form.is_valid():
            method = form.cleaned_data["method"]
            items_json = form.cleaned_data.get("items_json")
            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity")
            note = form.cleaned_data.get("note")

            audit_logger.info("ثبت درخواست اعلام بار")
            bug_logger.debug(f"method={method}, items_json={items_json}, quick_item={(getattr(product,'id',None), quantity)}, note={note}")

            messages.success(request, "درخواست اعلام بار ثبت شد.")
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"ok": True})
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    else:
        form = CargoAnnouncementForm()

    context.update({
        "form": form,
        "inventory_rows": inventory_rows,
        "info_rows": info_rows,
        "program_rows": program_rows,
        "allocation_rows": allocation_rows,
    })
    return render(request, "cargo_announcement.html", context)
