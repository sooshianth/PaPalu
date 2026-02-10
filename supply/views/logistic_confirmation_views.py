from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django import forms
from django.forms import ModelForm
from django_tables2 import RequestConfig
from django.utils import timezone
import logging
from core.logging_levels import *

from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
from core.OrderFolder.OrderModel import Order
from core.OrderFolder.OrderItemModel import OrderItem

from core.PersonFolder.PersonModel import Person
from core.RBACModel import user_has_task, TaskChoices, user_can_access_field
from django.contrib.auth import get_user_model
from supply.tables import LogisticConfirmationTable

User = get_user_model()
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


# ==================== Field Access Helper Functions ====================

def get_accessible_purchase_transport_fields_logistic(user):
    """Check field access for Transport model (view permission)"""
    # برای سوپریوزر، همه فیلدها قابل دسترسی هستند
    if user.is_superuser:
        return {
            'transport_number': True,
            'purchase_order': True,
            'status': True,
            'vehicle_type': True,
            'plate_number': True,
            'driver': True,
        'gross_weight': True,
        'tare_weight': True,
        'net_weight': True,
        'waybill_weight': True,
        'freight_payment_type': True,
            'initial_freight': True,
            'total_freight': True,
            'discount': True,
            'surplus': True,
            'freight_payment': True,
            'delivery_date': True,
            'created_at': True,
        }
    
    return {
        'transport_number': user_can_access_field(user, Transport, 'transport_number', 'view'),
        'purchase_order': user_can_access_field(user, Transport, 'purchase_order', 'view'),
        'status': user_can_access_field(user, Transport, 'status', 'view'),
        'vehicle_type': user_can_access_field(user, Transport, 'vehicle_type', 'view'),
        'plate_number': user_can_access_field(user, Transport, 'plate_number', 'view'),
        'driver': user_can_access_field(user, Transport, 'driver', 'view'),
        'gross_weight': user_can_access_field(user, Transport, 'gross_weight', 'view'),
        'tare_weight': user_can_access_field(user, Transport, 'tare_weight', 'view'),
        'net_weight': user_can_access_field(user, Transport, 'net_weight', 'view'),
        'waybill_weight': user_can_access_field(user, Transport, 'waybill_weight', 'view'),
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'view'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'view'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'view'),
        'discount': user_can_access_field(user, Transport, 'discount', 'view'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'view'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'view'),
        'delivery_date': user_can_access_field(user, Transport, 'delivery_date', 'view'),
        'created_at': user_can_access_field(user, Transport, 'created_at', 'view'),
    }


def get_accessible_purchase_transport_fields_logistic_edit(user):
    """Check field access for Transport model (edit permission)"""
    return {
        'freight_payment_type': user_can_access_field(user, Transport, 'freight_payment_type', 'edit'),
        'initial_freight': user_can_access_field(user, Transport, 'initial_freight', 'edit'),
        'total_freight': user_can_access_field(user, Transport, 'total_freight', 'edit'),
        'discount': user_can_access_field(user, Transport, 'discount', 'edit'),
        'surplus': user_can_access_field(user, Transport, 'surplus', 'edit'),
        'freight_payment': user_can_access_field(user, Transport, 'freight_payment', 'edit'),
    }


def get_accessible_procurement_purchase_order_fields_logistic(user):
    """Check field access for ProcurementPurchaseOrder model (for logistic views)"""
    return {
        'order_number': user_can_access_field(user, Order, 'order_number', 'view'),
        'status': user_can_access_field(user, Order, 'status', 'view'),
        'supplier': user_can_access_field(user, Order, 'supplier', 'view'),
        'materials': user_can_access_field(user, Order, 'materials', 'view'),
        'created_at': user_can_access_field(user, Order, 'created_at', 'view'),
    }


def get_accessible_person_fields_logistic(user):
    """Check field access for Person model (for logistic views)"""
    return {
        'name': user_can_access_field(user, Person, 'name', 'view'),
        'phone_number': user_can_access_field(user, Person, 'phone_number', 'view'),
        'type': user_can_access_field(user, Person, 'type', 'view'),
    }

# ==================== End Field Access Helper Functions ====================


class LogisticConfirmationForm(ModelForm):
    """فرم تایید لجستیک برای تکمیل اطلاعات مالی حمل"""
    
    class Meta:
        model = Transport
        fields = [
            'freight_payment_type',
            'initial_freight',
            'total_freight',
            'discount',
            'surplus',
            'freight_payment',
        ]
        labels = {
            'freight_payment_type': 'نوع کرایه',
            'initial_freight': 'کرایه اولیه',
            'total_freight': 'کرایه کل',
            'discount': 'تخفیف',
            'surplus': 'مازاد',
            'freight_payment': 'کرایه پرداختی',
        }
        widgets = {
            'freight_payment_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'نقدی، اعتباری و غیره',
                'required': True
            }),
            'initial_freight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'total_freight': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'surplus': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
            'freight_payment': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'required': True
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields required
        for field_name in self.fields:
            self.fields[field_name].required = True


@login_required
def logistic_confirmation_list_view(request):
    """صفحه لیست حمل‌های در انتظار تایید لجستیک"""
    audit_logger.info(f"دسترسی به لیست تایید لجستیک")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_LOGISTIC_CONFIRMATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به لیست تایید لجستیک بدون مجوز")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_logistic(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_logistic(request.user)
    accessible_person_fields = get_accessible_person_fields_logistic(request.user)
    
    try:
        # Get transports awaiting settlement (status = awaiting_settlement)
        transports = Transport.objects.filter(
            status=Transport.STATUS_AWAITING_SETTLEMENT
        ).select_related(
            'allocation__order',
            'allocation__order__customer',
            'driver'
        ).order_by('-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های در انتظار تسویه: {transports.count()}")
        
        # Create table
        table = LogisticConfirmationTable(transports, accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_person_fields': accessible_person_fields,
        }
        
        return render(request, 'logistic_confirmation_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در نمایش لیست تایید لجستیک: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها')
        return redirect('supply:home')


@login_required
def logistic_confirmation_detail_view(request, transport_number):
    """صفحه جزئیات و تایید لجستیک برای یک حمل"""
    audit_logger.info(f"دسترسی به جزئیات تایید لجستیک - حمل {transport_number}")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_LOGISTIC_CONFIRMATION.value):
        audit_logger.activity(f"تلاش برای دسترسی به تایید لجستیک بدون مجوز - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_logistic_edit(request.user)
    accessible_transport_fields_view = get_accessible_purchase_transport_fields_logistic(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_logistic(request.user)
    accessible_person_fields = get_accessible_person_fields_logistic(request.user)
    
    try:
        bug_logger.info(f"شروع بارگذاری جزئیات تایید لجستیک - transport_number: {transport_number}")
        
        # Support both transport_number and numeric pk as identifier
        transport = None
        if transport_number and str(transport_number).isdigit():
            bug_logger.debug(f"Fetching transport by pk: {transport_number}")
            try:
                transport = Transport.objects.select_related(
                    'allocation__order',
                    'allocation__order__customer',
                    'driver',
                    'freight_payment_document_uploaded_by'
                ).get(pk=int(transport_number))
                bug_logger.info(f"حمل با pk={transport_number} پیدا شد - transport_number: {transport.transport_number}, status: {transport.status}")
            except Transport.DoesNotExist:
                bug_logger.error(f"حمل با pk={transport_number} پیدا نشد")
                messages.error(request, 'حمل مورد نظر یافت نشد.')
                return redirect('supply:logistic_confirmation_list')
        else:
            bug_logger.debug(f"Fetching transport by transport_number: {transport_number}")
            try:
                transport = Transport.objects.select_related(
                    'allocation__order',
                    'allocation__order__customer',
                    'driver',
                    'freight_payment_document_uploaded_by'
                ).get(transport_number=transport_number)
                bug_logger.info(f"حمل با transport_number={transport_number} پیدا شد - pk: {transport.pk}, status: {transport.status}")
            except Transport.DoesNotExist:
                bug_logger.error(f"حمل با transport_number={transport_number} پیدا نشد")
                messages.error(request, 'حمل مورد نظر یافت نشد.')
                return redirect('supply:logistic_confirmation_list')
        
        if not transport:
            bug_logger.error(f"transport None است - transport_number: {transport_number}")
            messages.error(request, 'حمل مورد نظر یافت نشد.')
            return redirect('supply:logistic_confirmation_list')
        
        # Check if transport is in awaiting_settlement status
        bug_logger.info(f"بررسی وضعیت حمل - status: {transport.status}, expected: {Transport.STATUS_AWAITING_SETTLEMENT}")
        if transport.status != Transport.STATUS_AWAITING_SETTLEMENT:
            audit_logger.warning(
                f"تلاش برای تایید لجستیک در وضعیت نامناسب - حمل {transport_number} - "
                f"وضعیت: {transport.get_status_display()}"
            )
            messages.warning(request, f'این حمل در وضعیت مناسب برای تایید لجستیک نیست. وضعیت فعلی: {transport.get_status_display()}')
            return redirect('supply:logistic_confirmation_list')
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            # اگر action = 'reject' باشد، حمل را رد می‌کنیم
            if action == 'reject':
                try:
                    from django.db import transaction
                    with transaction.atomic():
                        # تغییر وضعیت به rejected
                        transport.status = Transport.STATUS_REJECTED
                        transport.save()
                        
                        # Log rejection
                        audit_logger.info(
                            f"ارجاع حمل به مدیریت توسط لجستیک - حمل {transport_number} | "
                            f"کاربر: {request.user.username} | "
                            f"زمان: {timezone.now()}"
                        )
                        
                        bug_logger.info(f"حمل {transport_number} به مدیریت ارجاع داده شد توسط کاربر {request.user.username}")
                        
                    messages.warning(request, 'حمل به مدیریت ارجاع داده شد.')
                    return redirect('supply:logistic_confirmation_list')
                except Exception as e:
                    bug_logger.error(f"خطا در رد حمل - حمل {transport_number}: {str(e)}", exc_info=True)
                    messages.error(request, 'خطا در رد حمل')
                    return redirect('supply:logistic_confirmation_list')
            
            # تأیید نهایی بدون نیاز به فرم - همه فیلدها فقط خواندنی هستند
            try:
                from django.db import transaction
                with transaction.atomic():
                    # تنظیم تایید لجستیک
                    transport.logistic_confirmed = True
                    
                    # اگر سند پرداخت هم بارگذاری شده است، وضعیت را به completed ببر
                    # در غیر این صورت، وضعیت را به awaiting_payment_doc ببر
                    if transport.payment_doc_uploaded:
                        # هر دو شرط برقرار است -> تکمیل شده
                        transport.status = Transport.STATUS_COMPLETED
                        bug_logger.info(f"حمل {transport_number} تکمیل شد - تایید لجستیک و بارگذاری سند هر دو انجام شده است")
                    else:
                        # فقط تایید لجستیک انجام شده -> در انتظار بارگذاری سند
                        transport.status = Transport.STATUS_AWAITING_PAYMENT_DOC
                    
                    transport.save()
                    
                    # بررسی وضعیت سفارش خرید
                    po = transport.allocation.order if transport.allocation else None
                    if po and po.order_type == 'purchase':
                        # بررسی اینکه آیا تمام حمل‌های سفارش تکمیل شده‌اند
                        all_transports = Transport.objects.filter(allocation__order=po)
                        all_completed = not all_transports.exclude(
                            status=Transport.STATUS_COMPLETED
                        ).exists()
                        
                        # بررسی اینکه آیا تمام وزن سفارش تخصیص یافته است
                        remaining_weight = po.get_remaining_weight()
                        
                        # اگر تمام وزن تخصیص یافته و تمام حمل‌ها تکمیل شده‌اند، سفارش را تکمیل کن
                        if remaining_weight <= 0 and all_completed:
                            if po.status != Order.STATUS_COMPLETED:
                                try:
                                    po.transition(Order.STATUS_COMPLETED, user=request.user, note='تمام حمل‌های سفارش تکمیل شدند و تمام وزن تخصیص یافت.')
                                    bug_logger.info(f"وضعیت سفارش {po.order_number} به 'تکمیل شده' تغییر یافت - تمام حمل‌ها تکمیل شدند")
                                    audit_logger.info(f"سفارش {po.order_number} به صورت خودکار تکمیل شد - تمام حمل‌ها تکمیل شدند")
                                except Exception as order_transition_err:
                                    bug_logger.warning(f"خطا در تغییر وضعیت سفارش {po.order_number} به تکمیل شده: {order_transition_err}")
                        elif all_completed:
                            # اگر تمام حمل‌ها تکمیل شده‌اند اما وزن هنوز تخصیص نیافته، به awaiting_final_settlement ببر
                            if po.status == Order.STATUS_AWAITING_WAREHOUSE_RECONCILIATION:
                                po.transition(Order.STATUS_AWAITING_FINAL_SETTLEMENT, user=request.user, note=f"تمام حمل‌های سفارش تکمیل شدند.")
                                bug_logger.info(f"وضعیت سفارش {po.order_number} به 'در انتظار تسویه نهایی' تغییر یافت")
                                audit_logger.info(f"وضعیت سفارش {po.order_number} به دنبال تسویه همه حمل‌ها به‌روزرسانی شد")
                    
                    # Log successful completion
                    audit_logger.info(
                        f"تایید نهایی لجستیک - حمل {transport_number} | "
                        f"کاربر: {request.user.username} | "
                        f"زمان: {timezone.now()} | "
                        f"وضعیت جدید: {transport.status}"
                    )
                    
                    bug_logger.info(f"تایید لجستیک موفق - حمل {transport_number} - وضعیت: {transport.status}")
                    
                if transport.status == Transport.STATUS_COMPLETED:
                    messages.success(request, 'تایید نهایی لجستیک با موفقیت انجام شد. حمل تکمیل شد (سند پرداخت قبلاً بارگذاری شده بود).')
                else:
                    messages.success(request, 'تایید نهایی لجستیک با موفقیت انجام شد و وضعیت به "در انتظار بارگذاری اسناد پرداخت کرایه" تغییر یافت.')
                return redirect('supply:logistic_confirmation_list')
                    
            except ValueError as ve:
                bug_logger.warning(f"خطای تغییر وضعیت در تایید لجستیک - حمل {transport_number}: {str(ve)}")
                messages.error(request, f'خطا در تغییر وضعیت: {str(ve)}')
            except Exception as e:
                bug_logger.error(f"خطا در تایید لجستیک - حمل {transport_number}: {str(e)}", exc_info=True)
                messages.error(request, 'خطا در ثبت تایید لجستیک')
        
        # آماده‌سازی context
        try:
            po = transport.allocation.order if transport.allocation else None
            bug_logger.info(f"آماده‌سازی context - transport: {transport.transport_number}, order: {po.order_number if po else 'None'}")
            
            # Pre-fetch و فیلتر order_items برای جلوگیری از خطاهای Decimal
            # استفاده از defer() برای جلوگیری از بارگذاری فیلدهای Decimal مشکل‌دار
            valid_order_items = []
            if po:
                try:
                    from decimal import Decimal, InvalidOperation
                    
                    # استفاده از defer() برای بارگذاری نکردن فیلدهای Decimal
                    # فقط فیلدهای مورد نیاز را load می‌کنیم
                    all_items = po.order_items.filter(
                        raw_material__isnull=False
                    ).select_related('raw_material').defer(
                        'quantity', 'unit_price', 'discount', 'additional_charges', 
                        'vat_percent', 'freight_cost', 'total_purchase_cost', 
                        'bag_weight', 'conversion_rate'
                    )
                    
                    # حالا می‌توانیم items را iterate کنیم بدون اینکه Decimal fields load شوند
                    for item in all_items:
                        if item.raw_material:
                            valid_order_items.append(item)
                    
                    bug_logger.info(f"تعداد order_items معتبر: {len(valid_order_items)}")
                except Exception as items_err:
                    bug_logger.error(f"خطا در بارگذاری order_items: {items_err}", exc_info=True)
                    # Fallback: استفاده از values() برای گرفتن فقط raw_material
                    try:
                        items_data = po.order_items.filter(
                            raw_material__isnull=False
                        ).values('id', 'raw_material__name', 'raw_material_id')
                        
                        # ساخت objects ساده برای template
                        class SimpleOrderItem:
                            def __init__(self, item_id, raw_material_name, raw_material_id):
                                self.id = item_id
                                self.raw_material_id = raw_material_id
                                self.raw_material = type('RawMaterial', (), {'name': raw_material_name})() if raw_material_name else None
                        
                        for item_data in items_data:
                            valid_order_items.append(SimpleOrderItem(
                                item_data['id'],
                                item_data['raw_material__name'],
                                item_data['raw_material_id']
                            ))
                        
                        bug_logger.info(f"تعداد order_items (fallback با values): {len(valid_order_items)}")
                    except Exception as fallback_err:
                        bug_logger.error(f"خطا در fallback method: {fallback_err}", exc_info=True)
            
            # محاسبه اختلاف وزن بارنامه و وزن خالص
            weight_discrepancy = None
            weight_discrepancy_percent = None
            has_weight_discrepancy = False
            
            if transport.waybill_weight and transport.net_weight:
                weight_discrepancy = abs(transport.net_weight - transport.waybill_weight)
                if transport.waybill_weight > 0:
                    weight_discrepancy_percent = (weight_discrepancy / transport.waybill_weight) * 100
                    # اگر اختلاف بیشتر از 5% باشد
                    if weight_discrepancy_percent > 5:
                        has_weight_discrepancy = True
            
            # دریافت اطلاعات RawMaterialInfo برای این حمل
            raw_material_infos = RawMaterialInfo.objects.filter(
                transport=transport
            ).select_related('order_item', 'raw_material', 'order_item__raw_material')
            
            # ساخت لیست مواد اولیه با اطلاعات وزن
            material_weights = []
            from decimal import Decimal
            total_allocated = Decimal('0')
            total_net_weight = Decimal('0')
            materials_with_high_discrepancy = []
            has_material_weight_discrepancy = False
            for rmi in raw_material_infos:
                allocated = Decimal(str(rmi.allocated_quantity)) if rmi.allocated_quantity else Decimal('0')
                net_weight = Decimal(str(rmi.net_weight)) if rmi.net_weight else Decimal('0')
                diff = net_weight - allocated
                diff_percent = Decimal('0')
                if allocated > 0:
                    diff_percent = abs((diff / allocated) * 100)
                
                # بررسی اینکه آیا اختلاف بیشتر از 10% است
                if diff_percent > 10:
                    has_material_weight_discrepancy = True
                    materials_with_high_discrepancy.append({
                        'raw_material': rmi.raw_material,
                        'allocated_quantity': allocated,
                        'net_weight': net_weight,
                        'difference': diff,
                        'diff_percent': diff_percent,
                    })
                
                material_weights.append({
                    'raw_material': rmi.raw_material,
                    'order_item': rmi.order_item,
                    'allocated_quantity': allocated,  # وزن تخصیص یافته برای این حمل
                    'net_weight': net_weight,  # وزن خالص از تخلیه
                    'difference': diff,
                    'diff_percent': diff_percent,  # درصد اختلاف
                })
                
                total_allocated += allocated
                total_net_weight += net_weight
            
            # محاسبه وزن خالص کل از RawMaterialInfo
            calculated_total_net_weight = transport.get_total_net_weight_from_materials()
            total_difference = total_net_weight - total_allocated
            
            context = {
                'transport': transport,
                'purchase_order': po,
                'order_items': valid_order_items,  # ارسال لیست فیلتر شده به template
                'material_weights': material_weights,  # اطلاعات وزن مواد اولیه
                'total_allocated': total_allocated,
                'total_net_weight': total_net_weight,
                'total_difference': total_difference,
                'calculated_total_net_weight': Decimal(str(calculated_total_net_weight)) if calculated_total_net_weight is not None else Decimal('0'),
                'materials_with_high_discrepancy': materials_with_high_discrepancy,  # مواد اولیه با اختلاف بیشتر از 10%
                'has_material_weight_discrepancy': has_material_weight_discrepancy,  # آیا اختلاف وزن ماده اولیه وجود دارد؟
                'accessible_transport_fields': accessible_transport_fields_view,
                'accessible_po_fields': accessible_po_fields,
                'accessible_person_fields': accessible_person_fields,
                'weight_discrepancy': weight_discrepancy,
                'weight_discrepancy_percent': weight_discrepancy_percent,
                'has_weight_discrepancy': has_weight_discrepancy,
            }
            
            bug_logger.info(f"رندر کردن template - logistic_confirmation_detail.html")
            return render(request, 'logistic_confirmation_detail.html', context)
        except Exception as context_err:
            bug_logger.error(f"خطا در آماده‌سازی context - حمل {transport_number}: {str(context_err)}", exc_info=True)
            messages.error(request, f'خطا در آماده‌سازی داده‌ها: {str(context_err)}')
            return redirect('supply:logistic_confirmation_list')
        
    except Transport.DoesNotExist:
        audit_logger.alert(f"تلاش برای دسترسی به حمل ناموجود - حمل {transport_number}")
        bug_logger.error(f"Transport.DoesNotExist - transport_number: {transport_number}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect('supply:logistic_confirmation_list')
    except Exception as e:
        bug_logger.error(f"خطا در نمایش جزئیات تایید لجستیک - حمل {transport_number}: {str(e)}", exc_info=True)
        audit_logger.error(f"خطا در نمایش جزئیات تایید لجستیک - حمل {transport_number}: {str(e)}")
        messages.error(request, f'خطا در بارگذاری جزئیات حمل: {str(e)}')
        return redirect('supply:logistic_confirmation_list')


@login_required
def rejected_transports_list_view(request):
    """صفحه لیست حمل‌های ارجاع به مدیریت"""
    audit_logger.info(f"دسترسی به لیست حمل‌های ارجاع به مدیریت")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_VIEW_REJECTED_TRANSPORTS.value):
        audit_logger.activity(f"تلاش برای دسترسی به لیست حمل‌های ارجاع به مدیریت بدون مجوز")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_logistic(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_logistic(request.user)
    accessible_person_fields = get_accessible_person_fields_logistic(request.user)
    
    try:
        # Get rejected transports
        transports = Transport.objects.filter(
            status=Transport.STATUS_REJECTED
        ).select_related(
            'allocation__order',
            'allocation__order__customer',
            'driver'
        ).order_by('-created_at')
        
        bug_logger.debug(f"تعداد حمل‌های ارجاع به مدیریت: {transports.count()}")
        
        # Create table
        table = LogisticConfirmationTable(transports, accessible_fields=accessible_transport_fields)
        RequestConfig(request, paginate={'per_page': 15}).configure(table)
        
        context = {
            'table': table,
            'total_count': transports.count(),
            'accessible_transport_fields': accessible_transport_fields,
            'accessible_po_fields': accessible_po_fields,
            'accessible_person_fields': accessible_person_fields,
        }
        
        return render(request, 'rejected_transports_list.html', context)
        
    except Exception as e:
        bug_logger.error(f"خطا در نمایش لیست حمل‌های ارجاع به مدیریت: {str(e)}", exc_info=True)
        messages.error(request, 'خطا در بارگذاری لیست حمل‌ها')
        return redirect('supply:logistic_confirmation_list')


@login_required
def rejected_transport_detail_view(request, transport_number):
    """صفحه جزئیات حمل ارجاع به مدیریت"""
    audit_logger.info(f"دسترسی به جزئیات حمل ارجاع به مدیریت - حمل {transport_number}")
    
    # Check permission
    if not user_has_task(request.user, TaskChoices.SUPPLY_VIEW_REJECTED_TRANSPORTS.value):
        audit_logger.activity(f"تلاش برای دسترسی به جزئیات حمل ارجاع به مدیریت بدون مجوز - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # Get field access permissions
    accessible_transport_fields = get_accessible_purchase_transport_fields_logistic(request.user)
    accessible_po_fields = get_accessible_procurement_purchase_order_fields_logistic(request.user)
    accessible_person_fields = get_accessible_person_fields_logistic(request.user)
    
    try:
        bug_logger.info(f"شروع بارگذاری جزئیات حمل ارجاع به مدیریت - transport_number: {transport_number}")
        
        # Support both transport_number and numeric pk as identifier
        transport = None
        if transport_number and str(transport_number).isdigit():
            bug_logger.debug(f"Fetching transport by pk: {transport_number}")
            try:
                transport = Transport.objects.select_related(
                    'allocation__order',
                    'allocation__order__customer',
                    'driver',
                    'freight_payment_document_uploaded_by'
                ).get(pk=int(transport_number))
                bug_logger.info(f"حمل با pk={transport_number} پیدا شد - transport_number: {transport.transport_number}, status: {transport.status}")
            except Transport.DoesNotExist:
                bug_logger.error(f"حمل با pk={transport_number} پیدا نشد")
                messages.error(request, 'حمل مورد نظر یافت نشد.')
                return redirect('supply:rejected_transports_list')
        else:
            bug_logger.debug(f"Fetching transport by transport_number: {transport_number}")
            try:
                transport = Transport.objects.select_related(
                    'allocation__order',
                    'allocation__order__customer',
                    'driver'
                ).get(transport_number=transport_number)
                bug_logger.info(f"حمل با transport_number={transport_number} پیدا شد - pk: {transport.pk}, status: {transport.status}")
            except Transport.DoesNotExist:
                bug_logger.error(f"حمل با transport_number={transport_number} پیدا نشد")
                messages.error(request, 'حمل مورد نظر یافت نشد.')
                return redirect('supply:rejected_transports_list')
        
        if not transport:
            bug_logger.error(f"transport None است - transport_number: {transport_number}")
            messages.error(request, 'حمل مورد نظر یافت نشد.')
            return redirect('supply:rejected_transports_list')
        
        # Check if transport is in rejected status
        bug_logger.info(f"بررسی وضعیت حمل - status: {transport.status}, expected: {Transport.STATUS_REJECTED}")
        if transport.status != Transport.STATUS_REJECTED:
            audit_logger.warning(
                f"تلاش برای مشاهده جزئیات حمل ارجاع به مدیریت در وضعیت نامناسب - حمل {transport_number} - "
                f"وضعیت: {transport.get_status_display()}"
            )
            messages.warning(request, f'این حمل در وضعیت ارجاع به مدیریت نیست. وضعیت فعلی: {transport.get_status_display()}')
            return redirect('supply:rejected_transports_list')
        
        # مدیریت تایید توسط مدیر (POST)
        if request.method == 'POST' and request.POST.get('action') == 'approve':
            from django.db import transaction
            try:
                with transaction.atomic():
                    transport.logistic_confirmed = True
                    if transport.payment_doc_uploaded:
                        transport.status = Transport.STATUS_COMPLETED
                        bug_logger.info(f"حمل {transport_number} تکمیل شد - تایید مدیر و بارگذاری سند هر دو انجام شده است")
                    else:
                        transport.status = Transport.STATUS_AWAITING_PAYMENT_DOC
                    transport.save()
                    po = transport.allocation.order if transport.allocation else None
                    if po and po.order_type == 'purchase':
                        all_transports = Transport.objects.filter(allocation__order=po)
                        all_completed = not all_transports.exclude(
                            status=Transport.STATUS_COMPLETED
                        ).exists()
                        remaining_weight = po.get_remaining_weight()
                        if remaining_weight <= 0 and all_completed:
                            if po.status != Order.STATUS_COMPLETED:
                                try:
                                    po.transition(Order.STATUS_COMPLETED, user=request.user, note='تمام حمل‌های سفارش تکمیل شدند و تمام وزن تخصیص یافت.')
                                    bug_logger.info(f"وضعیت سفارش {po.order_number} به 'تکمیل شده' تغییر یافت - تمام حمل‌ها تکمیل شدند")
                                except Exception as order_transition_err:
                                    bug_logger.warning(f"خطا در تغییر وضعیت سفارش {po.order_number}: {order_transition_err}")
                        elif all_completed and po.status == Order.STATUS_AWAITING_WAREHOUSE_RECONCILIATION:
                            try:
                                po.transition(Order.STATUS_AWAITING_FINAL_SETTLEMENT, user=request.user, note='تمام حمل‌های سفارش تکمیل شدند.')
                            except Exception:
                                pass
                    audit_logger.info(
                        f"تایید مدیر - حمل {transport_number} | کاربر: {request.user.username} | زمان: {timezone.now()} | وضعیت جدید: {transport.status}"
                    )
                    bug_logger.info(f"تایید مدیر موفق - حمل {transport_number} - وضعیت: {transport.status}")
                if transport.status == Transport.STATUS_COMPLETED:
                    messages.success(request, 'تایید مدیر با موفقیت انجام شد. حمل تکمیل شد.')
                else:
                    messages.success(request, 'تایید مدیر با موفقیت انجام شد. وضعیت به «در انتظار بارگذاری اسناد پرداخت کرایه» تغییر یافت.')
                return redirect('supply:rejected_transports_list')
            except Exception as e:
                bug_logger.error(f"خطا در تایید مدیر - حمل {transport_number}: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در ثبت تایید: {str(e)}')
        
        # آماده‌سازی context
        try:
            po = transport.allocation.order if transport.allocation else None
            bug_logger.info(f"آماده‌سازی context - transport: {transport.transport_number}, order: {po.order_number if po else 'None'}")
            
            # Pre-fetch و فیلتر order_items
            valid_order_items = []
            if po:
                try:
                    all_items = po.order_items.filter(
                        raw_material__isnull=False
                    ).select_related('raw_material').defer(
                        'quantity', 'unit_price', 'discount', 'additional_charges', 
                        'vat_percent', 'freight_cost', 'total_purchase_cost', 
                        'bag_weight', 'conversion_rate'
                    )
                    
                    for item in all_items:
                        if item.raw_material:
                            valid_order_items.append(item)
                    
                    bug_logger.info(f"تعداد order_items معتبر: {len(valid_order_items)}")
                except Exception as items_err:
                    bug_logger.error(f"خطا در بارگذاری order_items: {items_err}", exc_info=True)
                    try:
                        items_data = po.order_items.filter(
                            raw_material__isnull=False
                        ).values('id', 'raw_material__name', 'raw_material_id')
                        
                        class SimpleOrderItem:
                            def __init__(self, item_id, raw_material_name, raw_material_id):
                                self.id = item_id
                                self.raw_material_id = raw_material_id
                                self.raw_material = type('RawMaterial', (), {'name': raw_material_name})() if raw_material_name else None
                        
                        for item_data in items_data:
                            valid_order_items.append(SimpleOrderItem(
                                item_data['id'],
                                item_data['raw_material__name'],
                                item_data['raw_material_id']
                            ))
                    except Exception as fallback_err:
                        bug_logger.error(f"خطا در fallback method: {fallback_err}", exc_info=True)
            
            # محاسبه اختلاف وزن بارنامه و وزن خالص
            weight_discrepancy = None
            weight_discrepancy_percent = None
            has_weight_discrepancy = False
            
            if transport.waybill_weight and transport.net_weight:
                weight_discrepancy = abs(transport.net_weight - transport.waybill_weight)
                if transport.waybill_weight > 0:
                    weight_discrepancy_percent = (weight_discrepancy / transport.waybill_weight) * 100
                    if weight_discrepancy_percent > 5:
                        has_weight_discrepancy = True
            
            context = {
                'transport': transport,
                'purchase_order': po,
                'order_items': valid_order_items,
                'accessible_transport_fields': accessible_transport_fields,
                'accessible_po_fields': accessible_po_fields,
                'accessible_person_fields': accessible_person_fields,
                'weight_discrepancy': weight_discrepancy,
                'weight_discrepancy_percent': weight_discrepancy_percent,
                'has_weight_discrepancy': has_weight_discrepancy,
            }
            
            bug_logger.info(f"رندر کردن template - rejected_transport_detail.html")
            return render(request, 'rejected_transport_detail.html', context)
        except Exception as context_err:
            bug_logger.error(f"خطا در آماده‌سازی context - حمل {transport_number}: {str(context_err)}", exc_info=True)
            messages.error(request, f'خطا در آماده‌سازی داده‌ها: {str(context_err)}')
            return redirect('supply:rejected_transports_list')
        
    except Transport.DoesNotExist:
        audit_logger.alert(f"تلاش برای دسترسی به حمل ناموجود - حمل {transport_number}")
        bug_logger.error(f"Transport.DoesNotExist - transport_number: {transport_number}")
        messages.error(request, 'حمل مورد نظر یافت نشد.')
        return redirect('supply:rejected_transports_list')
    except Exception as e:
        bug_logger.error(f"خطا در نمایش جزئیات حمل ارجاع به مدیریت - حمل {transport_number}: {str(e)}", exc_info=True)
        audit_logger.error(f"خطا در نمایش جزئیات حمل ارجاع به مدیریت - حمل {transport_number}: {str(e)}")
        messages.error(request, f'خطا در بارگذاری جزئیات حمل: {str(e)}')
        return redirect('supply:rejected_transports_list')