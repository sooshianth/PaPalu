from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect

from core.RBACModel import user_has_task, TaskChoices
from core.OrderFolder.OrderModel import Order
from core.SettlementFolder.SettlementModel import Settlement
from core.SettlementFolder.TransactionApprovalModel import TransactionApproval
from sales.forms.approve_transaction_receipt import TransactionApprovalForm


@login_required
def approve_transaction_receipt_list_view(request):
    """
    لیست سفارش‌های در وضعیت «در انتظار تأیید حسابداری»
    """
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        messages.error(request, 'شما دسترسی به تأیید تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    orders_qs = Order.objects.filter(status='pending_accounting_approval').order_by('-created_at')

    if not request.user.is_superuser:
        orders_qs = orders_qs.filter(registered_by=request.user)

    context = {
        'orders': orders_qs.select_related('registered_by', 'customer'),
        'page_title': 'سفارش‌های در انتظار تأیید حسابداری',
    }
    return render(request, 'sales/approve_transaction_receipt_list.html', context)


@login_required
def approve_transaction_receipt_detail_view(request, order_number):
    """
    صفحه جزئیات تأیید تراکنش برای یک سفارش
    - نمایش همه اسناد تراکنش آپلود شده
    - نمایش لیست تأییدهای ثبت شده
    - فرم ثبت تأیید جدید
    - بعد از اینکه مجموع مبالغ استعلام = مبلغ کل، سفارش به "در انتظار تخصیص" می‌رود
    """
    if not user_has_task(request.user, TaskChoices.SALES_APPROVE_PROFORMA.value):  # TODO: باید task مناسب اضافه شود
        messages.error(request, 'شما دسترسی به تأیید تراکنش فروش را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    order = get_object_or_404(Order, order_number=order_number)

    if not request.user.is_superuser and order.registered_by != request.user:
        messages.error(request, 'شما دسترسی به این سفارش ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')

    if order.status != 'pending_accounting_approval':
        messages.error(request, 'این سفارش در وضعیت مناسب برای تأیید حسابداری نیست.')
        return redirect('sales:approve_transaction_receipt_list')

    # محاسبه مبلغ کل سفارش از اقلام
    order_total_amount = order.get_total_amount()
    
    # گرفتن یا ساختن Settlement مرتبط با این سفارش
    settlement, created = Settlement.objects.get_or_create(
        order=order,
        defaults={
            'settlement_type': 'sale',
            'settlement_status': 'pending',
            'original_document_amount': order_total_amount,
            'debtor_person': order.customer,  # برای فروش، مشتری بدهکار است
            'creditor_person': None,  # می‌تواند از تنظیمات شرکت گرفته شود
        },
    )
    
    # اگر settlement از قبل وجود داشت، مبلغ اصلی را به‌روزرسانی کن
    if not created and settlement.original_document_amount != order_total_amount:
        settlement.original_document_amount = order_total_amount
        settlement.save(update_fields=['original_document_amount'])
    
    # لیست اسناد تراکنش
    documents = settlement.transaction_documents.all().select_related('source_account', 'destination_account')
    
    # لیست تأییدهای تراکنش (TransactionApproval)
    approvals = settlement.transaction_approvals.all().order_by('-created_at')
    total_inquiry_amount = approvals.aggregate(total=Sum('inquiry_amount'))['total'] or 0
    
    # بررسی اینکه آیا مجموع مبالغ استعلام با مبلغ کل تسویه برابر است
    can_approve = False
    if settlement.original_document_amount and total_inquiry_amount >= settlement.original_document_amount:
        can_approve = True

    if request.method == 'POST':
        form = TransactionApprovalForm(request.POST, settlement=settlement)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # ثبت تأیید جدید
                    approval = form.save(commit=False)
                    approval.settlement = settlement
                    approval.save()
                    messages.success(request, 'تأیید تراکنش با موفقیت ثبت شد.')
                    
                    # Refresh settlement از دیتابیس
                    settlement.refresh_from_db()
                    
                    # محاسبه مجدد مجموع مبالغ استعلام
                    approvals_qs = settlement.transaction_approvals.all()
                    total_inquiry_amount = approvals_qs.aggregate(total=Sum('inquiry_amount'))['total'] or 0
                    
                    # اگر مجموع مبالغ استعلام >= مبلغ کل تسویه شد، وضعیت سفارش را تغییر بده
                    if settlement.original_document_amount:
                        # تبدیل به float برای مقایسه دقیق
                        total_inquiry_float = float(total_inquiry_amount) if total_inquiry_amount else 0
                        original_amount_float = float(settlement.original_document_amount)
                        
                        # Debug: نمایش مقادیر
                        print(f"Debug: total_inquiry_float = {total_inquiry_float}, original_amount_float = {original_amount_float}")
                        
                        if total_inquiry_float >= original_amount_float:
                            # Refresh order از دیتابیس
                            order.refresh_from_db()
                            # بررسی مجدد وضعیت قبل از تغییر
                            if order.status == 'pending_accounting_approval':
                                order.status = 'pending_allocation'
                                order.save(update_fields=['status'])
                                messages.success(request, 'مجموع مبالغ استعلام با مبلغ کل تسویه برابر شد. سفارش به مرحله "در انتظار تخصیص" منتقل شد.')
                                # Redirect به لیست چون وضعیت تغییر کرده
                                return redirect('sales:approve_transaction_receipt_list')

                return redirect('sales:approve_transaction_receipt_detail', order_number=order_number)
            except Exception as e:
                messages.error(request, f'خطا در ثبت تأیید تراکنش: {str(e)}')
        else:
            messages.error(request, 'اطلاعات فرم معتبر نیست. لطفاً خطاها را بررسی کنید.')
    else:
        form = TransactionApprovalForm(settlement=settlement)

    # محاسبه باقیمانده
    remaining_amount = 0
    if settlement.original_document_amount:
        remaining_amount = float(settlement.original_document_amount) - float(total_inquiry_amount)

    context = {
        'order': order,
        'settlement': settlement,
        'documents': documents,
        'approvals': approvals,
        'total_inquiry_amount': total_inquiry_amount,
        'remaining_amount': remaining_amount,
        'can_approve': can_approve,
        'form': form,
        'page_title': f'تأیید تراکنش - سفارش {order.order_number}',
    }
    return render(request, 'sales/approve_transaction_receipt_detail.html', context)

