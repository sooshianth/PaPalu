from django.utils import timezone
import json
from .models import SmsLog, SmsQueue, is_celery_active, SmsConfig
from sms_ir import SmsIr
from django.conf import settings
import re
import logging

# Get API key and line number from settings
api_key = settings.SMS_API_KEY
linenumber = settings.SMS_LINE_NUMBER

sms_account = SmsIr(api_key, linenumber)

logger = logging.getLogger("sms_api_api")

def normalize_phone_number(phone_number):
    """
    نرمال‌سازی شماره تلفن به فرمت استاندارد (10 رقمی شروع با 9)
    
    Args:
        phone_number (str): شماره تلفن خام
        
    Returns:
        str: شماره تلفن نرمال شده یا None اگر نامعتبر باشد
    """
    if not phone_number:
        return None
    
    # تبدیل به رشته و حذف فضاهای خالی
    phone_str = str(phone_number).strip()
    
    # تبدیل اعداد فارسی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    phone_str = phone_str.translate(translation_table)
    
    # حذف کاراکترهای غیرعددی (به جز + در ابتدا)
    if phone_str.startswith('+'):
        cleaned = '+' + ''.join(c for c in phone_str[1:] if c.isdigit())
    else:
        cleaned = ''.join(c for c in phone_str if c.isdigit())
    
    # اگر هیچ عددی نداشت، None برگردان
    if not any(c.isdigit() for c in cleaned):
        return None
    
    # حذف پیشوندهای مختلف
    if cleaned.startswith('+98'):
        cleaned = cleaned[3:]
    elif cleaned.startswith('0098'):
        cleaned = cleaned[4:]
    elif cleaned.startswith('98') and len(cleaned) >= 12:  # 98 + حداقل 10 digits
        cleaned = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) >= 11:  # 0 + حداقل 10 digits
        cleaned = cleaned[1:]
    
    # اعتبارسنجی نهایی: باید 10 رقم و شروع با 9 باشد
    if len(cleaned) == 10 and cleaned.startswith('9') and cleaned.isdigit():
        return cleaned
    
    # تلاش برای استخراج شماره معتبر از رشته طولانی‌تر
    if len(cleaned) > 10:
        for i in range(len(cleaned) - 9):
            potential_number = cleaned[i:i+10]
            if potential_number.startswith('9') and potential_number.isdigit():
                return potential_number
    
    return None

def normalize_phone_numbers_list(phone_numbers):
    """
    نرمال‌سازی لیستی از شماره‌های تلفن و حذف تکرارها
    
    Args:
        phone_numbers (list): لیست شماره‌های تلفن خام
        
    Returns:
        list: لیست شماره‌های تلفن نرمال شده و بدون تکرار
    """
    if not phone_numbers:
        return []
    
    normalized_set = set()
    for phone in phone_numbers:
        normalized = normalize_phone_number(phone)
        if normalized:
            normalized_set.add(normalized)
    
    return sorted(list(normalized_set))


def send_instant_sms(number:str, message:str, sms_account=sms_account):
    """
    Legacy function for immediate SMS sending. Now adds to queue with immediate processing flag.
    """
    if True: # is_celery_active:
        try:
            queue_sms(number, message, notification_type='custom')
            return True
        except Exception as e:
            print(f"SMS queueing error: {e}")
            return None
    else:
        try:
            response = sms_account.send_sms(number, message)
            if response:
                # Log the sent message
                SmsLog.objects.create(
                    recipient_number=number,
                    message=message,
                    notification_type='custom',
                    status='sent',
                    api_response=json.dumps(response) if response else None
                )
            return response
        except Exception as e:
            print(f"SMS sending error: {e}")
            return None


def queue_sms(number:str, message:str, notification_type='custom', purchase=None, suspended=False, scheduled_for=None):
    """
    Add SMS to the queue for batch processing
    """
    try:
        if not number or not message:
            logger.error(f"SMS queue error: Empty number or message")
            raise ValueError("شماره تلفن و متن پیام نمی‌توانند خالی باشند")
            
        # استفاده از تابع نرمال‌سازی جدید
        original_number = number
        normalized_number = normalize_phone_number(number)
        
        if not normalized_number:
            logger.error(f"SMS queue error: Invalid phone number format: {original_number}")
            raise ValueError(f"فرمت شماره تلفن {original_number} نامعتبر است. باید 10 رقم باشد و با 9 شروع شود.")
        
        # تبدیل به فرمت 11 رقمی برای ذخیره (اضافه کردن 0)
        number = '0' + normalized_number
        
        # Log the SMS being queued
        purchase_info = f"Purchase: {purchase.id}" if purchase else "No purchase"
        logger.info(f"Queueing SMS to {number} (normalized from {original_number}) - Type: {notification_type} - {purchase_info}")
                
        # Create queue entry
        status = 'suspended' if suspended else 'pending'
        
        sms_queue_data = {
            'recipient_number': number,
            'message': message,
            'notification_type': notification_type,
            'status': status,
            'is_suspended': suspended,
            'purchase': purchase
        }
        
        if scheduled_for:
            sms_queue_data['scheduled_for'] = scheduled_for
            
        sms_queue = SmsQueue.objects.create(**sms_queue_data)
        logger.info(f"SMS queued successfully: Queue ID {sms_queue.id}")
        return sms_queue
    except Exception as e:
        logger.error(f"Error queueing SMS to {number}: {str(e)}")
        raise  # Re-raise the exception to be handled by the caller

def process_sms_queue(batch_size=20, sms_account=sms_account):
    from sms_api.models import SmsConfig
    if not SmsConfig.is_sms_enabled():
        logger.info("SMS processing is disabled")
        return []
    """
    Process a batch of queued SMS messages
    To be run by a scheduled task (e.g., celery, cron job)
    """
    # Get pending, non-suspended messages ordered by scheduled time
    pending_messages = SmsQueue.objects.filter(
        status='pending',
        is_suspended=False,
        # scheduled_for__lte=timezone.now()  # فقط پیام‌هایی که زمان ارسال آنها فرا رسیده
    ).order_by('scheduled_for', 'created_at')[:batch_size]
    
    count = pending_messages.count()
    if count == 0:
        logger.debug("No pending messages found to process")
        return []

    logger.info(f"Processing {count} SMS messages from queue")
    results = []
    
    for sms in pending_messages:
        try:
            recipient = sms.recipient_number
            logger.info(f"Sending SMS to {recipient} (Queue ID: {sms.id})")
            
            # تلاش برای ارسال پیامک
            response = None
            try:
                # استفاده از api_key و linenumber از تنظیمات
                response = sms_account.send_sms(recipient, sms.message)
                logger.debug(f"SMS API response for {recipient}: {response}")
            except Exception as api_error:
                logger.error(f"Error from SMS API for {recipient}: {str(api_error)}")
                response = {"error": str(api_error)}
            
            # بررسی پاسخ API و به‌روزرسانی وضعیت
            # در محیط پروداکشن، اگر API کال شده و exception نداده، پیامک ارسال شده است
            sms_sent_successfully = False
            
            if response is not None:
                # بررسی اینکه آیا پاسخ حاوی خطا است یا نه
                if isinstance(response, dict) and 'error' in response:
                    # پاسخ حاوی خطا است
                    sms_sent_successfully = False
                    error_message = response.get('error', 'Unknown error')
                    logger.warning(f"SMS API returned error for {recipient}: {error_message}")
                else:
                    # پاسخ عادی دریافت شده - در محیط پروداکشن این معنی موفقیت است
                    sms_sent_successfully = True
                    logger.debug(f"SMS API returned response for {recipient}: {response}")
            else:
                # هیچ پاسخی دریافت نشده - این نادر است اما ممکن است در تست‌ها اتفاق بیفتد
                # بررسی تنظیمات برای تعیین رفتار
                assume_success = SmsConfig.should_assume_success_on_no_error()
                sms_sent_successfully = assume_success
                if assume_success:
                    logger.info(f"SMS API returned no response for {recipient} - assuming success based on config")
                else:
                    logger.warning(f"SMS API returned no response for {recipient} - marking as failed based on config")
            
            if sms_sent_successfully:
                # پیام با موفقیت ارسال شده
                sms.status = 'sent'
                sms.sent_at = timezone.now()
                sms.save()
                
                # ثبت در لاگ موفقیت
                try:
                    serializable_response = response
                    if response is not None:
                        json.dumps(response)
                except TypeError:
                    serializable_response = str(response) if response is not None else "No response"
                
                SmsLog.objects.create(
                    recipient_number=recipient,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='sent',
                    api_response=json.dumps(serializable_response) if serializable_response else None,
                    purchase=sms.purchase
                )
                
                logger.info(f"SMS sent successfully to {recipient} (Queue ID: {sms.id})")
                results.append({"id": sms.id, "status": "sent", "result": response})
            else:
                # پیام ارسال نشده - فقط در مواردی که واقعاً خطا داشته‌ایم
                sms.status = 'failed'
                sms.retry_count += 1
                sms.save()
                
                # ثبت در لاگ خطا
                error_response = response if response is not None else {"error": "No response from API"}
                SmsLog.objects.create(
                    recipient_number=recipient,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='failed',
                    api_response=json.dumps(error_response),
                    purchase=sms.purchase
                )
                
                logger.error(f"Failed to send SMS to {recipient} (Queue ID: {sms.id}): {error_response}")
                results.append({"id": sms.id, "status": "failed", "error": str(error_response)})
        except Exception as e:
            logger.exception(f"Unexpected error processing SMS queue item {sms.id}: {str(e)}")
            
            try:
                # به‌روزرسانی وضعیت پیامک در صورت بروز خطا
                sms.status = 'failed'
                sms.retry_count += 1
                sms.save()
                
                # ثبت در لاگ خطا
                SmsLog.objects.create(
                    recipient_number=sms.recipient_number,
                    message=sms.message,
                    notification_type=sms.notification_type,
                    status='failed',
                    api_response=json.dumps({"error": str(e)}),
                    purchase=sms.purchase
                )
                
                results.append({"id": sms.id, "status": "failed", "error": str(e)})
            except Exception as inner_error:
                logger.exception(f"Error handling failure for SMS {sms.id}: {str(inner_error)}")
    
    # گزارش کلی
    sent_count = sum(1 for r in results if r.get('status') == 'sent')
    failed_count = sum(1 for r in results if r.get('status') == 'failed')
    logger.info(f"SMS queue processing complete: {sent_count} sent, {failed_count} failed")
    
    return results

def todays_sms_report(sms_account=sms_account):
    return sms_account.report_today(
        page_size=20,
        page_number=15,
        )


def process_excel_file(excel_file):
    """
    پردازش فایل اکسل و استخراج شماره‌های تلفن
    
    Args:
        excel_file: فایل اکسل آپلود شده
        
    Returns:
        list: لیست شماره‌های تلفن نرمال شده
    """
    try:
        import pandas as pd
        logger.info(f"Starting Excel file processing: {excel_file.name}")
        
        # خواندن فایل اکسل با مدیریت خطاهای مختلف
        try:
            df = pd.read_excel(excel_file, engine='openpyxl')
        except ImportError:
            try:
                df = pd.read_excel(excel_file, engine='xlrd')
            except ImportError:
                raise ValueError("پکیج openpyxl یا xlrd برای خواندن فایل اکسل نصب نیست")
        except pd.errors.EmptyDataError:
            raise ValueError("فایل اکسل خالی است")
        except Exception as e:
            raise ValueError(f"خطا در خواندن فایل اکسل: {str(e)}")
        
        logger.info(f"Excel file loaded successfully. Shape: {df.shape}")
        
        if df.empty:
            raise ValueError("فایل اکسل خالی است یا هیچ داده‌ای ندارد")
        
        phone_numbers = set()  # استفاده از set برای جلوگیری از تکرار
        processed_cells = 0
        valid_numbers_found = 0
        
        # جستجو در تمام ستون‌ها برای پیدا کردن شماره‌های تلفن
        for column_idx, column in enumerate(df.columns):
            logger.info(f"Processing column {column_idx + 1}/{len(df.columns)}: '{column}'")
            
            for row_idx, value in enumerate(df[column].dropna()):
                processed_cells += 1
                
                # تبدیل به رشته
                str_value = str(value).strip()
                
                # بررسی اینکه آیا این مقدار شبیه شماره تلفن است یا نه
                if is_phone_number_like(str_value):
                    normalized = normalize_phone_number(str_value)
                    if normalized:
                        phone_numbers.add(normalized)
                        valid_numbers_found += 1
                        logger.debug(f"Found valid number at row {row_idx + 1}, column '{column}': {str_value} -> {normalized}")
        
        logger.info(f"Excel processing complete. Processed {processed_cells} cells, found {valid_numbers_found} valid numbers, {len(phone_numbers)} unique numbers")
        
        if not phone_numbers:
            raise ValueError("هیچ شماره تلفن معتبری در فایل اکسل یافت نشد. لطفاً مطمئن شوید که فایل حاوی شماره‌های تلفن معتبر ایرانی است")
        
        return sorted(list(phone_numbers))
        
    except ImportError as e:
        logger.error(f"Import error in process_excel_file: {str(e)}")
        raise ValueError("پکیج pandas برای پردازش فایل اکسل نصب نیست. لطفاً پکیج را نصب کنید")
    except ValueError as e:
        logger.error(f"ValueError in process_excel_file: {str(e)}")
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error processing Excel file: {str(e)}")
        raise ValueError(f"خطای غیرمنتظره در پردازش فایل اکسل: {str(e)}")

def is_phone_number_like(value):
    """
    بررسی اینکه آیا یک رشته شبیه شماره تلفن است یا نه
    
    Args:
        value (str): رشته برای بررسی
        
    Returns:
        bool: True اگر شبیه شماره تلفن باشد
    """
    if not value:
        return False
    
    try:
        str_value = str(value).strip()
        
        # بررسی خالی نبودن پس از تبدیل به رشته
        if not str_value:
            return False
        
        # حذف کاراکترهای غیرعددی (به جز + در ابتدا)
        clean_value = ''.join(c for c in str_value if c.isdigit() or c == '+')
        
        # بررسی حداقل طول
        if len(clean_value) < 10:
            return False
        
        # بررسی حداکثر طول (برای جلوگیری از شناسه‌های طولانی)
        if len(clean_value) > 15:
            return False
        
        # بررسی اینکه حداقل 70% اعداد باشد - با جلوگیری از division by zero
        str_len = len(str_value)
        if str_len == 0:
            return False
        
        digit_count = sum(1 for c in str_value if c.isdigit())
        digit_ratio = digit_count / str_len
        
        return digit_ratio >= 0.7
        
    except Exception as e:
        logger.error(f"Error in is_phone_number_like with value '{value}': {str(e)}")
        return False

def parse_phone_numbers_from_text(text):
    """
    استخراج شماره‌های تلفن از متن
    
    Args:
        text (str): متن شامل شماره‌های تلفن
        
    Returns:
        list: لیست شماره‌های تلفن نرمال شده
    """
    if not text:
        logger.warning("parse_phone_numbers_from_text: Empty text provided")
        return []
    
    logger.info(f"Starting text parsing. Text length: {len(text)} characters")
    
    try:
        # جدا کردن بر اساس خط جدید، کاما، فاصله
        separators = ['\n', ',', ' ', '\t', ';', '\r']
        numbers_text = text.strip()
        
        for sep in separators:
            numbers_text = numbers_text.replace(sep, '|')
        
        # استخراج شماره‌ها
        potential_numbers = [num.strip() for num in numbers_text.split('|') if num.strip()]
        
        logger.info(f"Found {len(potential_numbers)} potential number candidates")
        
        phone_numbers = set()
        valid_count = 0
        invalid_count = 0
        
        for idx, num in enumerate(potential_numbers):
            if is_phone_number_like(num):
                normalized = normalize_phone_number(num)
                if normalized:
                    phone_numbers.add(normalized)
                    valid_count += 1
                    logger.debug(f"Valid number {valid_count}: {num} -> {normalized}")
                else:
                    invalid_count += 1
                    logger.debug(f"Invalid number after normalization: {num}")
            else:
                invalid_count += 1
                logger.debug(f"Not phone-like: {num}")
        
        logger.info(f"Text parsing complete. Valid: {valid_count}, Invalid: {invalid_count}, Unique: {len(phone_numbers)}")
        
        if not phone_numbers:
            logger.warning("No valid phone numbers found in text")
        
        return sorted(list(phone_numbers))
        
    except Exception as e:
        logger.exception(f"Error parsing phone numbers from text: {str(e)}")
        raise ValueError(f"خطا در استخراج شماره‌های تلفن از متن: {str(e)}")

