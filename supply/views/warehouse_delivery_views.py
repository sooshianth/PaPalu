import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.db import transaction
from django.http import HttpResponseForbidden
from django_tables2 import RequestConfig
import jdatetime

from core.logging_levels import *
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrder
from core.RBACModel.TaskPermission import TaskChoices
from core.RBACModel.Roles import user_has_task
from supply.tables import PurchaseTransportTable
import django_tables2 as tables
from django.utils.html import format_html


class WarehouseDeliveryForm(forms.Form):
    """فرم تحویل انبار - صفحه اطلاعات تخلیه"""
    # وزن ها
    gross_weight = forms.DecimalField(
        label='وزن پر',
        required=True,
        max_digits=15,
        decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    tare_weight = forms.DecimalField(
        label='وزن خالی',
        required=True,
        max_digits=15,
        decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    
    # نوع کرایه
    freight_payment_type = forms.ChoiceField(
        label='نوع کرایه',
        choices=[
            ('', 'انتخاب کنید'),
            ('cash', 'نقدی'),
            ('credit', 'اعتباری'),
        ],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # فی حمل
    freight_rate = forms.DecimalField(
        label='فی حمل',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه اولیه
    initial_freight = forms.DecimalField(
        label='کرایه اولیه',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه کل
    total_freight = forms.DecimalField(
        label='کرایه کل',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # تخفیف
    discount = forms.DecimalField(
        label='تخفیف',
        required=True,
        max_digits=15,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'})
    )
    
    # مازاد
    surplus = forms.DecimalField(
        label='مازاد',
        required=True,
        max_digits=15,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'value': '0'})
    )
    
    # کرایه پرداختی
    freight_payment = forms.DecimalField(
        label='کرایه پرداختی',
        required=True,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # شناسه انبار
    warehouse_identifier = forms.CharField(
        label='شناسه انبار',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        """اعتبارسنجی کلی فرم"""
        cleaned_data = super().clean()
        gross = cleaned_data.get('gross_weight')
        tare = cleaned_data.get('tare_weight')
        
        bug_logger.debug(f"Form validation - gross_weight: {gross}, tare_weight: {tare}")
        
        # وزن پر باید بزرگتر از وزن خالی باشد
        if gross and tare:
            if gross <= tare:
                bug_logger.warning(f"Invalid weights - gross ({gross}) <= tare ({tare})")
                raise forms.ValidationError(
                    'وزن پر باید همیشه بزرگ‌تر از وزن خالی باشد.'
                )
            
            net_weight = gross - tare
            bug_logger.debug(f"Calculated net_weight: {net_weight}")
            if net_weight <= 0:
                bug_logger.warning(f"Invalid net_weight: {net_weight}")
                raise forms.ValidationError(
                    'مقدار تحویلی (وزن پر − وزن خالی) نامعقول است.'
                )
        
        return cleaned_data


class WarehouseDeliveryTable(PurchaseTransportTable):
    """جدول حمل‌های در انتظار تخلیه"""
    
    raw_materials = tables.Column(
        verbose_name='نام ماده اولیه',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def render_raw_materials(self, record):
        """نمایش لیست مواد اولیه از سفارش خرید"""
        if not record.purchase_order:
            return '—'
        materials = record.purchase_order.materials.select_related('raw_material').all()
        if materials:
            names = [m.raw_material.name for m in materials if m.raw_material]
            return format_html('<br>'.join(names)) if names else '—'
        return '—'
    
    quantity = tables.Column(
        verbose_name='مقدار',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    unit = tables.Column(
        verbose_name='واحد',
        empty_values=(),
        orderable=False,
        attrs={
            'td': {'class': 'text-center'},
            'th': {'class': 'text-center'}
        }
    )
    
    def render_quantity(self, record):
        """نمایش مقدار سفارش"""
        if not record.purchase_order:
            return '—'
        materials = record.purchase_order.materials.all()
        if materials:
            quantities = [str(m.quantity) for m in materials]
            return format_html('<br>'.join(quantities)) if quantities else '—'
        return '—'
    
    def render_unit(self, record):
        """نمایش واحد سفارش"""
        if not record.purchase_order:
            return '—'
        materials = record.purchase_order.materials.all()
        if materials:
            units = [m.unit or '—' for m in materials]
            return format_html('<br>'.join(units)) if units else '—'
        return '—'
    
    def render_actions(self, record):
        identifier = record.transport_number or record.transport_id
        detail_url = reverse('supply:warehouse_delivery_detail', args=[identifier])
        return format_html(
            '<a href="{}" class="btn btn-primary btn-sm">ثبت اطلاعات تخلیه</a>',
            detail_url
        )
    
    class Meta(PurchaseTransportTable.Meta):
        sequence = ('purchase_order', 'raw_materials', 'quantity', 'unit', 'plate_number', 'vehicle_type', 'actions')


@login_required
def warehouse_delivery_list_view(request):
    """صفحه لیست حمل‌های در انتظار تخلیه - مخصوص انباردار"""
    audit_logger.info("مشاهده صفحه تحویل انبار")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه تحویل انبار بدون دسترسی")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        # حمل‌های در وضعیت های قابل تحویل انبار (awaiting_unloading for warehouseman)
        transports_unloading_qs = PurchaseTransport.objects.filter(
            status=PurchaseTransport.STATUS_AWAITING_UNLOADING
        ).select_related('purchase_order', 'driver').order_by('-created_at')
        
        bug_logger.debug(f"Found {transports_unloading_qs.count()} transports awaiting unloading")
        
        # حمل‌های در انتظار تایید خروج توسط نگهبان (awaiting_wh_reconciliation)
        transports_guard_qs = PurchaseTransport.objects.filter(
            status=PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION
        ).select_related('purchase_order', 'driver').order_by('-created_at')
        
        bug_logger.debug(f"Found {transports_guard_qs.count()} transports awaiting guard reconciliation")

        # Ensure transport_number is populated for all records
        transports_unloading = []
        for pt in transports_unloading_qs:
            if not pt.transport_number:
                try:
                    bug_logger.debug(f"Backfilling transport_number for transport_id={pt.transport_id}")
                    pt.save()
                except Exception as gen_err:
                    bug_logger.warning(f"Failed to backfill transport_number for transport_id={pt.transport_id}: {gen_err}")
            transports_unloading.append(pt)
        
        transports_guard = []
        for pt in transports_guard_qs:
            if not pt.transport_number:
                try:
                    pt.save()
                except Exception as gen_err:
                    bug_logger.warning(f"Failed to backfill transport_number for transport_id={pt.transport_id}: {gen_err}")
            transports_guard.append(pt)
        
        table_unloading = WarehouseDeliveryTable(transports_unloading, prefix='wh-')
        RequestConfig(request, paginate={'per_page': 20}).configure(table_unloading)
        
        from supply.tables import GuardExitTable
        table_guard = GuardExitTable(transports_guard, prefix='guard-')
        RequestConfig(request, paginate={'per_page': 20}).configure(table_guard)
        
        return render(request, 'supply_warehouse_delivery_list.html', {
            'table': table_unloading,
            'guard_table': table_guard,
        })
    except Exception as e:
        bug_logger.error(f"Warehouse delivery list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست تحویل انبار.')
        return render(request, 'supply_warehouse_delivery_list.html', {
            'table': WarehouseDeliveryTable([], prefix='wh-')
        })


@login_required
def warehouse_delivery_detail_view(request, transport_number):
    """صفحه اطلاعات تخلیه - ثبت وزن‌ها و اطلاعات مالی (انباردار)"""
    audit_logger.info(f"دسترسی به صفحه تخلیه حمل {transport_number}")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
        audit_logger.activity(f"تلاش برای ثبت تخلیه بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به ثبت تخلیه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Support both transport_number and numeric transport_id as identifier
    try:
        if transport_number and str(transport_number).isdigit():
            bug_logger.debug(f"Fetching transport by transport_id: {transport_number}")
            pt = get_object_or_404(PurchaseTransport, transport_id=int(transport_number))
        else:
            bug_logger.debug(f"Fetching transport by transport_number: {transport_number}")
            pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
        bug_logger.debug(f"Transport found - ID: {pt.transport_id}, Status: {pt.status}, Order: {pt.purchase_order.order_number if pt.purchase_order else 'N/A'}")
    except Exception as e:
        bug_logger.error(f"Warehouse delivery detail fetch error for identifier={transport_number}: {e}")
        messages.error(request, 'شناسه حمل نامعتبر است یا یافت نشد.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    # Allow viewing in awaiting_unloading (for data entry) or awaiting_wh_reconciliation (read-only)
    if pt.status not in [PurchaseTransport.STATUS_AWAITING_UNLOADING, PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION]:
        audit_logger.activity(f"تلاش برای دسترسی به تخلیه با وضعیت نامعتبر - حمل {transport_number}: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل مشاهده نیست.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    # Only allow editing if status is awaiting_unloading
    if pt.status != PurchaseTransport.STATUS_AWAITING_UNLOADING:
        # Read-only mode for awaiting_wh_reconciliation
        bug_logger.debug(f"Loading read-only form for transport {transport_number} - status: {pt.status}")
        initial = {
            'gross_weight': pt.gross_weight,
            'tare_weight': pt.tare_weight,
            'freight_payment_type': pt.freight_payment_type,
            'freight_rate': getattr(pt, 'freight_rate', None),
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
            'warehouse_identifier': getattr(pt, 'warehouse_identifier', None),
        }
        form = WarehouseDeliveryForm(initial=initial)
        for field in form.fields:
            form.fields[field].disabled = True
        
        return render(request, 'supply_warehouse_delivery_detail.html', {
            'form': form,
            'pt': pt,
            'read_only': True,
            'awaiting_guard': True,
        })
    
    if request.method == 'POST':
        form = WarehouseDeliveryForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            audit_logger.info(f"شروع ثبت تخلیه برای حمل {transport_number}")
            
            try:
                with transaction.atomic():
                    # محاسبه وزن خالص
                    gross = data.get('gross_weight')
                    tare = data.get('tare_weight')
                    net_weight = gross - tare if gross and tare else None
                    warehouse_id = data.get('warehouse_identifier')
                    
                    bug_logger.debug(f"Saving unloading data - Transport: {transport_number}, Gross: {gross}, Tare: {tare}, Net: {net_weight}, Warehouse: {warehouse_id}")
                    
                    # به‌روزرسانی فیلدهای حمل
                    pt.gross_weight = gross
                    pt.tare_weight = tare
                    pt.net_weight = net_weight
                    pt.freight_payment_type = data.get('freight_payment_type')
                    pt.initial_freight = data.get('initial_freight')
                    pt.total_freight = data.get('total_freight')
                    pt.discount = data.get('discount', 0)
                    pt.surplus = data.get('surplus', 0)
                    pt.freight_payment = data.get('freight_payment')
                    
                    # ثبت تاریخ تخلیه
                    pt.loading_date = jdatetime.date.today()
                    pt.save()
                    
                    bug_logger.info(f"اطلاعات تخلیه برای حمل {transport_number} ثبت شد - وزن خالص: {net_weight}")
                    
                    # TODO: افزایش موجودی انبار
                    # این قسمت باید لاگ موجودی از انبار مجازی تامین‌کنندگان به انبار با شناسه {warehouse_id} ایجاد کند
                    # مقدار افزایش: net_weight
                    # کد نمونه:
                    # from core.WarehouseFolder.InventoryLog import InventoryLog
                    # InventoryLog.objects.create(
                    #     warehouse_id=warehouse_id,
                    #     raw_material=pt.purchase_order.materials.first().raw_material,
                    #     quantity=net_weight,
                    #     transaction_type='inbound',
                    #     reference_transport=pt,
                    #     created_by=request.user
                    # )
                    
                    # تغییر وضعیت به "در انتظار تطبیق انبار"
                    try:
                        pt.transition(
                            PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION,
                            user=request.user,
                            note=f'تکمیل تخلیه - وزن خالص: {net_weight} - انبار: {warehouse_id} - نوع کرایه: {data.get("freight_payment_type")}'
                        )
                        bug_logger.info(f"وضعیت حمل {transport_number} به 'در انتظار تطبیق انبار' تغییر یافت")
                    except Exception as trans_err:
                        bug_logger.error(f"خطا در تغییر وضعیت حمل {transport_number}: {trans_err}")
                        raise
                    
                    # ثبت در Audit Trail
                    audit_logger.info(
                        f"تخلیه تکمیل شد - "
                        f"حمل: {transport_number} - "
                        f"سفارش: {pt.purchase_order.order_number} - "
                        f"وزن پر: {gross} - "
                        f"وزن خالی: {tare} - "
                        f"وزن خالص: {net_weight} - "
                        f"انبار: {warehouse_id} - "
                        f"کاربر: {request.user.username} - "
                        f"کرایه پرداختی: {data.get('freight_payment')}"
                    )
                    
                messages.success(request, f'اطلاعات تخلیه ثبت شد. وزن خالص: {net_weight} - حمل به مرحله تطبیق انبار منتقل شد.')
                return redirect(reverse('supply:warehouse_delivery'))
            except Exception as e:
                bug_logger.error(f"خطا در ثبت تخلیه برای حمل {transport_number}: {e}")
                messages.error(request, f'خطا در ثبت اطلاعات تخلیه: {str(e)}')
        else:
            bug_logger.warning(f"فرم ثبت تخلیه نامعتبر برای حمل {transport_number}: {form.errors}")
            audit_logger.activity(f"فرم نامعتبر برای ثبت تخلیه حمل {transport_number}")
    else:
        # پیش‌پر کردن فرم با داده‌های موجود
        bug_logger.debug(f"Initializing edit form for transport {transport_number} with existing data")
        initial = {
            'gross_weight': pt.gross_weight,
            'tare_weight': pt.tare_weight,
            'freight_payment_type': pt.freight_payment_type,
            'initial_freight': pt.initial_freight,
            'total_freight': pt.total_freight,
            'discount': pt.discount,
            'surplus': pt.surplus,
            'freight_payment': pt.freight_payment,
        }
        form = WarehouseDeliveryForm(initial=initial)
    
    return render(request, 'supply_warehouse_delivery_detail.html', {
        'form': form,
        'pt': pt,
        'read_only': False,
        'awaiting_guard': False,
    })


@login_required  
def guard_vehicle_exit_view(request, transport_number):
    """صفحه تایید خروج خودرو توسط نگهبان"""
    audit_logger.info(f"دسترسی نگهبان به صفحه خروج خودرو - حمل {transport_number}")
    
    # Check guard permission - using SUPPLY_REGISTER_VEHICLE_EXIT which is the existing guard permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_VEHICLE_EXIT.value):
        audit_logger.activity(f"تلاش برای تایید خروج خودرو بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به تایید خروج خودرو را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get transport
    try:
        if transport_number and str(transport_number).isdigit():
            bug_logger.debug(f"Guard fetching transport by transport_id: {transport_number}")
            pt = get_object_or_404(PurchaseTransport, transport_id=int(transport_number))
        else:
            bug_logger.debug(f"Guard fetching transport by transport_number: {transport_number}")
            pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
        bug_logger.debug(f"Guard access - Transport: {pt.transport_id}, Status: {pt.status}, Net weight: {pt.net_weight}")
    except Exception as e:
        bug_logger.error(f"Guard exit fetch error for identifier={transport_number}: {e}")
        messages.error(request, 'شناسه حمل نامعتبر است یا یافت نشد.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    # Check status - must be awaiting_wh_reconciliation (warehouseman completed)
    if pt.status != PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION:
        audit_logger.activity(f"تلاش برای خروج خودرو با وضعیت نامعتبر - حمل {transport_number}: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل خروج نیست. ابتدا باید اطلاعات تخلیه توسط انباردار تکمیل شود.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    if request.method == 'POST':
        # Confirm vehicle exit
        bug_logger.debug(f"Guard confirming vehicle exit for transport {transport_number}")
        try:
            with transaction.atomic():
                # Transition to awaiting_settlement
                bug_logger.debug(f"Transitioning transport {transport_number} to awaiting_settlement")
                pt.transition(
                    PurchaseTransport.STATUS_AWAITING_SETTLEMENT,
                    user=request.user,
                    note=f'تایید خروج خودرو توسط نگهبان - وزن خالص: {pt.net_weight}'
                )
                
                audit_logger.info(
                    f"خروج خودرو تایید شد - "
                    f"حمل: {transport_number} - "
                    f"سفارش: {pt.purchase_order.order_number} - "
                    f"نگهبان: {request.user.username} - "
                    f"وزن خالص: {pt.net_weight}"
                )
                
            messages.success(request, f'خروج خودرو تایید شد. حمل {transport_number} به مرحله تسویه منتقل شد.')
            return redirect(reverse('supply:warehouse_delivery'))
        except Exception as e:
            bug_logger.error(f"خطا در تایید خروج خودرو برای حمل {transport_number}: {e}")
            messages.error(request, f'خطا در تایید خروج خودرو: {str(e)}')
    
    return render(request, 'supply_guard_vehicle_exit.html', {
        'pt': pt
    })
