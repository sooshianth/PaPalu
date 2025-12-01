import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django import forms
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.html import format_html
from django.utils import timezone
from django_tables2 import RequestConfig
import jdatetime

from core.logging_levels import *
bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

from core.SupplyFolder.PurchaseTransportModel import PurchaseTransport
from core.SupplyFolder.ProcurementPurchaseOrderModel import ProcurementPurchaseOrder
from core.PersonFolder.PersonModel import Person
from core.RBACModel.TaskPermission import TaskChoices
from core.RBACModel.Roles import user_has_task
from supply.tables import PurchaseTransportTable
import django_tables2 as tables


class CarEntranceDriverForm(forms.Form):
    phone = forms.CharField(label='شماره تلفن راننده', required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    name = forms.CharField(label='نام راننده', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    national_id = forms.CharField(label='کد ملی', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    plate_number = forms.CharField(label='پلاک', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    account = forms.CharField(label='شماره حساب', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    sheba = forms.CharField(label='شماره شبا', required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))


class CarEntranceTable(PurchaseTransportTable):
    raw_materials = tables.Column(
        verbose_name='نام مواد اولیه',
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
        register_url = reverse('supply:carentrance_register_driver', args=[record.transport_number])
        enter_url = reverse('supply:carentrance_mark_entered', args=[record.transport_number])
        return format_html(
            '<div class="btn-group">'
            '<a href="{}" class="btn btn-primary btn-sm">ثبت راننده</a>'
            '<a href="{}" class="btn btn-success btn-sm" style="margin-left:6px">ثبت ورود</a>'
            '</div>',
            register_url,
            enter_url
        )
    
    class Meta(PurchaseTransportTable.Meta):
        sequence = ('transport_number', 'vehicle_type', 'raw_materials', 'status', 'created_at', 'actions')


@login_required
def car_entrance_list_view(request):
    """صفحه لیست ورود خودروها مخصوص نگهبان - فقط حمل‌هایی که در وضعیت "در انتظار ورود خودرو" هستند."""
    audit_logger.info("مشاهده صفحه ورود خودرو (نگهبان)")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_DRIVER.value):
        audit_logger.activity("تلاش برای دسترسی به صفحه ورود خودرو بدون دسترسی")
        messages.error(request, 'شما دسترسی به این بخش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    try:
        transports = PurchaseTransport.objects.filter(status=PurchaseTransport.STATUS_AWAITING_VEHICLE_ENTRY).select_related('purchase_order', 'driver').order_by('-created_at')
        table = CarEntranceTable(transports, prefix='car-')
        RequestConfig(request, paginate={'per_page': 20}).configure(table)
        return render(request, 'supply_carentrance_list.html', {'table': table})
    except Exception as e:
        bug_logger.error(f"Car entrance list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست ورود خودروها.')
        return render(request, 'supply_carentrance_list.html', {'table': PurchaseTransportTable([], prefix='car-')})


@login_required
def register_driver_for_transport_view(request, transport_number):
    """فرم ثبت اطلاعات راننده و پلاک برای یک حمل؛ پس از ثبت، وضعیت به "در انتظار تخلیه" تغییر می‌یابد."""
    audit_logger.info(f"دسترسی به فرم ثبت راننده برای حمل {transport_number}")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_DRIVER.value):
        audit_logger.activity(f"تلاش برای ثبت راننده بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به ثبت راننده را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)

    if pt.status != PurchaseTransport.STATUS_AWAITING_VEHICLE_ENTRY:
        audit_logger.activity(f"تلاش برای ثبت راننده برای حمل {transport_number} با وضعیت نامعتبر: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل ثبت راننده نیست.')
        return redirect(reverse('supply:carentrance'))

    if request.method == 'POST':
        form = CarEntranceDriverForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            phone = data.get('phone')
            audit_logger.info(f"شروع ثبت راننده برای حمل {transport_number}")
            try:
                with transaction.atomic():
                    # try to find driver by phone
                    driver = Person.objects.filter(phone_number=phone, type='driver').first()
                    if not driver:
                        bug_logger.info(f"راننده جدید با شماره تلفن ایجاد شد برای حمل {transport_number}")
                        # create a minimal driver record
                        driver = Person.objects.create(
                            name=data.get('name') or 'راننده ثبت نشده',
                            phone_number=phone,
                            national_id=data.get('national_id') or None,
                            type='driver'
                        )
                        audit_logger.info(f"راننده جدید ایجاد شد برای حمل {transport_number}")
                    else:
                        bug_logger.debug(f"راننده موجود یافت شد برای حمل {transport_number}")
                    
                    # Update transport fields
                    pt.driver = driver
                    if data.get('plate_number'):
                        pt.plate_number = data.get('plate_number')
                    # Store account/sheba as actual values
                    if data.get('account'):
                        pt.driver_account_number = data.get('account')
                    if data.get('sheba'):
                        pt.driver_sheba_number = data.get('sheba')
                    
                    # Record actual arrival time (gate entry time)
                    today_jalali = jdatetime.date.today()
                    pt.actual_arrival_date = today_jalali
                    pt.save()
                    
                    bug_logger.info(f"اطلاعات راننده و زمان ورود برای حمل {transport_number} ثبت شد")
                    
                    # Transition to awaiting_unloading (در انتظار تخلیه)
                    try:
                        pt.transition(
                            PurchaseTransport.STATUS_AWAITING_UNLOADING,
                            user=request.user,
                            note=f'ثبت ورود خودرو توسط نگهبان - راننده: {driver.name} - پلاک: {pt.plate_number or "ثبت نشده"}'
                        )
                        bug_logger.info(f"وضعیت حمل {transport_number} به 'در انتظار تخلیه' تغییر یافت")
                    except Exception as trans_err:
                        bug_logger.error(f"خطا در تغییر وضعیت حمل {transport_number}: {trans_err}")
                        raise
                    
                    # Update purchase order status to awaiting_delivery (در انتظار تحویل بار)
                    po = pt.purchase_order
                    if po.status == ProcurementPurchaseOrder.STATUS_AWAITING_VEHICLE_ENTRY:
                        po.transition(
                            ProcurementPurchaseOrder.STATUS_AWAITING_DELIVERY,
                            user=request.user,
                            note='ورود خودرو ثبت شد'
                        )
                        bug_logger.info(f"وضعیت سفارش {po.order_number} به 'در انتظار تحویل بار' تغییر یافت")
                        audit_logger.info(f"وضعیت سفارش {po.order_number} به دنبال ورود خودرو به‌روزرسانی شد")
                    
                    audit_logger.info(f"ورود خودرو ثبت شد - حمل: {transport_number} - راننده: {driver.name}")
                    
                messages.success(request, 'اطلاعات راننده ثبت شد و ورود خودرو ثبت گردید.')
                return redirect(reverse('supply:carentrance'))
            except Exception as e:
                bug_logger.error(f"خطا در ثبت راننده برای حمل {transport_number}: {e}")
                messages.error(request, 'خطا در ثبت اطلاعات راننده.')
        else:
            bug_logger.warning(f"فرم ثبت راننده نامعتبر برای حمل {transport_number}: {form.errors}")
            audit_logger.activity(f"فرم نامعتبر برای ثبت راننده حمل {transport_number}")
    else:
        # prefill if driver exists
        initial = {}
        if pt.driver:
            initial['phone'] = pt.driver.phone_number
            initial['name'] = pt.driver.name
            initial['national_id'] = getattr(pt.driver, 'national_id', '')
            initial['plate_number'] = pt.plate_number
        form = CarEntranceDriverForm(initial=initial)

    return render(request, 'supply_carentrance_register.html', {'form': form, 'pt': pt})


@login_required
def mark_vehicle_entered_view(request, transport_number):
    """علامت‌گذاری سریع ورود خودرو بدون اطلاعات راننده کامل - انتقال مستقیم به در انتظار تخلیه"""
    audit_logger.info(f"ثبت سریع ورود خودرو برای حمل {transport_number}")
    
    if not user_has_task(request.user, TaskChoices.SUPPLY_REGISTER_DRIVER.value):
        audit_logger.activity(f"تلاش برای ثبت سریع ورود بدون دسترسی - حمل {transport_number}")
        messages.error(request, 'شما دسترسی به این عملیات را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    
    if pt.status != PurchaseTransport.STATUS_AWAITING_VEHICLE_ENTRY:
        audit_logger.activity(f"تلاش برای ثبت سریع ورود برای حمل {transport_number} با وضعیت نامعتبر: {pt.status}")
        messages.error(request, 'این حمل در وضعیت قابل ثبت ورود نیست.')
        return redirect(reverse('supply:carentrance'))
    
    try:
        with transaction.atomic():
            # Record actual arrival time
            today_jalali = jdatetime.date.today()
            pt.actual_arrival_date = today_jalali
            pt.save(update_fields=['actual_arrival_date'])
            
            # Transition to awaiting_unloading
            pt.transition(
                PurchaseTransport.STATUS_AWAITING_UNLOADING,
                user=request.user,
                note='ثبت سریع ورود خودرو توسط نگهبان (بدون ثبت کامل راننده)'
            )
            
            # Update purchase order status
            po = pt.purchase_order
            if po.status == ProcurementPurchaseOrder.STATUS_AWAITING_VEHICLE_ENTRY:
                po.transition(
                    ProcurementPurchaseOrder.STATUS_AWAITING_DELIVERY,
                    user=request.user,
                    note='ثبت سریع ورود خودرو'
                )
                bug_logger.info(f"وضعیت سفارش {po.order_number} به 'در انتظار تحویل بار' تغییر یافت")
            
            audit_logger.info(f"ورود سریع خودرو ثبت شد - حمل: {transport_number}")
            
        messages.success(request, 'ورود خودرو ثبت شد.')
    except ValueError as ve:
        bug_logger.warning(f"انتقال نامعتبر برای حمل {transport_number}: {ve}")
        messages.error(request, str(ve))
    except Exception as e:
        bug_logger.error(f"خطا در ثبت سریع ورود برای حمل {transport_number}: {e}")
        messages.error(request, 'خطا در ثبت ورود خودرو.')
    return redirect(reverse('supply:carentrance'))


@login_required
def driver_lookup_api(request):
    """API ساده برای جستجوی راننده با شماره تلفن (برای autofill)"""
    phone = request.GET.get('phone')
    if not phone:
        return JsonResponse({'error': 'phone_required'}, status=400)
    try:
        driver = Person.objects.filter(phone_number=phone, type='driver').first()
        if not driver:
            return JsonResponse({'found': False})
        data = {
            'found': True,
            'name': driver.name,
            'national_id': getattr(driver, 'national_id', ''),
            'phone': driver.phone_number,
        }
        return JsonResponse(data)
    except Exception as e:
        bug_logger.error(f"Driver lookup error for phone {phone}: {e}")
        return JsonResponse({'error': 'lookup_failed'}, status=500)


class CarExitTable(PurchaseTransportTable):
    """جدول برای خودروهای در انتظار خروج"""
    def render_actions(self, record):
        # خروج خودرو فقط بعد از تکمیل تحویل انبار فعال است
        if record.status == PurchaseTransport.STATUS_COMPLETED:
            exit_url = reverse('supply:carexit_mark_exited', args=[record.transport_number])
            return format_html(
                '<a href="{}" class="btn btn-warning btn-sm">خروج ماشین</a>',
                exit_url
            )
        else:
            return format_html(
                '<span class="badge badge-secondary" style="font-size:0.7rem">در انتظار تحویل انبار</span>'
            )


@login_required
def car_exit_list_view(request):
    """صفحه لیست خروج خودروها مخصوص نگهبان - خودروهایی که وارد شده‌اند و در حال فرآیند تخلیه و تحویل هستند."""
    audit_logger.info("مشاهده صفحه خروج خودرو (نگهبان)")
    try:
        # نمایش حمل‌هایی که از مرحله تخلیه به بعد هستند و هنوز خارج نشده‌اند
        transports = PurchaseTransport.objects.filter(
            status__in=[
                PurchaseTransport.STATUS_AWAITING_UNLOADING,
                PurchaseTransport.STATUS_AWAITING_DELIVERY,
                PurchaseTransport.STATUS_AWAITING_WH_RECONCILIATION,
                PurchaseTransport.STATUS_COMPLETED
            ]
        ).select_related('purchase_order', 'driver').order_by('status', 'created_at')
        
        table = CarExitTable(transports, prefix='exit-')
        RequestConfig(request, paginate={'per_page': 20}).configure(table)
        return render(request, 'supply_carexit_list.html', {'table': table})
    except Exception as e:
        bug_logger.error(f"Car exit list error: {e}")
        messages.error(request, 'خطا در بارگذاری لیست خروج خودروها.')
        return render(request, 'supply_carexit_list.html', {'table': CarExitTable([], prefix='exit-')})


@login_required
def mark_vehicle_exited_view(request, transport_number):
    """ثبت خروج خودرو از کارخانه - فقط برای حمل‌های تکمیل شده"""
    audit_logger.info(f"ثبت خروج خودرو برای حمل {transport_number}")
    pt = get_object_or_404(PurchaseTransport, transport_number=transport_number)
    
    # فقط حمل‌های تکمیل شده می‌توانند خارج شوند
    if pt.status != PurchaseTransport.STATUS_COMPLETED:
        audit_logger.activity(f"تلاش برای خروج خودرو با وضعیت نامعتبر - حمل {transport_number}: وضعیت {pt.status}")
        messages.error(request, 'این خودرو هنوز آماده خروج نیست. باید ابتدا فرآیند تحویل انبار تکمیل شود.')
        return redirect(reverse('supply:carexit'))
    
    try:
        with transaction.atomic():
            # ثبت زمان خروج
            today_jalali = jdatetime.date.today()
            pt.delivery_date = today_jalali  # استفاده از delivery_date برای ثبت زمان خروج نهایی
            pt.save(update_fields=['delivery_date'])
            
            bug_logger.info(f"زمان خروج خودرو برای حمل {transport_number} ثبت شد")
            audit_logger.info(f"خروج خودرو ثبت شد - حمل: {transport_number} - راننده: {pt.driver.name if pt.driver else 'نامشخص'} - پلاک: {pt.plate_number or 'ثبت نشده'}")
            
        messages.success(request, f'خروج خودرو با شماره حمل {transport_number} ثبت شد.')
    except Exception as e:
        bug_logger.error(f"خطا در ثبت خروج خودرو برای حمل {transport_number}: {e}")
        messages.error(request, 'خطا در ثبت خروج خودرو.')
    
    return redirect(reverse('supply:carexit'))
