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
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه اولیه
    initial_freight = forms.DecimalField(
        label='کرایه اولیه',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه کل
    total_freight = forms.DecimalField(
        label='کرایه کل',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # تخفیف
    discount = forms.DecimalField(
        label='تخفیف',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # مازاد
    surplus = forms.DecimalField(
        label='مازاد',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # کرایه پرداختی
    freight_payment = forms.DecimalField(
        label='کرایه پرداختی',
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    
    # شناسه انبار
    warehouse_identifier = forms.CharField(
        label='شناسه انبار',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


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
    
    def render_actions(self, record):
        identifier = record.transport_number or record.transport_id
        detail_url = reverse('supply:warehouse_delivery_detail', args=[identifier])
        return format_html(
            '<a href="{}" class="btn btn-primary btn-sm">ثبت اطلاعات تخلیه</a>',
            detail_url
        )
    
    class Meta(PurchaseTransportTable.Meta):
        sequence = ('transport_number', 'vehicle_type', 'raw_materials', 'plate_number', 'status', 'created_at', 'actions')


@login_required
def warehouse_delivery_list_view(request):
    """صفحه لیست حمل‌های در انتظار تخلیه - مخصوص انباردار"""
    audit_logger.info("مشاهده صفحه تحویل انبار")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه تحویل انبار بدون دسترسی")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        # حمل‌های در وضعیت های قابل تحویل انبار
        transports_qs = PurchaseTransport.objects.filter(
            status=PurchaseTransport.STATUS_AWAITING_UNLOADING
        ).select_related('purchase_order', 'driver').order_by('-created_at')

        # Ensure transport_number is populated for all records
        transports = []
        for pt in transports_qs:
            if not pt.transport_number:
                try:
                    bug_logger.debug(f"Backfilling transport_number for transport_id={pt.transport_id}")
                    pt.save()
                except Exception as gen_err:
                    bug_logger.warning(f"Failed to backfill transport_number for transport_id={pt.transport_id}: {gen_err}")
            transports.append(pt)
        
        table = WarehouseDeliveryTable(transports, prefix='wh-')
        RequestConfig(request, paginate={'per_page': 20}).configure(table)
        
        return render(request, 'supply_warehouse_delivery_list.html', {'table': table})
    except Exception as e:
        bug_logger.error(f"Warehouse delivery list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست تحویل انبار.')
        return render(request, 'supply_warehouse_delivery_list.html', {
            'table': WarehouseDeliveryTable([], prefix='wh-')
        })


@login_required
def warehouse_delivery_detail_view(request, transport_number):
    """صفحه اطلاعات تخلیه - ثبت وزن‌ها و اطلاعات مالی"""
    audit_logger.info(f"دسترسی به صفحه تخلیه حمل {transport_number}")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_WAREHOUSE_DELIVERY.value):
        audit_logger.activity(f"تلاش برای ثبت تخلیه بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به ثبت تخلیه را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Support both transport_number and numeric transport_id as identifier
    try:
        if transport_number and str(transport_number).isdigit():
            pt = get_object_or_404(PurchaseTransport, transport_id=int(transport_number))
        else:
            pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    except Exception as e:
        bug_logger.error(f"Warehouse delivery detail fetch error for identifier={transport_number}: {e}")
        messages.error(request, 'شناسه حمل نامعتبر است یا یافت نشد.')
        return redirect(reverse('supply:warehouse_delivery'))
    
    if pt.status != PurchaseTransport.STATUS_AWAITING_UNLOADING:
        audit_logger.activity(f"تلاش برای ثبت تخلیه با وضعیت نامعتبر - حمل {transport_number}: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل ثبت تخلیه نیست.')
        return redirect(reverse('supply:warehouse_delivery'))
    
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
                    
                    # به‌روزرسانی فیلدهای حمل
                    pt.gross_weight = gross
                    pt.tare_weight = tare
                    pt.net_weight = net_weight
                    pt.freight_payment_type = data.get('freight_payment_type')
                    pt.initial_freight = data.get('initial_freight')
                    pt.total_freight = data.get('total_freight')
                    pt.discount = data.get('discount')
                    pt.surplus = data.get('surplus')
                    pt.freight_payment = data.get('freight_payment')
                    
                    # ثبت تاریخ تخلیه
                    pt.loading_date = jdatetime.date.today()
                    pt.save()
                    
                    bug_logger.info(f"اطلاعات تخلیه برای حمل {transport_number} ثبت شد - وزن خالص: {net_weight}")
                    
                    # تغییر وضعیت به "در انتظار تطبیق انبار"
                    try:
                        pt.transition(
                            PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION,
                            user=request.user,
                            note=f'تکمیل تخلیه - وزن خالص: {net_weight} - نوع کرایه: {data.get("freight_payment_type")}'
                        )
                        bug_logger.info(f"وضعیت حمل {transport_number} به 'در انتظار تطبیق انبار' تغییر یافت")
                    except Exception as trans_err:
                        bug_logger.error(f"خطا در تغییر وضعیت حمل {transport_number}: {trans_err}")
                        raise
                    
                    audit_logger.info(f"تخلیه تکمیل شد - حمل: {transport_number} - وزن خالص: {net_weight}")
                    
                messages.success(request, 'اطلاعات تخلیه ثبت شد و حمل به مرحله تطبیق انبار منتقل شد.')
                return redirect(reverse('supply:warehouse_delivery'))
            except Exception as e:
                bug_logger.error(f"خطا در ثبت تخلیه برای حمل {transport_number}: {e}")
                messages.error(request, 'خطا در ثبت اطلاعات تخلیه.')
        else:
            bug_logger.warning(f"فرم ثبت تخلیه نامعتبر برای حمل {transport_number}: {form.errors}")
            audit_logger.activity(f"فرم نامعتبر برای ثبت تخلیه حمل {transport_number}")
    else:
        # پیش‌پر کردن فرم با داده‌های موجود
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
        'pt': pt
    })
