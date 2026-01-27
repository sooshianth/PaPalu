from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils import timezone
from .models import SmsQueue, SmsLog
import datetime
import xlsxwriter
import io
from django.template.loader import get_template
from xhtml2pdf import pisa
import logging
import json
from django.contrib.auth.decorators import login_required
from .apis import queue_sms, process_sms_queue
import re
from django.db import connection
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role

logger = logging.getLogger("sms_api_views")

def persian_digits_to_english(persian_text):
    """تبدیل اعداد فارسی به انگلیسی در یک رشته."""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    return persian_text.translate(translation_table)

def jalali_to_gregorian(jalali_datetime_str):
    """تبدیل رشته جلالی (با اعداد فارسی) به DateTime گرگوریان."""
    try:
        from persiantools.jdatetime import JalaliDateTime
        
        # تبدیل اعداد فارسی به انگلیسی
        jalali_datetime_str_en = persian_digits_to_english(jalali_datetime_str)
        
        # تلاش برای تبدیل با فرمت صحیح
        return JalaliDateTime.strptime(jalali_datetime_str_en, "%Y/%m/%d %H:%M").to_gregorian()
    except Exception as e:
        raise ValueError(f"فرمت تاریخ نامعتبر است: {jalali_datetime_str} - خطای اصلی: {str(e)}")

def mask_phone_number(phone_number):
    """
    مخفی کردن شماره تلفن - فقط 3 رقم اول و 3 رقم آخر نمایش داده می‌شود
    مثال: 09123456789 -> 091*****789
    """
    if not phone_number:
        return ''
    
    phone_str = str(phone_number).strip()
    if len(phone_str) < 6:
        return phone_str
    
    # 3 رقم اول + ستاره‌ها + 3 رقم آخر
    if phone_str.startswith('09'):
        last_three = phone_str[:4]
    else:
        last_three = phone_str[:3]
    first_three = phone_str[-3:]
    middle_stars = '*' * (len(phone_str) - 6)

    return first_three + middle_stars + last_three


@role_required('admin')
@login_required
def sms_queue(request):
    """مشاهده صف پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    
    # فیلتر کردن داده‌ها
    queue_items = SmsQueue.objects.all()
    
    if status:
        queue_items = queue_items.filter(status=status)
    
    if notification_type:
        queue_items = queue_items.filter(notification_type=notification_type)
    
    if search:
        queue_items = queue_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    # مرتب‌سازی
    queue_items = queue_items.order_by('-created_at')
    
    # صفحه‌بندی
    paginator = Paginator(queue_items, 12)  # 12 آیتم در هر صفحه
    page_number = request.GET.get('page', 1)
    queue_items = paginator.get_page(page_number)
    
    # تعداد پیامک‌ها با وضعیت‌های مختلف
    pending_count = SmsQueue.objects.filter(status='pending').count()
    sent_count = SmsQueue.objects.filter(status='sent').count()
    failed_count = SmsQueue.objects.filter(status='failed').count()
    suspended_count = SmsQueue.objects.filter(status='suspended').count()
    
    context = {
        'queue_items': queue_items,
        'status': status,
        'notification_type': notification_type,
        'search': search,
        'pending_count': pending_count,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'suspended_count': suspended_count,
        'notification_types': SmsQueue.NOTIFICATION_TYPES,
    }
    
    return render(request, 'sms_api/sms_queue.html', context)


@role_required('admin')
@login_required
def sms_log(request):
    """مشاهده تاریخچه پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # فیلتر کردن داده‌ها
    log_items = SmsLog.objects.all()
    
    if status:
        log_items = log_items.filter(status=status)
    
    if notification_type:
        log_items = log_items.filter(notification_type=notification_type)
    
    if search:
        log_items = log_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # مرتب‌سازی
    log_items = log_items.order_by('-sent_at')
    
    # صفحه‌بندی
    paginator = Paginator(log_items, 20)  # 20 آیتم در هر صفحه
    page_number = request.GET.get('page', 1)
    log_items = paginator.get_page(page_number)
    
    # آمار
    total_count = SmsLog.objects.count()
    sent_count = SmsLog.objects.filter(status='sent').count()
    failed_count = SmsLog.objects.filter(status='failed').count()
    today = timezone.now().date()
    today_count = SmsLog.objects.filter(sent_at__date=today).count()
    
    # انواع اطلاع‌رسانی برای فیلتر
    notification_types = SmsQueue.NOTIFICATION_TYPES
    
    context = {
        'log_items': log_items,
        'status': status,
        'notification_type': notification_type,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
        'total_count': total_count,
        'sent_count': sent_count,
        'failed_count': failed_count,
        'today_count': today_count,
        'notification_types': notification_types,
    }
    
    return render(request, 'sms_api/sms_log.html', context)


@role_required('admin')
@login_required
def edit_sms(request, sms_id):
    """ویرایش پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار یا معلق قابل ویرایش هستند
    if sms.status not in ['pending', 'suspended']:
        messages.error(request, 'فقط پیامک‌های در انتظار یا معلق قابل ویرایش هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    if request.method == 'POST':
        recipient_number = request.POST.get('recipient_number')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type')
        scheduled_for = request.POST.get('scheduled_for')
        purchase_id = request.POST.get('purchase_id')
        
        # اعتبارسنجی داده‌ها
        if not recipient_number or not message:
            messages.error(request, 'لطفاً تمامی فیلدهای ضروری را پر کنید.')
            return redirect('sms_api:edit_sms', sms_id=sms.id)
        
        # تبدیل شناسه خرید به عدد
        try:
            purchase_id = int(purchase_id) if purchase_id else None
        except ValueError:
            purchase_id = None
        
        # تبدیل زمان ارسال
        if scheduled_for:
            try:
                scheduled_for = timezone.datetime.strptime(scheduled_for, '%Y-%m-%dT%H:%M')
                scheduled_for = timezone.make_aware(scheduled_for)
            except ValueError:
                scheduled_for = timezone.now()
        else:
            scheduled_for = timezone.now()
        
        # به‌روزرسانی پیامک
        sms.recipient_number = recipient_number
        sms.message = message
        sms.notification_type = notification_type
        sms.scheduled_for = scheduled_for
        sms.purchase_id = purchase_id
        sms.save()
        
        messages.success(request, 'پیامک با موفقیت به‌روزرسانی شد.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    # انواع اطلاع‌رسانی
    notification_types = SmsQueue.NOTIFICATION_TYPES
    
    context = {
        'sms': sms,
        'notification_types': notification_types,
        'scheduled_for': sms.scheduled_for.strftime('%Y-%m-%dT%H:%M') if sms.scheduled_for else None,
    }
    
    return render(request, 'sms_api/edit_sms.html', context)


@role_required('admin')
@login_required
@require_POST
def delete_sms(request, sms_id):
    """حذف پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار یا معلق قابل حذف هستند
    if sms.status not in ['pending', 'suspended']:
        messages.error(request, 'فقط پیامک‌های در انتظار یا معلق قابل حذف هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.delete()
    messages.success(request, 'پیامک با موفقیت حذف شد.')
    return redirect('sms_api:sms_queue')


@role_required('admin')
@login_required
def suspend_sms(request, sms_id):
    """تعلیق پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار قابل تعلیق هستند
    if sms.status != 'pending':
        messages.error(request, 'فقط پیامک‌های در انتظار قابل تعلیق هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.status = 'suspended'
    sms.is_suspended = True
    sms.save()
    
    messages.success(request, 'پیامک با موفقیت معلق شد.')
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
def resume_sms(request, sms_id):
    logger.debug(f"Resuming SMS with ID: {sms_id}")
    """از سرگیری پیامک معلق"""
    try:
        sms = get_object_or_404(SmsQueue, id=sms_id)
        
        # فقط پیامک‌های معلق قابل از سرگیری هستند
        if sms.status != 'suspended':
            messages.error(request, 'فقط پیامک‌های معلق قابل از سرگیری هستند.')
            return redirect('sms_api:sms_detail', sms_id=sms.id)
        
        sms.status = 'pending'
        sms.is_suspended = False
        sms.save()
        messages.success(request, 'پیامک با موفقیت از سرگرفته شد.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    except Exception as e:
        logger.error(f"Error resuming SMS with ID {sms_id}: {e}")
        messages.error(request, 'خطا در از سرگیری پیامک.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
@require_POST
def send_sms_now(request, sms_id):
    """ارسال فوری پیامک"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های در انتظار قابل ارسال فوری هستند
    if sms.status != 'pending':
        messages.error(request, 'فقط پیامک‌های در انتظار قابل ارسال فوری هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    # اگر پیامک مرتبط با خرید است و مشتری دارد، به همه شماره‌های مشتری ارسال شود
    if sms.purchase and hasattr(sms.purchase, 'customer') and sms.purchase.customer:
        customer = sms.purchase.customer
        phone_numbers = customer.get_all_phone_numbers()
        
        if not phone_numbers:
            messages.error(request, f'هیچ شماره تلفنی برای مشتری {customer.name} یافت نشد.')
            return redirect('sms_api:sms_detail', sms_id=sms.id)
        
        success_count = 0
        for phone in phone_numbers:
            from sms_api.apis import sms_account
            result = sms_account.send_sms(phone, sms.message)
            
            if result and isinstance(result, list) and 200 in result:
                # ثبت در لاگ
                SmsLog.objects.create(
                    recipient_number=phone,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='sent',
                    purchase=sms.purchase,
                    api_response=json.dumps(result)
                )
                success_count += 1
        
        if success_count > 0:
            # به‌روزرسانی وضعیت پیامک اصلی
            sms.status = 'sent'
            sms.sent_at = timezone.now()
            sms.save()
            
            messages.success(request, f'پیامک با موفقیت به {success_count} شماره ارسال شد.')
        else:
            messages.error(request, 'ارسال پیامک ناموفق بود. لطفا دوباره تلاش کنید.')
    else:
        # ارسال به یک شماره تکی
        from sms_api.apis import sms_account
        result = sms_account.send_sms(sms.recipient_number, sms.message)
            
        # به‌روزرسانی وضعیت پیامک
        if result and isinstance(result, list) and 200 in result:
            sms.status = 'sent'
            sms.sent_at = timezone.now()
            sms.save()
            
            # ثبت در لاگ
            SmsLog.objects.create(
                recipient_number=sms.recipient_number,
                message=sms.message,
                notification_type=sms.notification_type,
                status='sent',
                purchase=sms.purchase,
                api_response=json.dumps(result)
            )
            
            messages.success(request, 'پیامک با موفقیت ارسال شد.')
        else:
            messages.error(request, 'ارسال پیامک ناموفق بود. لطفا دوباره تلاش کنید.')
            
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
@require_POST
def retry_sms(request, sms_id):
    """تلاش مجدد برای ارسال پیامک ناموفق"""
    sms = get_object_or_404(SmsQueue, id=sms_id)
    
    # فقط پیامک‌های ناموفق قابل ارسال مجدد هستند
    if sms.status != 'failed':
        messages.error(request, 'فقط پیامک‌های ناموفق قابل ارسال مجدد هستند.')
        return redirect('sms_api:sms_detail', sms_id=sms.id)
    
    sms.status = 'pending'
    sms.retry_count += 1
    sms.save()
    
    messages.success(request, 'پیامک برای ارسال مجدد در صف قرار گرفت.')
    return redirect('sms_api:sms_detail', sms_id=sms.id)


@role_required('admin')
@login_required
def export_sms_log_excel(request):
    """خروجی اکسل از تاریخچه پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # فیلتر کردن داده‌ها
    log_items = SmsLog.objects.all()
    
    if status:
        log_items = log_items.filter(status=status)
    
    if notification_type:
        log_items = log_items.filter(notification_type=notification_type)
    
    if search:
        log_items = log_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # مرتب‌سازی
    log_items = log_items.order_by('-sent_at')
    
    # ایجاد فایل اکسل
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    # فرمت‌ها
    header_format = workbook.add_format({'bold': True, 'bg_color': '#B2DFDB', 'border': 1})
    cell_format = workbook.add_format({'border': 1})
    date_format = workbook.add_format({'border': 1, 'num_format': 'yyyy/mm/dd hh:mm:ss'})
    
    # سرستون‌ها
    headers = ['ردیف', 'شماره گیرنده', 'نوع اطلاع رسانی', 'تاریخ ارسال', 'وضعیت', 'متن پیام']
    
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header, header_format)
    
    # داده‌ها
    for row_num, sms in enumerate(log_items, 1):
        notification_type_display = dict(SmsQueue.NOTIFICATION_TYPES).get(sms.notification_type, sms.notification_type)
        status_display = 'ارسال شده' if sms.status == 'sent' else 'ناموفق'
        
        worksheet.write(row_num, 0, row_num, cell_format)
        worksheet.write(row_num, 1, sms.recipient_number, cell_format)
        worksheet.write(row_num, 2, notification_type_display, cell_format)
        worksheet.write(row_num, 3, sms.sent_at, date_format)
        worksheet.write(row_num, 4, status_display, cell_format)
        worksheet.write(row_num, 5, sms.message, cell_format)
    
    # تنظیم عرض ستون‌ها
    worksheet.set_column(0, 0, 8)
    worksheet.set_column(1, 1, 15)
    worksheet.set_column(2, 2, 20)
    worksheet.set_column(3, 3, 20)
    worksheet.set_column(4, 4, 12)
    worksheet.set_column(5, 5, 50)
    
    workbook.close()
    
    # تنظیم پاسخ HTTP
    output.seek(0)
    
    filename = f'sms_log_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename={filename}'
    
    return response


@role_required('admin')
@login_required
def export_sms_log_pdf(request):
    """خروجی PDF از تاریخچه پیامک‌ها"""
    # پارامترهای فیلتر
    status = request.GET.get('status', '')
    notification_type = request.GET.get('notification_type', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # فیلتر کردن داده‌ها
    log_items = SmsLog.objects.all()
    
    if status:
        log_items = log_items.filter(status=status)
    
    if notification_type:
        log_items = log_items.filter(notification_type=notification_type)
    
    if search:
        log_items = log_items.filter(
            Q(recipient_number__icontains=search) | 
            Q(message__icontains=search)
        )
    
    if date_from:
        try:
            date_from_obj = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            log_items = log_items.filter(sent_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # مرتب‌سازی
    log_items = log_items.order_by('-sent_at')
    
    # محدود کردن تعداد نتایج برای PDF
    log_items = log_items[:200]
    
    # تهیه داده‌ها برای تمپلیت
    context = {
        'log_items': log_items,
        'title': 'گزارش پیامک‌ها',
        'date': timezone.now().strftime('%Y/%m/%d %H:%M:%S'),
    }
    
    # رندر کردن تمپلیت HTML
    template = get_template('sms_api/pdf_template.html')
    html = template.render(context)
    
    # ایجاد فایل PDF
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        filename = f'sms_log_{timezone.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename={filename}'
        return response
    
    return HttpResponse('خطا در ایجاد PDF', status=400)

@role_required('admin')
@login_required
def sms_logs(request):
    """نمایش لیست پیامک‌های ارسال شده"""
    logs = SmsLog.objects.all().order_by('-sent_at')
    return render(request, 'sms_api/sms_logs.html', {'logs': logs})

@role_required('admin')
@login_required
@require_POST
def process_sms_queue_manually(request):
    """
    اجرای دستی پردازش صف پیامک ها
    برای مواقعی که سیستم خودکار (سلری) در دسترس نیست
    """
    try:
        # اجرای پردازش صف پیامک
        results = process_sms_queue()
        
        # تعداد پیام‌های ارسال شده
        sent_count = sum(1 for r in results if r.get("status") == "sent")
        
        # تعداد پیام‌های ناموفق
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        
        if not results:
            messages.info(request, "هیچ پیامکی در صف ارسال یافت نشد.")
        else:
            messages.success(
                request, 
                f"پردازش صف با موفقیت انجام شد. {sent_count} پیام ارسال شد و {failed_count} پیام ناموفق بود."
            )
            
        # ثبت لاگ
        logger.info(f"پردازش دستی صف پیامک توسط کاربر {request.user}: {len(results)} پیامک")
        
    except Exception as e:
        messages.error(request, f"خطا در پردازش صف پیامک: {str(e)}")
        logger.error(f"خطا در پردازش دستی صف پیامک: {str(e)}")
    
    # بازگشت به صفحه قبلی
    return redirect('sms_api:sms_queue')

