from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm, inlineformset_factory, BaseInlineFormSet
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from decimal import Decimal, ROUND_HALF_UP
import logging
from core.logging_levels import *
from django_tables2 import RequestConfig

from core.OrderFolder.OrderModel import Order, OrderStatusLog
from core.OrderFolder.OrderItemModel import OrderItem
from core.PersonFolder.PersonModel import Person
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from django.contrib.auth import get_user_model
from supply.forms.procurement_order_form import ProcurementPurchaseOrderForm, ProcurementPurchaseOrderMaterialForm, MaterialFormSetBase

User = get_user_model()

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_procurement_purchase_order_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل Order (سفارش خرید)"""
    return {
        'order_number': user_can_access_field(user, Order, 'order_number', 'view'),
        'customer': user_can_access_field(user, Order, 'customer', 'view'),  # supplier در Order به نام customer است
        'status': user_can_access_field(user, Order, 'status', 'view'),
        'freight_payment_type': user_can_access_field(user, Order, 'freight_payment_type', 'view'),
        'subtotal_without_freight': user_can_access_field(user, Order, 'subtotal_without_freight', 'view'),
        'freight_cost': user_can_access_field(user, Order, 'freight_cost', 'view'),
        'vat_percentage': user_can_access_field(user, Order, 'vat_percentage', 'view'),
        'payment_confirmed': user_can_access_field(user, Order, 'payment_confirmed', 'view'),
        'external_system_id': user_can_access_field(user, Order, 'external_system_id', 'view'),
        'registered_by': user_can_access_field(user, Order, 'registered_by', 'view'),
        'created_at': user_can_access_field(user, Order, 'created_at', 'view'),
        'updated_at': user_can_access_field(user, Order, 'updated_at', 'view'),
        'ordered_at': user_can_access_field(user, Order, 'ordered_at', 'view'),
    }


def get_accessible_procurement_purchase_order_material_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل OrderItem"""
    return {
        'raw_material': user_can_access_field(user, OrderItem, 'raw_material', 'view'),
        'quantity': user_can_access_field(user, OrderItem, 'quantity', 'view'),
        'weight_unit': user_can_access_field(user, OrderItem, 'weight_unit', 'view'),
        'notes': user_can_access_field(user, OrderItem, 'notes', 'view'),
        'unit_price': user_can_access_field(user, OrderItem, 'unit_price', 'view'),
        'total_purchase_cost': user_can_access_field(user, OrderItem, 'total_purchase_cost', 'view'),
        'vat_percent': user_can_access_field(user, OrderItem, 'vat_percent', 'view'),
        'freight_cost': user_can_access_field(user, OrderItem, 'freight_cost', 'view'),
        'total_purchase_cost': user_can_access_field(user, OrderItem, 'total_purchase_cost', 'view'),
        'external_allocation_id': user_can_access_field(user, OrderItem, 'external_allocation_id', 'view'),
    }


def get_accessible_raw_material_fields_for_po(user):
    """دریافت فیلدهای قابل دسترس برای مدل RawMaterial"""
    return {
        'raw_material_id': user_can_access_field(user, RawMaterial, 'raw_material_id', 'view'),
        'name': user_can_access_field(user, RawMaterial, 'name', 'view'),
        'physical_form': user_can_access_field(user, RawMaterial, 'physical_form', 'view'),
    }


def get_accessible_person_fields_for_po(user):
    """دریافت فیلدهای قابل دسترس برای مدل Person (supplier)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'national_id': user_can_access_field(user, Person, 'national_id', 'view'),
    }


def get_accessible_user_fields_for_po(user):
    """دریافت فیلدهای قابل دسترس برای مدل User (created_by)"""
    return {
        'username': user_can_access_field(user, User, 'username', 'view'),
        'first_name': user_can_access_field(user, User, 'first_name', 'view'),
        'last_name': user_can_access_field(user, User, 'last_name', 'view'),
    }


MaterialFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=ProcurementPurchaseOrderMaterialForm,
    formset=MaterialFormSetBase,
    fields=[
        'raw_material', 'quantity', 'weight_unit', 'notes',
        'unit_price', 'total_purchase_cost',
        'vat_percent', 'freight_cost',
        'external_allocation_id'
    ],
    extra=1,
    can_delete=True
)


@login_required
def purchase_order_management_view(request):
    """صفحه مدیریت سفارش‌های خرید شامل دو جدول سفارشات باز و تکمیل‌شده"""
    audit_logger.info("مشاهده مدیریت سفارش‌های خرید")
    
    # Check task permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_CREATE_ORDER.value):
        audit_logger.activity(f"تلاش برای دسترسی به مدیریت سفارش‌های خرید بدون مجوز - کاربر: {request.user.username}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_po_fields = get_accessible_procurement_purchase_order_fields(request.user)
    accessible_po_material_fields = get_accessible_procurement_purchase_order_material_fields(request.user)
    accessible_raw_material_fields = get_accessible_raw_material_fields_for_po(request.user)
    accessible_person_fields = get_accessible_person_fields_for_po(request.user)
    accessible_user_fields = get_accessible_user_fields_for_po(request.user)
    
    # دریافت پارامترهای جستجو و فیلتر
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    supplier_filter = request.GET.get('supplier', '')
    
    try:
        from supply.tables import ProcurementPurchaseOrderTable
        open_orders = Order.objects.filter(
            order_type='purchase'
        ).exclude(
            status=Order.STATUS_COMPLETED
        ).select_related('customer', 'registered_by').prefetch_related(
            'order_items__raw_material'
        )
        
        completed_orders = Order.objects.filter(
            order_type='purchase',
            status=Order.STATUS_COMPLETED
        ).select_related('customer', 'registered_by').prefetch_related(
            'order_items__raw_material'
        )
        
        # اعمال جستجو
        if search_query:
            open_orders = open_orders.filter(
                Q(order_number__icontains=search_query) |
                Q(customer__name__icontains=search_query) |
                Q(registered_by__username__icontains=search_query) |
                Q(order_items__raw_material__name__icontains=search_query)
            ).distinct()
            completed_orders = completed_orders.filter(
                Q(order_number__icontains=search_query) |
                Q(customer__name__icontains=search_query) |
                Q(registered_by__username__icontains=search_query) |
                Q(order_items__raw_material__name__icontains=search_query)
            ).distinct()
        
        # اعمال فیلتر وضعیت
        if status_filter:
            open_orders = open_orders.filter(status=status_filter)
            completed_orders = completed_orders.filter(status=status_filter)
        
        # اعمال فیلتر تامین‌کننده
        if supplier_filter:
            open_orders = open_orders.filter(customer__national_id=supplier_filter)
            completed_orders = completed_orders.filter(customer__national_id=supplier_filter)
        
        open_orders = open_orders.order_by('-created_at')
        completed_orders = completed_orders.order_by('-created_at')
        
        # Prepare table accessible fields dict
        # materials_list requires both OrderItem and raw material access
        table_accessible_fields = {
            'order_number': accessible_po_fields.get('order_number', False),
            'status': accessible_po_fields.get('status', False),
            'materials_list': (
                accessible_po_material_fields.get('raw_material', False) and
                accessible_raw_material_fields.get('name', False)
            ),
            'supplier': (
                accessible_po_fields.get('customer', False) and
                accessible_person_fields.get('name', False)
            ),
            'created_by': accessible_po_fields.get('registered_by', False),
            'ordered_at': accessible_po_fields.get('ordered_at', False),
            'total_weight': (
                accessible_po_material_fields.get('quantity', False) and
                accessible_po_material_fields.get('weight_unit', False)
            ),
        }
        
        # Create tables
        open_table = ProcurementPurchaseOrderTable(open_orders, prefix='open-', accessible_fields=table_accessible_fields)
        completed_table = ProcurementPurchaseOrderTable(completed_orders, prefix='completed-', accessible_fields=table_accessible_fields)
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 15}).configure(open_table)
        RequestConfig(request, paginate={'per_page': 15}).configure(completed_table)
        
        # دریافت لیست تامین‌کنندگان برای dropdown
        from core.PersonFolder.PersonModel import Person
        suppliers = Person.objects.filter(type='supplier').order_by('name')
        
        context = {
            'open_table': open_table,
            'completed_table': completed_table,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
            'search_query': search_query,
            'status_filter': status_filter,
            'supplier_filter': supplier_filter,
            'suppliers': suppliers,
        }
        return render(request, 'purchase/procurement_order_list.html', context)
    except Exception as e:
        bug_logger.error(f"Purchase order management error: {e}")
        messages.error(request, 'خطا در بارگذاری سفارش‌های خرید.')
        from supply.tables import ProcurementPurchaseOrderTable
        table_accessible_fields = {
            'order_number': accessible_po_fields.get('order_number', False),
            'status': accessible_po_fields.get('status', False),
            'materials_list': False,
            'supplier': False,
            'created_by': accessible_po_fields.get('created_by', False),
            'created_at': accessible_po_fields.get('created_at', False),
            'total_weight': False,
        }
        open_table = ProcurementPurchaseOrderTable([], prefix='open-', accessible_fields=table_accessible_fields)
        completed_table = ProcurementPurchaseOrderTable([], prefix='completed-', accessible_fields=table_accessible_fields)
        return render(request, 'purchase/procurement_order_list.html', {
            'open_table': open_table,
            'completed_table': completed_table,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
            'accessible_raw_material_fields': accessible_raw_material_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
        })


@login_required
def create_procurement_purchase_order_view(request):
    """ایجاد سفارش خرید جدید"""
    audit_logger.info("ایجاد سفارش خرید جدید")
    
    # Check task permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_CREATE_ORDER.value):
        audit_logger.activity(f"تلاش برای دسترسی به ایجاد سفارش خرید بدون مجوز - کاربر: {request.user.username}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions (edit permissions for form)
    accessible_po_fields = {
        'customer': user_can_access_field(request.user, Order, 'customer', 'edit'),
        'freight_payment_type': user_can_access_field(request.user, Order, 'freight_payment_type', 'edit'),
        'subtotal_without_freight': user_can_access_field(request.user, Order, 'subtotal_without_freight', 'edit'),
        'freight_cost': user_can_access_field(request.user, Order, 'freight_cost', 'edit'),
        'external_system_id': user_can_access_field(request.user, Order, 'external_system_id', 'edit'),
        'ordered_at': user_can_access_field(request.user, Order, 'ordered_at', 'edit'),
    }
    
    accessible_po_material_fields = {
        'raw_material': user_can_access_field(request.user, OrderItem, 'raw_material', 'edit'),
        'quantity': user_can_access_field(request.user, OrderItem, 'quantity', 'edit'),
        'weight_unit': user_can_access_field(request.user, OrderItem, 'weight_unit', 'edit'),
        'notes': user_can_access_field(request.user, OrderItem, 'notes', 'edit'),
        'unit_price': user_can_access_field(request.user, OrderItem, 'unit_price', 'edit'),
        'total_purchase_cost': user_can_access_field(request.user, OrderItem, 'total_purchase_cost', 'edit'),
        'vat_percent': user_can_access_field(request.user, OrderItem, 'vat_percent', 'edit'),
        'freight_cost': user_can_access_field(request.user, OrderItem, 'freight_cost', 'edit'),
        'external_allocation_id': user_can_access_field(request.user, OrderItem, 'external_allocation_id', 'edit'),
    }
    
    try:
        if request.method == 'POST':
            form = ProcurementPurchaseOrderForm(request.POST, request.FILES)
            if form.is_valid():
                with transaction.atomic():
                    
                    po = form.save(commit=False)
                    print("ordered at: ", po.ordered_at)
                    po.order_type = 'purchase'
                    po.status = Order.STATUS_DRAFT  # تنظیم وضعیت به پیش‌نویس
                    po.registered_by = request.user
                    
                    # محاسبه خودکار subtotal_without_freight از مجموع total_purchase_cost اقلام
                    material_formset = MaterialFormSet(request.POST, prefix='mat')
                    if material_formset.is_valid():
                        # محاسبه مجموع قبل از ذخیره
                        total_subtotal = Decimal('0')
                        for material_form in material_formset:
                            if material_form.cleaned_data and not material_form.cleaned_data.get('DELETE', False):
                                # بررسی اینکه آیا فرم خالی است
                                raw_material_id_value = material_form.cleaned_data.get('raw_material_id', '')
                                raw_material_id = raw_material_id_value.strip() if isinstance(raw_material_id_value, str) else ''
                                raw_material_value = material_form.cleaned_data.get('raw_material', '')
                                raw_material_text = raw_material_value.strip() if isinstance(raw_material_value, str) else ''
                                quantity = material_form.cleaned_data.get('quantity')
                                
                                # اگر فرم خالی است، آن را نادیده بگیر
                                if not raw_material_id and not raw_material_text and not quantity:
                                    continue
                                
                                total_purchase_cost = material_form.cleaned_data.get('total_purchase_cost')
                                if total_purchase_cost:
                                    total_subtotal += Decimal(str(total_purchase_cost))
                        
                        po.subtotal_without_freight = total_subtotal
                        po.save()  # triggers order_number generation, status defaults to DRAFT
                        
                        # Create initial status log for DRAFT
                        OrderStatusLog.objects.create(
                            order=po,
                            old_status='',
                            new_status=po.status,
                            changed_by=request.user,
                            note='ایجاد سفارش خرید'
                        )
                        
                        material_formset.instance = po
                        material_formset.save()
                        
                        # تغییر وضعیت به "در انتظار تعریف حمل" بعد از ذخیره مواد اولیه
                        if po.status == Order.STATUS_DRAFT:
                            po.transition(Order.STATUS_AWAITING_TRANSPORT_DEFINITION, user=request.user, note='مواد اولیه ثبت شد')
                    else:
                        bug_logger.warning(f"Material formset invalid on create: {material_formset.errors}")
                        messages.error(request, 'مواد اولیه تکراری یا نامعتبر هستند. لطفاً خطاهای فرم را بررسی و اصلاح کنید.')
                        # Rollback parent creation to avoid orphan PO
                        try:
                            po.delete()
                        except Exception:
                            pass
                        return render(request, 'purchase/create_procurement_order.html', {
                            'form': form,
                            'material_formset': material_formset,
                            'accessible_po_fields': accessible_po_fields,
                            'accessible_po_material_fields': accessible_po_material_fields,
                        })
                messages.success(request, 'سفارش خرید ثبت شد.')
                return redirect(reverse('supply:purchase_order_management'))
            else:
                bug_logger.warning(f"Procurement PO form invalid: {form.errors}")
                material_formset = MaterialFormSet(request.POST, prefix='mat')
        else:
            form = ProcurementPurchaseOrderForm()
            material_formset = MaterialFormSet(prefix='mat')
        return render(request, 'purchase/create_procurement_order.html', {
            'form': form,
            'material_formset': material_formset,
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        })
    except Exception as e:
        bug_logger.error(f"Create procurement PO error: {e}")
        messages.error(request, 'خطا در ایجاد سفارش خرید.')
        return render(request, 'purchase/create_procurement_order.html', {
            'form': ProcurementPurchaseOrderForm(),
            'material_formset': MaterialFormSet(prefix='mat'),
            'accessible_po_fields': accessible_po_fields,
            'accessible_po_material_fields': accessible_po_material_fields,
        })


@login_required
def procurement_purchase_order_detail_view(request, order_number):
    """جزئیات سفارش خرید"""
    audit_logger.info(f"مشاهده جزئیات سفارش خرید {order_number}")
    from supply.tables import ProcurementPurchaseOrderStatusLogTable
    from core.TransportFolder.TransportModel import Transport
    
    # ابتدا سعی می‌کنیم سفارش را با order_type='purchase' پیدا کنیم
    try:
        po = Order.objects.get(order_number=order_number, order_type='purchase')
    except Order.DoesNotExist:
        # اگر پیدا نشد، سعی می‌کنیم بدون فیلتر order_type پیدا کنیم
        try:
            po = Order.objects.get(order_number=order_number)
            # اگر order_type null است یا purchase نیست، خطا می‌دهیم
            if po.order_type is None:
                bug_logger.warning(f"سفارش {order_number} دارای order_type null است")
                messages.error(request, f'سفارش {order_number} دارای نوع سفارش مشخصی نیست. لطفاً نوع سفارش را تنظیم کنید.')
                return redirect('supply:purchase_transport_list')
            elif po.order_type != 'purchase':
                bug_logger.warning(f"سفارش {order_number} از نوع {po.order_type} است نه purchase")
                messages.error(request, f'سفارش {order_number} یک سفارش خرید نیست.')
                return redirect('supply:purchase_transport_list')
        except Order.DoesNotExist:
            # اگر اصلاً سفارش پیدا نشد
            bug_logger.error(f"سفارش {order_number} یافت نشد")
            messages.error(request, f'سفارش {order_number} یافت نشد.')
            return redirect('supply:purchase_transport_list')
    materials = po.order_items.filter(raw_material__isnull=False).select_related('raw_material').all()
    raw_material_infos = RawMaterialInfo.objects.filter(
        order_item__order=po
    ).select_related('order_item')
    totals_by_item_id = {}
    for raw_material_info in raw_material_infos:
        bucket = totals_by_item_id.setdefault(
            raw_material_info.order_item_id,
            {'total_net_weight': Decimal('0'), 'total_waybill_weight': Decimal('0')}
        )
        if raw_material_info.net_weight is not None:
            bucket['total_net_weight'] += raw_material_info.net_weight
        if raw_material_info.waybill_weight is not None:
            bucket['total_waybill_weight'] += raw_material_info.waybill_weight

    for material in materials:
        item_totals = totals_by_item_id.get(material.id, {})
        material.total_net_weight = item_totals.get('total_net_weight')
        material.total_waybill_weight = item_totals.get('total_waybill_weight')
    logs = po.status_logs.all().order_by('-changed_at')
    log_table = ProcurementPurchaseOrderStatusLogTable(logs)
    RequestConfig(request, paginate=False).configure(log_table)
    can_edit_financial = not po.payment_confirmed
    can_delete = po.can_delete()  # محاسبه مقدار can_delete برای استفاده در template
    
    # اگر تمام مواد تخصیص یافته و وضعیت هنوز «در انتظار تعریف حمل» است، وضعیت را به‌روز کن
    if po.status == Order.STATUS_AWAITING_TRANSPORT_DEFINITION:
        remaining_weight = po.get_remaining_weight()
        if remaining_weight <= Decimal('0'):
            try:
                po.transition(Order.STATUS_AWAITING_VEHICLE_ENTRY, user=request.user, note='تمام مواد اولیه به حمل‌ها تخصیص یافت')
                messages.success(request, 'وضعیت سفارش به «در انتظار ورود خودرو» به‌روزرسانی شد.')
            except Exception as transition_err:
                bug_logger.warning(f"خطا در تغییر وضعیت سفارش {po.order_number}: {transition_err}")
    
    # Get transports for this purchase order
    transports = Transport.objects.filter(allocation__order=po).select_related('driver').order_by('-created_at')
    
    # Create tables for materials and transports
    from supply.tables import PurchaseOrderMaterialTable, PurchaseOrderTransportTable
    material_table = PurchaseOrderMaterialTable(materials)
    RequestConfig(request, paginate=False).configure(material_table)
    transport_table = PurchaseOrderTransportTable(transports)
    RequestConfig(request, paginate={'per_page': 10}).configure(transport_table)
    
    # Get allowed next statuses for workflow transitions
    allowed_next_statuses = po.WORKFLOW_ALLOWED.get(po.status, set())
    next_status_choices = [(code, label) for code, label in po.STATUS_CHOICES if code in allowed_next_statuses]
    
    # محاسبه جزئیات فی تمام شده خرید
    final_unit_price_details = po.get_final_unit_price_details()
    
    return render(request, 'purchase/procurement_purchase_detail.html', {
        'po': po,
        'material_table': material_table,
        'logs': logs,
        'log_table': log_table,
        'can_edit_financial': can_edit_financial,
        'can_delete': can_delete,
        'next_status_choices': next_status_choices,
        'transport_table': transport_table,
        'final_unit_price_details': final_unit_price_details,
    })


@login_required
def edit_procurement_purchase_order_view(request, order_number):
    """ویرایش سفارش خرید (فقط قبل از تایید پرداخت برای داده مالی)"""
    audit_logger.info(f"ویرایش سفارش خرید {order_number}")
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    if po.status == Order.STATUS_COMPLETED:
        messages.error(request, 'سفارش تکمیل شده قابل ویرایش نیست.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        if request.method == 'POST':
            form = ProcurementPurchaseOrderForm(request.POST, request.FILES, instance=po)
            material_formset = MaterialFormSet(request.POST, instance=po, prefix='mat')
            if form.is_valid() and material_formset.is_valid():
                with transaction.atomic():
                    form.save()
                    material_formset.save()
                messages.success(request, 'سفارش خرید ویرایش شد.')
                return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
            else:
                bug_logger.warning(f"Edit PO invalid form={form.errors} mat={material_formset.errors}")
        else:
            form = ProcurementPurchaseOrderForm(instance=po)
            material_formset = MaterialFormSet(instance=po, prefix='mat')
        return render(request, 'purchase/edit_procurement_order.html', {
            'form': form,
            'material_formset': material_formset,
            'po': po,
        })
    except Exception as e:
        bug_logger.error(f"Edit procurement PO error: {e}")
        messages.error(request, 'خطا در ویرایش سفارش خرید.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))


@login_required
def delete_procurement_purchase_order_view(request, order_number):
    audit_logger.activity(f"حذف سفارش خرید {order_number}")
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    if not po.can_delete():
        messages.error(request, 'حذف فقط در وضعیت پیش‌نویس مجاز است.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        po.delete()
        messages.success(request, 'سفارش خرید حذف شد.')
    except Exception as e:
        bug_logger.error(f"Delete procurement PO error: {e}")
        messages.error(request, 'خطا در حذف سفارش.')
    return redirect(reverse('supply:purchase_order_management'))


@login_required
def transition_procurement_purchase_order_status_view(request, order_number, new_status):
    audit_logger.activity(f"درخواست تغییر وضعیت سفارش خرید {order_number} -> {new_status}")
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    try:
        po.transition(new_status, user=request.user)
        messages.success(request, 'وضعیت سفارش بروزرسانی شد.')
    except ValueError as ve:
        bug_logger.warning(f"Invalid PO status transition {order_number}: {ve}")
        messages.error(request, str(ve))
    except Exception as e:
        bug_logger.error(f"Transition procurement PO error: {e}")
        messages.error(request, 'خطای تغییر وضعیت سفارش.')
    return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))


@login_required
def confirm_procurement_purchase_order_payment_view(request, order_number):
    """تایید پرداخت سفارش خرید و قفل شدن داده‌های مالی"""
    audit_logger.activity(f"تایید پرداخت سفارش خرید {order_number}")
    po = get_object_or_404(Order, order_number=order_number, order_type='purchase')
    if po.payment_confirmed:
        messages.info(request, 'پرداخت قبلاً تایید شده است.')
        return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))
    try:
        po.payment_confirmed = True
        po.save(update_fields=['payment_confirmed'])
        OrderStatusLog.objects.create(
            order=po,
            old_status=po.status,
            new_status=po.status,
            changed_by=request.user,
            note='تایید پرداخت'
        )
        messages.success(request, 'پرداخت تایید شد. داده‌های مالی قفل شدند.')
    except Exception as e:
        bug_logger.error(f"Confirm payment PO error: {e}")
        messages.error(request, 'خطا در تایید پرداخت.')
    return redirect(reverse('supply:procurement_purchase_order_detail', kwargs={'order_number': order_number}))


@login_required
@require_http_methods(["GET"])
def supplier_search_api(request):
    """
    API endpoint برای جستجوی تامین‌کننده‌ها
    """
    audit_logger.info("جستجوی تامین‌کننده از طریق API")
    query = request.GET.get('q', '').strip()
    
    if not query:
        # اگر کوئری خالی است، 20 تامین‌کننده اخیر را برگردان
        suppliers = Person.objects.filter(
            type='supplier'
        ).order_by('name')[:20]
    else:
        # فیلتر کردن تامین‌کننده‌ها
        suppliers = Person.objects.filter(
            type='supplier'
        ).filter(
            Q(name__icontains=query) | Q(national_id__icontains=query)
        ).order_by('name')[:20]
    
    results = []
    for supplier in suppliers:
        results.append({
            'id': supplier.national_id,
            'text': f"{supplier.name} ({supplier.national_id})"
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def raw_material_search_api(request):
    """
    API endpoint برای جستجوی مواد اولیه
    """
    audit_logger.info("جستجوی مواد اولیه از طریق API")
    query = request.GET.get('q', '').strip()
    
    if not query:
        # اگر کوئری خالی است، 20 ماده اولیه فعال را برگردان
        raw_materials = RawMaterial.objects.filter(
            status='active'
        ).order_by('name')[:20]
    else:
        # فیلتر کردن مواد اولیه فعال
        raw_materials = RawMaterial.objects.filter(
            status='active'
        ).filter(
            Q(name__icontains=query) | Q(raw_material_id__icontains=query)
        ).order_by('name')[:20]
    
    results = []
    for rm in raw_materials:
        results.append({
            'id': rm.id,
            'text': f"{rm.raw_material_id or ''} - {rm.name}",
            'primary_unit': rm.primary_unit or '',
            'secondary_unit': rm.secondary_unit or '',
            'primary_unit_display': rm.get_primary_unit_display() if rm.primary_unit else '',
            'secondary_unit_display': rm.get_secondary_unit_display() if rm.secondary_unit else '',
        })
    
    return JsonResponse({'results': results})


@login_required
@require_http_methods(["GET"])
def raw_material_info_api(request, raw_material_id):
    """
    API endpoint برای دریافت اطلاعات کامل ماده اولیه شامل:
    - واحدهای اصلی و فرعی
    - آخرین استعلام قیمت (اگر تامین‌کننده مشخص باشد، استعلام مربوط به آن تامین‌کننده)
    - درصد مالیات بر ارزش افزوده از اطلاعات خرید
    """
    audit_logger.info(f"دریافت اطلاعات ماده اولیه از طریق API - شناسه: {raw_material_id}")
    if not raw_material_id:
        audit_logger.alert("درخواست اطلاعات ماده اولیه بدون شناسه")
        return JsonResponse({'error': 'شناسه ماده اولیه الزامی است'}, status=400)
    
    try:
        raw_material = RawMaterial.objects.get(id=raw_material_id, status='active')
        
        # دریافت تامین‌کننده از query parameter (اختیاری)
        supplier_national_id = request.GET.get('supplier_id', '').strip()
        
        # دریافت آخرین استعلام قیمت
        from core.SupplyFolder.RawMaterialPriceInquiryModel import RawMaterialPriceInquiry
        inquiry_query = RawMaterialPriceInquiry.objects.filter(
            raw_material=raw_material
        )
        
        # اگر تامین‌کننده مشخص شده باشد، فقط استعلام‌های مربوط به آن تامین‌کننده را در نظر بگیر
        if supplier_national_id:
            try:
                supplier = Person.objects.get(national_id=supplier_national_id, type='supplier')
                inquiry_query = inquiry_query.filter(supplier=supplier)
            except Person.DoesNotExist:
                # اگر تامین‌کننده پیدا نشد، از آخرین استعلام عمومی استفاده کن
                pass
        
        latest_inquiry = inquiry_query.order_by('-inquiry_date', '-created_at').first()
        
        # دریافت اطلاعات خرید (برای vat_percentage)
        from core.RawMaterialFolder.RawMaterialPurchaseInfoModel import RawMaterialPurchaseInfo
        purchase_info = RawMaterialPurchaseInfo.objects.filter(
            raw_material=raw_material
        ).first()
        
        # ساخت لیست واحدهای قابل استفاده - واحدها فقط از تعریف ماده اولیه
        available_units = []
        if raw_material.primary_unit:
            primary_display = raw_material.get_primary_unit_display()
            available_units.append({
                'value': raw_material.primary_unit,
                'display': primary_display,
                'is_main': True
            })
        if raw_material.secondary_unit:
            secondary_display = raw_material.get_secondary_unit_display()
            # فقط اگر با واحد اصلی متفاوت باشد اضافه کن
            if secondary_display != (raw_material.get_primary_unit_display() if raw_material.primary_unit else ''):
                available_units.append({
                    'value': raw_material.secondary_unit,
                    'display': secondary_display,
                    'is_main': False
                })
        
        if not available_units:
            available_units.append({
                'value': 'kg',
                'display': 'کیلوگرم',
                'is_main': True
            })
        
        data = {
            'primary_unit': raw_material.get_primary_unit_display() if raw_material.primary_unit else '',
            'secondary_unit': raw_material.get_secondary_unit_display() if raw_material.secondary_unit else '',
            'available_units': available_units,
            'latest_price': str(latest_inquiry.price) if latest_inquiry else None,
            'vat_percentage': f'{purchase_info.vat_percentage:.2f}' if purchase_info and purchase_info.vat_percentage is not None else '0.00',
        }
        
        return JsonResponse(data)
    except RawMaterial.DoesNotExist:
        return JsonResponse({'error': 'ماده اولیه یافت نشد'}, status=404)
    except Exception as e:
        bug_logger.error(f"خطا در دریافت اطلاعات ماده اولیه {raw_material_id}: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
