from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import ModelForm
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
import logging
from core.logging_levels import *
from django_tables2 import RequestConfig

from core.TransportFolder.TransportModel import Transport
from core.OrderFolder.OrderModel import Order
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from core.PersonFolder.PersonModel import Person
from django.contrib.auth import get_user_model

User = get_user_model()

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_purchase_transport_fields(user):
    """دریافت فیلدهای قابل دسترس برای مدل Transport"""
    return {
        'transport_number': user_can_access_field(user, Transport, 'transport_number', 'view'),
        'purchase_order': user_can_access_field(user, Transport, 'allocation', 'view'),
        'status': user_can_access_field(user, Transport, 'status', 'view'),
        'transport_type': user_can_access_field(user, Transport, 'transport_type', 'view'),
        'vehicle_type': user_can_access_field(user, Transport, 'vehicle_type', 'view'),
        'plate_number': user_can_access_field(user, Transport, 'plate_number', 'view'),
        'driver': user_can_access_field(user, Transport, 'driver', 'view'),
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'view'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'view'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'view'),
        'discount': user_can_access_field(user, Transport, 'discount', 'view'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'view'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'view'),
        'driver_account_number': user_can_access_field(user, Transport, 'driver_account_number', 'view'),
        'driver_sheba_number': user_can_access_field(user, Transport, 'driver_sheba_number', 'view'),
        'expected_arrival_date': user_can_access_field(user, Transport, 'expected_arrival_date', 'view'),
        'actual_arrival_date': user_can_access_field(user, Transport, 'actual_arrival_date', 'view'),
        'loading_date': user_can_access_field(user, Transport, 'loading_date', 'view'),
        'delivery_date': user_can_access_field(user, Transport, 'delivery_date', 'view'),
        'gross_weight': user_can_access_field(user, Transport, 'gross_weight', 'view'),
        'tare_weight': user_can_access_field(user, Transport, 'tare_weight', 'view'),
        'net_weight': user_can_access_field(user, Transport, 'net_weight', 'view'),
        'waybill_number': user_can_access_field(user, Transport, 'waybill_number', 'view'),
        'notes': user_can_access_field(user, Transport, 'notes', 'view'),
        'created_at': user_can_access_field(user, Transport, 'created_at', 'view'),
        'created_by': user_can_access_field(user, Transport, 'created_by', 'view'),
    }


def get_accessible_procurement_purchase_order_fields_for_transport(user):
    """دریافت فیلدهای قابل دسترس برای مدل ProcurementPurchaseOrder"""
    return {
        'order_number': user_can_access_field(user, Order, 'order_number', 'view'),
        'status': user_can_access_field(user, Order, 'status', 'view'),
        'supplier': user_can_access_field(user, Order, 'supplier', 'view'),
    }


def get_accessible_person_fields_for_transport(user):
    """دریافت فیلدهای قابل دسترس برای مدل Person (driver and supplier)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'national_id': user_can_access_field(user, Person, 'national_id', 'view'),
    }


def get_accessible_user_fields_for_transport(user):
    """دریافت فیلدهای قابل دسترس برای مدل User (created_by)"""
    return {
        'username': user_can_access_field(user, User, 'username', 'view'),
        'first_name': user_can_access_field(user, User, 'first_name', 'view'),
        'last_name': user_can_access_field(user, User, 'last_name', 'view'),
    }


class TransportForm(ModelForm):
    """فرم ایجاد/ویرایش حمل خرید
    
    فیلدهای اجباری:
    - purchase_order (شماره سفارش) - به صورت custom field
    - vehicle_type (نوع ماشین)
    
    transport_type به صورت خودکار به 'inbound' تنظیم می‌شود.
    بقیه فیلدها اختیاری هستند.
    """
    purchase_order = forms.ModelChoiceField(
        queryset=Order.objects.none(),
        label='سفارش خرید',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Transport
        fields = [
            'allocation', 'vehicle_type',
            'plate_number', 'driver',
            'freight_payment_type', 'initial_freight', 'total_freight',
            'discount', 'surplus', 'freight_payment',
            'driver_account_number', 'driver_sheba_number',
            'expected_arrival_date',
            'waybill_number', 'notes'
        ]
        labels = {
            'allocation': 'تخصیص',
            'vehicle_type': 'نوع ماشین',
            'plate_number': 'پلاک',
            'driver': 'راننده',
            'freight_payment_type': 'نوع کرایه',
            'initial_freight': 'کرایه اولیه',
            'total_freight': 'کرایه کل',
            'discount': 'تخفیف',
            'surplus': 'مازاد',
            'freight_payment': 'کرایه پرداختی',
            'driver_account_number': 'شماره حساب راننده',
            'driver_sheba_number': 'شماره شبا راننده',
            'expected_arrival_date': 'تاریخ پیش‌بینی ورود',
            'waybill_number': 'شماره بارنامه',
            'notes': 'یادداشت',
        }
        widgets = {
            'allocation': forms.Select(attrs={'class': 'form-control'}),
            'vehicle_type': forms.Select(attrs={'class': 'form-control'}),
            'plate_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver': forms.Select(attrs={'class': 'form-control'}),
            'freight_payment_type': forms.TextInput(attrs={'class': 'form-control'}),
            'initial_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'total_freight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'surplus': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'freight_payment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'driver_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'driver_sheba_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expected_arrival_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'text', 'placeholder': '1403/09/15'}),
            'waybill_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.PersonFolder.PersonModel import Person
        from core.AllocationFolder.AllocationModel import Allocation
        
        # فیلدهای اجباری
        self.fields['vehicle_type'].required = True
        
        # حذف فیلد transport_type از فرم (خودکار به inbound تنظیم می‌شود)
        if 'transport_type' in self.fields:
            del self.fields['transport_type']
        
        # Filter purchase orders that are not in draft or completed status
        self.fields['purchase_order'].queryset = Order.objects.filter(
            order_type='purchase'
        ).exclude(
            status__in=[
                Order.STATUS_DRAFT,
                Order.STATUS_COMPLETED
            ]
        ).order_by('-created_at')
        
        # اگر instance موجود است، purchase_order را از allocation تنظیم کن
        if self.instance and self.instance.pk and self.instance.allocation:
            self.fields['purchase_order'].initial = self.instance.allocation.order
        
        # allocation را مخفی کن (از purchase_order استفاده می‌کنیم)
        self.fields['allocation'].widget = forms.HiddenInput()
        self.fields['allocation'].required = False
        
        # تبدیل فیلد driver به text input برای autocomplete
        # یک hidden field برای driver_id اضافه می‌کنیم
        self.fields['driver'].widget = forms.HiddenInput()
        self.fields['driver'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        purchase_order = cleaned_data.get('purchase_order')
        
        if purchase_order:
            # پیدا کردن یا ایجاد Allocation برای این Order
            from core.AllocationFolder.AllocationModel import Allocation
            import uuid
            
            # سعی کن Allocation موجود را پیدا کنی
            allocation = Allocation.objects.filter(order=purchase_order).first()
            
            # اگر Allocation وجود نداشت، یکی بساز
            if not allocation:
                allocation_number = f"ALLOC-{purchase_order.order_number}-{str(uuid.uuid4())[:8]}"
                allocation = Allocation.objects.create(
                    allocation_number=allocation_number,
                    order=purchase_order,
                    allocation_status='planned'
                )
            
            cleaned_data['allocation'] = allocation
        
        return cleaned_data


@login_required
def purchase_transport_list_view(request):
    """صفحه لیست حمل‌های خرید شامل دو جدول: فعال و تکمیل‌شده"""
    audit_logger.info("مشاهده لیست حمل‌های خرید")
    
    # Check task permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_DEFINE_TRANSPORTATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به لیست حمل‌های خرید بدون مجوز - کاربر: {request.user.username}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_for_transport(request.user)
    accessible_person_fields = get_accessible_person_fields_for_transport(request.user)
    accessible_user_fields = get_accessible_user_fields_for_transport(request.user)
    
    try:
        from supply.tables import TransportTable
        
        # دریافت پارامترهای فیلتر و جست‌وجو
        order_number_filter = request.GET.get('order_number', '').strip()
        vehicle_type_filter = request.GET.get('vehicle_type', '').strip()
        transport_type_filter = request.GET.get('transport_type', '').strip()
        status_filter = request.GET.get('status', '').strip()
        created_at_filter = request.GET.get('created_at', '').strip()
        
        # Orders awaiting transport definition (for quick create)
        awaiting_pos = Order.objects.filter(
            status=Order.STATUS_AWAITING_TRANSPORT_DEFINITION
        ).select_related('customer').order_by('-created_at')
        
        # Active transports (not completed) - فقط حمل‌های ورودی
        active_transports = Transport.objects.exclude(
            status__in=[Transport.STATUS_COMPLETED, Transport.STATUS_PAYMENT_DOC_UPLOADED]
        ).filter(
            Q(direction='inbound') | Q(transport_type='inbound')
        ).select_related('allocation', 'allocation__order', 'created_by')
        
        # Completed transports (both old completed status and new payment_doc_uploaded status) - فقط حمل‌های ورودی
        completed_transports = Transport.objects.filter(
            status__in=[Transport.STATUS_COMPLETED, Transport.STATUS_PAYMENT_DOC_UPLOADED]
        ).filter(
            Q(direction='inbound') | Q(transport_type='inbound')
        ).select_related('allocation', 'allocation__order', 'created_by')
        
        # اعمال فیلترها بر روی حمل‌های فعال
        if order_number_filter:
            active_transports = active_transports.filter(
                Q(allocation__order__order_number__icontains=order_number_filter)
            )
        if vehicle_type_filter:
            active_transports = active_transports.filter(vehicle_type=vehicle_type_filter)
        if transport_type_filter:
            active_transports = active_transports.filter(transport_type=transport_type_filter)
        if status_filter:
            active_transports = active_transports.filter(status=status_filter)
        if created_at_filter:
            try:
                from datetime import datetime
                # فرض می‌کنیم تاریخ به فرمت YYYY-MM-DD وارد شده
                date_obj = datetime.strptime(created_at_filter, '%Y-%m-%d').date()
                active_transports = active_transports.filter(created_at__date=date_obj)
            except ValueError:
                pass  # اگر تاریخ نامعتبر بود، فیلتر اعمال نمی‌شود
        
        # اعمال فیلترها بر روی حمل‌های تکمیل‌شده
        if order_number_filter:
            completed_transports = completed_transports.filter(
                Q(allocation__order__order_number__icontains=order_number_filter)
            )
        if vehicle_type_filter:
            completed_transports = completed_transports.filter(vehicle_type=vehicle_type_filter)
        if transport_type_filter:
            completed_transports = completed_transports.filter(transport_type=transport_type_filter)
        if status_filter:
            completed_transports = completed_transports.filter(status=status_filter)
        if created_at_filter:
            try:
                from datetime import datetime
                date_obj = datetime.strptime(created_at_filter, '%Y-%m-%d').date()
                completed_transports = completed_transports.filter(created_at__date=date_obj)
            except ValueError:
                pass
        
        # مرتب‌سازی
        active_transports = active_transports.order_by('-created_at')
        completed_transports = completed_transports.order_by('-created_at')
        
        # Prepare table accessible fields dict
        table_accessible_fields = {
            'transport_number': accessible_transport_fields.get('transport_number', False),
            'purchase_order': (
                accessible_transport_fields.get('purchase_order', False) and
                accessible_po_fields.get('order_number', False)
            ),
            'purchase_order_status': (
                accessible_transport_fields.get('purchase_order', False) and
                accessible_po_fields.get('status', False)
            ),
            'transport_type': accessible_transport_fields.get('transport_type', False),
            'vehicle_type': accessible_transport_fields.get('vehicle_type', False),
            'status': accessible_transport_fields.get('status', False),
            'plate_number': accessible_transport_fields.get('plate_number', False),
            'expected_arrival_date': accessible_transport_fields.get('expected_arrival_date', False),
            'created_at': accessible_transport_fields.get('created_at', False),
        }
        
        # Create tables
        active_table = TransportTable(active_transports, prefix='active-', accessible_fields=table_accessible_fields)
        completed_table = TransportTable(completed_transports, prefix='completed-', accessible_fields=table_accessible_fields)
        
        # Configure pagination
        RequestConfig(request, paginate={'per_page': 15}).configure(active_table)
        RequestConfig(request, paginate={'per_page': 15}).configure(completed_table)
        
        context = {
            'active_table': active_table,
            'completed_table': completed_table,
            'awaiting_pos': awaiting_pos,
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
            'filters': {
                'order_number': order_number_filter,
                'vehicle_type': vehicle_type_filter,
                'transport_type': transport_type_filter,
                'status': status_filter,
                'created_at': created_at_filter,
            },
        }
        return render(request, 'supply_purchase_transport_list.html', context)
    except Exception as e:
        bug_logger.error(f"Purchase transport list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها.')
        from supply.tables import TransportTable
        table_accessible_fields = {
            'transport_number': accessible_transport_fields.get('transport_number', False),
            'purchase_order': False,
            'purchase_order_status': False,
            'transport_type': accessible_transport_fields.get('transport_type', False),
            'vehicle_type': accessible_transport_fields.get('vehicle_type', False),
            'status': accessible_transport_fields.get('status', False),
            'plate_number': accessible_transport_fields.get('plate_number', False),
            'expected_arrival_date': accessible_transport_fields.get('expected_arrival_date', False),
            'created_at': accessible_transport_fields.get('created_at', False),
        }
        active_table = TransportTable([], prefix='active-', accessible_fields=table_accessible_fields)
        completed_table = TransportTable([], prefix='completed-', accessible_fields=table_accessible_fields)
        return render(request, 'supply_purchase_transport_list.html', {
            'active_table': active_table,
            'completed_table': completed_table,
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_person_fields': accessible_person_fields,
            'accessible_user_fields': accessible_user_fields,
        })


@login_required
def create_purchase_transport_view(request):
    """ایجاد حمل جدید برای سفارش خرید"""
    audit_logger.info("ایجاد حمل خرید جدید")
    
    # Check task permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_DEFINE_TRANSPORTATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به ایجاد حمل خرید بدون مجوز - کاربر: {request.user.username}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions (edit permissions for form)
    accessible_transport_fields = {
        'purchase_order': user_can_access_field(request.user, Transport, 'allocation', 'edit'),
        'transport_type': user_can_access_field(request.user, Transport, 'transport_type', 'edit'),
        'vehicle_type': user_can_access_field(request.user, Transport, 'vehicle_type', 'edit'),
        'plate_number': user_can_access_field(request.user, Transport, 'plate_number', 'edit'),
        'driver': user_can_access_field(request.user, Transport, 'driver', 'edit'),
        'freight_payment_type': user_can_access_field(request.user, Transport, 'freight_payment_type', 'edit'),
        'initial_freight': user_can_access_field(request.user, Transport, 'initial_freight', 'edit'),
        'total_freight': user_can_access_field(request.user, Transport, 'total_freight', 'edit'),
        'discount': user_can_access_field(request.user, Transport, 'discount', 'edit'),
        'surplus': user_can_access_field(request.user, Transport, 'surplus', 'edit'),
        'freight_payment': user_can_access_field(request.user, Transport, 'freight_payment', 'edit'),
        'driver_account_number': user_can_access_field(request.user, Transport, 'driver_account_number', 'edit'),
        'driver_sheba_number': user_can_access_field(request.user, Transport, 'driver_sheba_number', 'edit'),
        'expected_arrival_date': user_can_access_field(request.user, Transport, 'expected_arrival_date', 'edit'),
        'actual_arrival_date': user_can_access_field(request.user, Transport, 'actual_arrival_date', 'edit'),
        'loading_date': user_can_access_field(request.user, Transport, 'loading_date', 'edit'),
        'delivery_date': user_can_access_field(request.user, Transport, 'delivery_date', 'edit'),
        'gross_weight': user_can_access_field(request.user, Transport, 'gross_weight', 'edit'),
        'tare_weight': user_can_access_field(request.user, Transport, 'tare_weight', 'edit'),
        'net_weight': user_can_access_field(request.user, Transport, 'net_weight', 'edit'),
        'waybill_number': user_can_access_field(request.user, Transport, 'waybill_number', 'edit'),
        'notes': user_can_access_field(request.user, Transport, 'notes', 'edit'),
    }
    
    # Check if coming from purchase order detail page
    order_number = request.GET.get('order')
    initial_order = None
    if order_number:
        try:
            initial_order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            pass
    
    try:
        if request.method == 'POST':
            form = TransportForm(request.POST)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        pt = form.save(commit=False)
                        pt.created_by = request.user
                        # تنظیم خودکار transport_type و direction به inbound
                        pt.transport_type = 'inbound'
                        pt.direction = 'inbound'
                        # اطمینان از اینکه وضعیت پیش‌فرض draft است
                        if not pt.status:
                            pt.status = Transport.STATUS_DRAFT
                        
                        # تولید خودکار شماره حمل
                        if not pt.transport_number:
                            import uuid
                            from datetime import datetime
                            # تولید شماره حمل به فرمت TRANSPORT-YYYYMMDD-XXXX
                            date_str = datetime.now().strftime('%Y%m%d')
                            unique_id = str(uuid.uuid4())[:4].upper()
                            pt.transport_number = f"TRANSPORT-{date_str}-{unique_id}"
                        
                        pt.save()
                        
                        # تغییر وضعیت از پیش‌نویس به "در انتظار ورود خودرو"
                        pt.status = Transport.STATUS_AWAITING_VEHICLE_ENTRY
                        pt.save()
                        
                        # تغییر وضعیت سفارش از "در انتظار تعریف حمل" به "در انتظار ورود خودرو"
                        if pt.allocation and pt.allocation.order:
                            order = pt.allocation.order
                            if order.status == Order.STATUS_AWAITING_TRANSPORT_DEFINITION:
                                try:
                                    order.transition(Order.STATUS_AWAITING_VEHICLE_ENTRY, user=request.user, note='تعریف حمل انجام شد')
                                    bug_logger.info(f"وضعیت سفارش {order.order_number} از 'در انتظار تعریف حمل' به 'در انتظار ورود خودرو' تغییر کرد")
                                except Exception as order_transition_err:
                                    bug_logger.warning(f"خطا در تغییر وضعیت سفارش {order.order_number}: {order_transition_err}")
                        
                        bug_logger.info(f"حمل جدید ایجاد شد: {pt.transport_number} - وضعیت: {pt.status} - ID: {pt.pk}")
                        
                        # ارسال اعلان به نگهبان
                        try:
                            pt.send_guard_notification()
                            bug_logger.info(f"اعلان نگهبان برای حمل {pt.transport_number} ارسال شد")
                        except Exception as notif_err:
                            bug_logger.warning(f"خطا در ارسال اعلان نگهبان برای حمل {pt.transport_number}: {notif_err}")
                            # این خطا نباید باعث rollback شود
                        
                        order_number = pt.allocation.order.order_number if pt.allocation and pt.allocation.order else 'نامشخص'
                        audit_logger.info(f"حمل جدید ایجاد شد - شماره: {pt.transport_number} - سفارش: {order_number}")
                    
                    messages.success(request, f'حمل {pt.transport_number} ثبت شد و اعلان به نگهبان ارسال شد.')
                    return redirect(reverse('supply:purchase_transport_list'))
                except ValueError as ve:
                    bug_logger.error(f"خطا در ایجاد حمل: {ve}", exc_info=True)
                    messages.error(request, f'خطا در ایجاد حمل: {str(ve)}')
                except Exception as e:
                    bug_logger.error(f"خطا در ایجاد حمل: {e}", exc_info=True)
                    messages.error(request, f'خطا در ایجاد حمل: {str(e)}')
            else:
                bug_logger.warning(f"Purchase transport form invalid: {form.errors}")
                audit_logger.activity(f"فرم نامعتبر برای ایجاد حمل")
        else:
            if initial_order:
                form = TransportForm(initial={'purchase_order': initial_order})
                # Make purchase_order field read-only if coming from order detail
                form.fields['purchase_order'].disabled = True
            else:
                form = TransportForm()
        
        return render(request, 'supply_create_purchase_transport.html', {
            'form': form,
            'initial_order': initial_order,
            'accessible_transport_fields': accessible_transport_fields,
        })
    except Exception as e:
        bug_logger.error(f"Create purchase transport error: {e}")
        messages.error(request, 'خطا در ایجاد حمل.')
        return render(request, 'supply_create_purchase_transport.html', {
            'form': TransportForm(),
            'initial_order': None,
            'accessible_transport_fields': accessible_transport_fields,
        })


@login_required
def purchase_transport_detail_view(request, transport_number):
    """جزئیات حمل خرید"""
    audit_logger.info(f"مشاهده جزئیات حمل خرید {transport_number}")
    from supply.tables import TransportStatusLogTable
    
    # اگر transport_number برابر None است، خطا بده
    if not transport_number or transport_number == 'None':
        messages.error(request, 'شماره حمل نامعتبر است.')
        return redirect(reverse('supply:purchase_transport_list'))
    
    # تلاش برای پیدا کردن حمل با transport_number یا pk
    try:
        if transport_number.isdigit():
            pt = get_object_or_404(
                Transport.objects.select_related('allocation', 'allocation__order', 'driver', 'created_by'),
                pk=int(transport_number)
            )
        else:
            pt = get_object_or_404(
                Transport.objects.select_related('allocation', 'allocation__order', 'driver', 'created_by'),
                transport_number=transport_number
            )
    except (ValueError, Transport.DoesNotExist) as e:
        bug_logger.error(f"خطا در یافتن حمل با شناسه {transport_number}: {e}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect(reverse('supply:purchase_transport_list'))
    # Transport model doesn't have status_logs, so we use empty list for now
    logs = []
    log_table = TransportStatusLogTable(logs)
    RequestConfig(request, paginate=False).configure(log_table)
    
    # لیست تمام وضعیت‌های ممکن
    next_status_choices = pt.STATUS_CHOICES
    
    return render(request, 'supply_purchase_transport_detail.html', {
        'pt': pt,
        'logs': logs,
        'log_table': log_table,
        'next_status_choices': next_status_choices,
    })


@login_required
def edit_purchase_transport_view(request, transport_number):
    """ویرایش حمل خرید"""
    audit_logger.info(f"ویرایش حمل خرید {transport_number}")
    pt = get_object_or_404(Transport, transport_number=transport_number)
    
    if pt.status in [Transport.STATUS_COMPLETED, Transport.STATUS_PAYMENT_DOC_UPLOADED]:
        messages.error(request, 'حمل تکمیل شده قابل ویرایش نیست.')
        return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
    
    try:
        if request.method == 'POST':
            form = TransportForm(request.POST, instance=pt)
            if form.is_valid():
                form.save()
                messages.success(request, 'حمل ویرایش شد.')
                return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
            else:
                bug_logger.warning(f"Edit transport invalid form={form.errors}")
        else:
            form = TransportForm(instance=pt)
        return render(request, 'supply_edit_purchase_transport.html', {
            'form': form,
            'pt': pt,
        })
    except Exception as e:
        bug_logger.error(f"Edit purchase transport error: {e}")
        messages.error(request, 'خطا در ویرایش حمل.')
        return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))


@login_required
def delete_purchase_transport_view(request, transport_number):
    """حذف حمل خرید (فقط پیش‌نویس)"""
    audit_logger.activity(f"حذف حمل خرید {transport_number}")
    pt = get_object_or_404(Transport, transport_number=transport_number)
    
    if not pt.can_delete():
        messages.error(request, 'حذف فقط در وضعیت پیش‌نویس مجاز است.')
        return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
    
    try:
        pt.delete()
        messages.success(request, 'حمل حذف شد.')
    except Exception as e:
        bug_logger.error(f"Delete purchase transport error: {e}")
        messages.error(request, 'خطا در حذف حمل.')
    return redirect(reverse('supply:purchase_transport_list'))


@login_required
def transition_purchase_transport_status_view(request, transport_number, new_status):
    """تغییر وضعیت حمل خرید"""
    audit_logger.activity(f"درخواست تغییر وضعیت حمل خرید {transport_number} -> {new_status}")
    pt = get_object_or_404(Transport, transport_number=transport_number)
    
    try:
        # بررسی معتبر بودن وضعیت
        valid_statuses = [code for code, label in Transport.STATUS_CHOICES]
        if new_status not in valid_statuses:
            messages.error(request, 'وضعیت انتخاب شده نامعتبر است.')
            return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))
        
        pt.status = new_status
        pt.save()
        messages.success(request, 'وضعیت حمل بروزرسانی شد.')
    except Exception as e:
        bug_logger.error(f"Transition purchase transport error: {e}")
        messages.error(request, 'خطای تغییر وضعیت حمل.')
    
    return redirect(reverse('supply:purchase_transport_detail', kwargs={'transport_number': transport_number}))


@login_required
def get_purchase_order_info_api(request, order_number):
    """API endpoint برای دریافت اطلاعات سفارش خرید"""
    from django.http import JsonResponse
    
    try:
        po = get_object_or_404(Order, order_number=order_number)
        materials_data = []
        
        for material in po.materials.select_related('raw_material').all():
            materials_data.append({
                'name': material.raw_material.name,
                'quantity': str(material.quantity),
                'unit': material.unit,
            })
        
        data = {
            'order_date': po.created_at.strftime('%Y/%m/%d'),
            'supplier': po.supplier.name if po.supplier else '',
            'materials': materials_data,
        }
        
        return JsonResponse(data)
    except Exception as e:
        bug_logger.error(f"Get purchase order info API error: {e}")
        return JsonResponse({'error': 'خطا در دریافت اطلاعات سفارش'}, status=400)


@login_required
def driver_search_api(request):
    """API برای جستجوی راننده بر اساس نام یا شماره تلفن"""
    from django.http import JsonResponse
    
    query = request.GET.get('q', '').strip()
    driver_id = request.GET.get('id', '').strip()
    
    # اگر id داده شده، فقط آن راننده را برگردان
    if driver_id:
        try:
            driver = Person.objects.filter(pk=int(driver_id), type='driver').first()
            if driver:
                return JsonResponse({
                    'results': [{
                        'id': driver.pk,
                        'text': f"{driver.name or 'بدون نام'} - {driver.phone_number or 'بدون تلفن'}",
                        'name': driver.name or '',
                        'phone': driver.phone_number or '',
                        'national_id': driver.national_id or '',
                    }]
                })
            else:
                return JsonResponse({'results': []})
        except (ValueError, TypeError):
            return JsonResponse({'results': []})
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    try:
        drivers = Person.objects.filter(
            type='driver'
        ).filter(
            Q(name__icontains=query) | Q(phone_number__icontains=query) | Q(national_id__icontains=query)
        ).order_by('name')[:10]
        
        results = []
        for driver in drivers:
            results.append({
                'id': driver.pk,
                'text': f"{driver.name or 'بدون نام'} - {driver.phone_number or 'بدون تلفن'}",
                'name': driver.name or '',
                'phone': driver.phone_number or '',
                'national_id': driver.national_id or '',
            })
        
        return JsonResponse({'results': results})
    except Exception as e:
        bug_logger.error(f"Driver search API error: {e}")
        return JsonResponse({'error': 'خطا در جستجوی راننده'}, status=400)


@login_required
def create_driver_api(request):
    """API برای ایجاد راننده جدید"""
    from django.http import JsonResponse
    from django.db import transaction
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        national_id = request.POST.get('national_id', '').strip()
        
        if not name or not phone:
            return JsonResponse({'error': 'نام و شماره تلفن اجباری است'}, status=400)
        
        # بررسی تکراری نبودن
        existing = Person.objects.filter(
            Q(phone_number=phone) | Q(national_id=national_id)
        ).filter(type='driver').first()
        
        if existing:
            return JsonResponse({
                'error': 'راننده با این شماره تلفن یا کد ملی قبلاً ثبت شده است',
                'driver': {
                    'id': existing.pk,
                    'name': existing.name,
                    'phone': existing.phone_number,
                    'national_id': existing.national_id,
                }
            }, status=400)
        
        with transaction.atomic():
            driver = Person.objects.create(
                name=name,
                phone_number=phone,
                national_id=national_id if national_id else None,
                type='driver'
            )
            
            audit_logger.info(f"راننده جدید ایجاد شد - نام: {driver.name} - تلفن: {driver.phone_number} - توسط: {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'driver': {
                    'id': driver.pk,
                    'name': driver.name,
                    'phone': driver.phone_number,
                    'national_id': driver.national_id or '',
                    'text': f"{driver.name} - {driver.phone_number}",
                }
            })
    except Exception as e:
        bug_logger.error(f"Create driver API error: {e}", exc_info=True)
        return JsonResponse({'error': f'خطا در ایجاد راننده: {str(e)}'}, status=500)
