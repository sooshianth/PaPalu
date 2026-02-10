"""
View های مربوط به صفحه یکپارچه ارجاعات به مدیر
فقط سوپرادمین دسترسی دارد.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.db.models import Max, Q

from core.TransportFolder.TransportModel import Transport
from core.ProductionFolder.ProductionProgramModel import ProductionProgram
from core.OrderFolder.OrderModel import Order
from core.AllocationFolder.AllocationModel import Allocation


def _get_referrals(user):
    """
    جمع‌آوری تمام ارجاعات به مدیر از منابع مختلف.
    برگرداندن لیست با ساختار: type, source, resolve_url, identifier, created_at, description
    """
    if not user.is_superuser:
        return []

    referrals = []

    # 1. حمل‌های ارجاع به مدیریت (از تایید لجستیک)
    transports = Transport.objects.filter(status=Transport.STATUS_REJECTED).order_by('-updated_at')
    for t in transports:
        referrals.append({
            'type': 'transport',
            'source': 'تایید لجستیک',
            'resolve_url': reverse('supply:rejected_transport_detail', kwargs={'transport_number': t.transport_number}),
            'identifier': t.transport_number,
            'created_at': t.updated_at,
            'description': f'حمل {t.transport_number} - ارجاع به مدیریت (اختلاف وزن)',
        })

    # 2. برنامه‌های تولید رد شده (از اظهار تولید انبار)
    programs = ProductionProgram.objects.filter(
        status=ProductionProgram.Status.COMPLETED,
        sent_to_manager_for_revalidation=True
    ).select_related('product').order_by('-updated_at')
    for p in programs:
        product_name = p.product.name if p.product else (p.program_id or '-')
        referrals.append({
            'type': 'production',
            'source': 'اظهار تولید انبار',
            'resolve_url': reverse('production:manager_warehouse_resolve', kwargs={'program_id': p.id}),
            'identifier': p.program_id or str(p.id),
            'created_at': p.updated_at,
            'description': f'برنامه تولید {p.program_id or p.id} - {product_name}',
        })

    # 2.5. ثبت ورود خودرو ارجاع‌شده به مدیر (از نگهبان)
    carentrance_referred = Transport.objects.filter(
        carentrance_referred_to_manager=True,
        status=Transport.STATUS_AWAITING_VEHICLE_ENTRY
    ).order_by('-carentrance_referred_at')
    for t in carentrance_referred:
        dt = getattr(t, 'carentrance_referred_at', None) or t.updated_at
        referrals.append({
            'type': 'carentrance',
            'source': 'ثبت ورود خودرو',
            'resolve_url': reverse('supply:carentrance_register_driver', kwargs={'transport_number': t.transport_number or str(t.pk)}),
            'identifier': t.transport_number or str(t.pk),
            'created_at': dt,
            'description': f'حمل {t.transport_number or t.pk} - ارجاع از ثبت ورود خودرو',
        })

    # 3. تخصیص‌های رد شده (از تایید تخصیص)
    orders_with_rejected = Order.objects.filter(
        allocations__is_rejected=True
    ).annotate(
        last_rejected_at=Max('allocations__updated_at', filter=Q(allocations__is_rejected=True))
    ).distinct().order_by('-last_rejected_at')
    for o in orders_with_rejected:
        count = o.allocations.filter(is_rejected=True).count()
        dt = getattr(o, 'last_rejected_at', None) or o.updated_at
        referrals.append({
            'type': 'allocation',
            'source': 'تایید تخصیص',
            'resolve_url': reverse('sales:manage_allocations_detail', kwargs={'order_number': o.order_number}),
            'identifier': o.order_number,
            'created_at': dt,
            'description': f'سفارش {o.order_number} - {count} تخصیص رد شده',
        })

    # مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
    def sort_key(r):
        dt = r['created_at']
        if dt is None:
            return (0, None)  # بدون تاریخ در انتها
        return (1, dt)

    referrals.sort(key=sort_key, reverse=True)
    return referrals


@login_required
def referrals_list_view(request):
    """صفحه لیست ارجاعات به مدیر - فقط سوپرادمین"""
    if not request.user.is_superuser:
        return HttpResponseForbidden('شما دسترسی به این بخش را ندارید.')

    referrals = _get_referrals(request.user)
    context = {
        'referrals': referrals,
        'total_count': len(referrals),
    }
    return render(request, 'referrals_list.html', context)


@login_required
def referrals_api_view(request):
    """API برای بروزرسانی لایو لیست ارجاعات - برگرداندن JSON"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'عدم دسترسی'}, status=403)

    referrals = _get_referrals(request.user)

    # تبدیل تاریخ برای JSON
    def serialize_referral(r):
        dt = r['created_at']
        return {
            **r,
            'created_at': dt.strftime('%Y-%m-%d %H:%M') if dt else None,
        }

    return JsonResponse({
        'referrals': [serialize_referral(r) for r in referrals],
        'total_count': len(referrals),
    })
