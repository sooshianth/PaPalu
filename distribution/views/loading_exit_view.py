from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django_tables2 import RequestConfig
import logging
from core.logging_levels import *

from core.RBACModel import user_has_task, TaskChoices
from core.TransportFolder.TransportModel import Transport
from core.TransportFolder.ProductInfoModel import ProductInfo
from core.TransportFolder.LoadingScheduleInfoModel import LoadingScheduleInfo
from core.TransportFolder.TruckInfoModel import TruckInfo
from core.PersonFolder.PersonModel import Person
from core.PersonFolder.PhoneNumberModel import PhoneNumber
from core.PersonFolder.BankAccountModel import BankAccount
from core.PersonFolder.FinancialBankingModel import FinancialBanking
from core.AllocationFolder.AllocationModel import Allocation
from core.WarehouseFolder.WarehouseModel import Warehouse
from django.contrib.contenttypes.models import ContentType
from core.helpers import check_field_access_prefer_edit
from distribution.forms.loading_exit_form import LoadingExitForm
from distribution.tables import LoadingExitTable
from core.StockEntryFolder.StockEntryModel import StockEntry
from core.StockEntryFolder.SourceStockModel import SourceStock
from core.StockEntryFolder.TargetStockModel import TargetStock
from core.StockEntryFolder.StockEntryParentModel import StockEntryParent
from core.ProductFolder.ProductModel import Product
from core.RawMaterialFolder.RawMaterialModel import RawMaterial
import re

bug_logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")


def get_accessible_person_fields(user):
    """بررسی دسترسی کاربر به فیلدهای Person"""
    if user.is_superuser:
        return {'name': True, 'national_id': True, 'description': True}
    
    accessible_fields = {}
    accessible_fields['name'] = check_field_access_prefer_edit(user, Person, 'name')
    accessible_fields['national_id'] = check_field_access_prefer_edit(user, Person, 'national_id')
    accessible_fields['description'] = check_field_access_prefer_edit(user, Person, 'description')
    return accessible_fields


def get_accessible_truck_info_fields(user):
    """بررسی دسترسی کاربر به فیلدهای TruckInfo"""
    if user.is_superuser:
        return {'plate_number': True, 'vehicle_type': True, 'loading_type': True}
    
    accessible_fields = {}
    accessible_fields['plate_number'] = check_field_access_prefer_edit(user, TruckInfo, 'plate_number')
    accessible_fields['vehicle_type'] = check_field_access_prefer_edit(user, TruckInfo, 'vehicle_type')
    accessible_fields['loading_type'] = check_field_access_prefer_edit(user, TruckInfo, 'loading_type')
    return accessible_fields


@login_required
def loading_exit_list_view(request):
    """
    لیست حمل‌های در انتظار بارگیری
    """
    audit_logger.info("درخواست مشاهده لیست حمل‌های در انتظار بارگیری")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_VIEW_LOADING_EXIT_LIST.value):
        audit_logger.activity("تلاش برای دسترسی به لیست خروج کالا بدون دسترسی")
        messages.error(request, 'شما دسترسی به مشاهده لیست خروج کالا را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    # دریافت حمل‌های در انتظار بارگیری
    transports = Transport.objects.filter(
        status='loading'
    ).select_related('driver', 'allocation', 'allocation__order').prefetch_related(
        'truck_infos', 'product_infos'
    ).order_by('-waybill_date', 'waybill_number')
    
    # آماده‌سازی اطلاعات حمل‌ها برای جدول
    # استفاده از یک class ساده که transport و اطلاعات مرتبط را نگه می‌دارد
    class TransportRow:
        def __init__(self, transport):
            self.transport = transport
            
            # دریافت اطلاعات کامیون
            truck_info = transport.truck_infos.first()
            self.plate_number = None
            self.vehicle_type = None
            if truck_info:
                self.plate_number = truck_info.plate_number
                self.vehicle_type = truck_info.get_vehicle_type_display() if truck_info.vehicle_type else None
            
            # اگر vehicle_type در TruckInfo وجود نداشت، از Transport.vehicle_type_official استفاده کن
            if not self.vehicle_type and transport.vehicle_type_official:
                self.vehicle_type = transport.get_vehicle_type_official_display()
            
            # دریافت اطلاعات محصول از ProductInfo
            product_name = None
            allocated_quantity = None
            unit = None
            
            # ابتدا از ProductInfo بررسی می‌کنیم
            product_info = transport.product_infos.first()
            if product_info:
                if product_info.product:
                    product_name = product_info.product.name
                elif product_info.raw_material:
                    product_name = product_info.raw_material.name
                if product_info.weight:
                    allocated_quantity = product_info.weight
                unit = 'کیلوگرم'
            
            self.product_name = product_name or 'نامشخص'
            self.allocated_quantity = allocated_quantity or 'نامشخص'
            self.unit = unit or 'کیلوگرم'
            
            # دریافت شماره سفارش
            order_number = None
            if transport.allocation:
                allocation = transport.allocation
                if allocation and allocation.order:
                    order_number = allocation.order.order_number if hasattr(allocation.order, 'order_number') else None
            
            self.order_number = order_number or 'نامشخص'
        
        def __getattr__(self, name):
            # اگر attribute در self وجود نداشت، از transport بگیر
            if hasattr(self.transport, name):
                return getattr(self.transport, name)
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    transports_data = [TransportRow(transport) for transport in transports]
    
    # ایجاد جدول
    table = LoadingExitTable(
        transports_data,
        accessible_fields=None,  # table خودش محاسبه می‌کند
        user=request.user
    )
    
    # تنظیم صفحه‌بندی
    RequestConfig(request, paginate={'per_page': 25}).configure(table)
    
    bug_logger.debug(f"تعداد {len(transports_data)} حمل در انتظار بارگیری لود شد")
    
    context = {
        'table': table,
        'page_title': 'لیست حمل‌های در انتظار بارگیری',
    }
    return render(request, 'distribution/loading_exit_list.html', context)


@login_required
def register_loading_exit_view(request, waybill_number):
    """
    ثبت خروج کالا
    """
    audit_logger.info(f"درخواست ثبت خروج کالا برای حمل {waybill_number}")
    
    if not user_has_task(request.user, TaskChoices.DISTRIBUTION_REGISTER_LOADING_EXIT.value):
        audit_logger.activity("تلاش برای ثبت خروج کالا بدون دسترسی")
        messages.error(request, 'شما دسترسی به ثبت خروج کالا را ندارید.')
        return HttpResponseForbidden('شما دسترسی به این بخش ندارید.')
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if transport.status != 'loading':
        messages.error(request, 'این حمل در وضعیت مناسب برای ثبت خروج کالا نیست.')
        return redirect('distribution:loading_exit_list')
    
    # دریافت انبار مشتری از طریق Allocation -> Order -> Customer
    customer_warehouse = None
    if transport.allocation:
        allocation = transport.allocation
        if allocation and allocation.order and allocation.order.customer:
            customer = allocation.order.customer
            if customer.warehouse:
                customer_warehouse = customer.warehouse
    
    # دریافت حساب‌های بانکی راننده
    driver_account_choices = []
    if transport.driver:
        financial_banking = FinancialBanking.objects.filter(person=transport.driver).first()
        if financial_banking:
            bank_accounts = BankAccount.objects.filter(financial_banking=financial_banking)
            for account in bank_accounts:
                account_display = f"{account.account_number}"
                if account.bank_name:
                    account_display += f" ({account.bank_name})"
                driver_account_choices.append((account.account_number, account_display))
    
    if request.method == 'POST':
        form = LoadingExitForm(request.POST)
        
        # تنظیم queryset و choices برای فیلدهای داینامیک قبل از اعتبارسنجی
        # انبار مقصد: انبار مشتری
        if customer_warehouse:
            form.fields['destination_warehouse'].queryset = Warehouse.objects.filter(
                pk=customer_warehouse.pk
            )
        else:
            form.fields['destination_warehouse'].queryset = Warehouse.objects.filter(
                warehouse_type='consumer'
            )
        
        # حساب‌های بانکی راننده
        if driver_account_choices:
            form.fields['driver_account_number'].choices = driver_account_choices
            form.fields['driver_account_number'].required = False
        else:
            form.fields['driver_account_number'].choices = [('', '-- حساب بانکی یافت نشد --')]
            form.fields['driver_account_number'].required = False
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # دریافت وزن خالی اولیه از فیلد جداگانه
                    empty_weight = request.POST.get('initial_empty_weight')
                    packaging_type = form.cleaned_data['packaging_type']
                    destination_warehouse_obj = form.cleaned_data['destination_warehouse']
                    driver_account_number = form.cleaned_data.get('driver_account_number', '').strip()
                    
                    if not empty_weight:
                        messages.error(request, 'وزن خالی اولیه وارد نشده است.')
                        return redirect('distribution:loading_exit_list')
                    
                    try:
                        empty_weight = float(empty_weight)
                    except (ValueError, TypeError):
                        messages.error(request, 'وزن خالی اولیه نامعتبر است.')
                        return redirect('distribution:loading_exit_list')
                    
                    if empty_weight <= 0:
                        messages.error(request, 'وزن خالی اولیه باید بزرگتر از صفر باشد.')
                        return redirect('distribution:loading_exit_list')
                    
                    # پردازش داده‌های مرحله‌ای بارگیری
                    # فرمت: loading_stages[0][product_info_id]=X&loading_stages[0][weight]=Y
                    product_infos_qs = transport.product_infos.all()
                    
                    # دریافت مراحل بارگیری از POST
                    loading_stages = []
                    stage_index = 0
                    while True:
                        product_info_id_key = f'loading_stages[{stage_index}][product_info_id]'
                        weight_key = f'loading_stages[{stage_index}][weight]'
                        origin_warehouse_key = f'loading_stages[{stage_index}][origin_warehouse_id]'
                        
                        product_info_id = request.POST.get(product_info_id_key)
                        weight = request.POST.get(weight_key)
                        origin_warehouse_id = request.POST.get(origin_warehouse_key)
                        
                        if not product_info_id or not weight:
                            break
                        
                        try:
                            product_info_id = int(product_info_id)
                            weight = float(weight)
                            origin_warehouse_id = int(origin_warehouse_id) if origin_warehouse_id else None
                            if weight > 0:
                                loading_stages.append({
                                    'product_info_id': product_info_id,
                                    'weight': weight,
                                    'origin_warehouse_id': origin_warehouse_id
                                })
                        except (ValueError, TypeError):
                            pass
                        
                        stage_index += 1
                    
                    if not loading_stages:
                        messages.error(request, 'حداقل یک مرحله بارگیری باید ثبت شود.')
                        return redirect('distribution:loading_exit_list')
                    
                    # محاسبه وزن‌های خالص هر محصول و وزن پر نهایی
                    product_info_data = {}  # {product_info_id: {'weight': net_weight, 'origin_warehouse_id': id}}
                    current_weight = float(empty_weight)
                    
                    for stage in loading_stages:
                        product_info_id = stage['product_info_id']
                        weight_after_loading = stage['weight']
                        origin_warehouse_id = stage.get('origin_warehouse_id')
                        
                        # بررسی اینکه انبار مبدأ انتخاب شده است
                        if not origin_warehouse_id:
                            messages.error(request, f'برای مرحله بارگیری، انتخاب انبار مبدأ الزامی است.')
                            return redirect('distribution:loading_exit_list')
                        
                        try:
                            origin_warehouse_obj = Warehouse.objects.get(pk=origin_warehouse_id)
                        except Warehouse.DoesNotExist:
                            messages.error(request, f'انبار مبدأ انتخاب شده معتبر نیست.')
                            return redirect('distribution:loading_exit_list')
                        
                        # وزن خالص این محصول = وزن بعد از بارگیری - وزن قبل از بارگیری
                        net_item_weight = weight_after_loading - current_weight
                        
                        if net_item_weight <= 0:
                            messages.error(request, f'وزن خالص محصول نامعتبر است. وزن بعد از بارگیری باید بیشتر از وزن قبلی باشد.')
                            return redirect('distribution:loading_exit_list')
                        
                        # بررسی اینکه این محصول قبلاً بارگیری نشده باشد
                        if product_info_id in product_info_data:
                            messages.error(request, 'هر محصول فقط یک بار می‌تواند بارگیری شود.')
                            return redirect('distribution:loading_exit_list')
                        
                        product_info_data[product_info_id] = {
                            'weight': net_item_weight,
                            'origin_warehouse_id': origin_warehouse_id,
                            'origin_warehouse_obj': origin_warehouse_obj
                        }
                        current_weight = weight_after_loading
                    
                    # وزن پر نهایی = آخرین وزن ثبت شده
                    gross_weight = current_weight
                    net_weight = float(gross_weight) - float(empty_weight)
                    
                    # بررسی اینکه همه محصولات بارگیری شده‌اند
                    if product_infos_qs.exists():
                        product_info_ids_in_stages = set(product_info_data.keys())
                        product_info_ids_in_transport = set(product_infos_qs.values_list('id', flat=True))
                        
                        if product_info_ids_in_stages != product_info_ids_in_transport:
                            missing = product_info_ids_in_transport - product_info_ids_in_stages
                            messages.error(request, f'همه محصولات باید بارگیری شوند. محصولات باقیمانده: {missing}')
                            return redirect('distribution:loading_exit_list')
                    
                    # بررسی اینکه انبار مقصد انتخاب شده است
                    if not destination_warehouse_obj:
                        messages.error(request, 'انتخاب انبار مقصد الزامی است.')
                        return redirect('distribution:loading_exit_list')
                    
                    # تبدیل انبار مقصد به نام (چون ProductInfo از CharField استفاده می‌کند)
                    destination_warehouse = destination_warehouse_obj.name if destination_warehouse_obj else ''
                    
                    
                    # اطلاعات اختیاری راننده
                    driver_national_id = form.cleaned_data.get('driver_national_id', '').strip()
                    driver_name = form.cleaned_data.get('driver_name', '').strip()
                    driver_mobile = form.cleaned_data.get('driver_mobile', '').strip()
                    driver_description = form.cleaned_data.get('driver_description', '').strip()
                    
                    # اطلاعات اختیاری حمل
                    plate_part1 = form.cleaned_data.get('plate_part1', '').strip()
                    plate_part2 = form.cleaned_data.get('plate_part2', '').strip()
                    plate_part3 = form.cleaned_data.get('plate_part3', '').strip()
                    plate_part4 = form.cleaned_data.get('plate_part4', '').strip()
                    vehicle_type = form.cleaned_data.get('vehicle_type', '').strip()
                    loading_type = form.cleaned_data.get('loading_type', '').strip()
                    
                    # اگر اطلاعات راننده ناقص است، تکمیل می‌کنیم
                    if not transport.driver and driver_national_id:
                        driver_person, created = Person.objects.get_or_create(
                            national_id=driver_national_id,
                            defaults={
                                'name': driver_name or None,
                                'type': 'driver',
                                'description': driver_description or None,
                            }
                        )
                        
                        if not created:
                            if driver_name:
                                driver_person.name = driver_name
                            if driver_description:
                                driver_person.description = driver_description
                            driver_person.type = 'driver'
                            driver_person.save()
                        
                        # اضافه یا به‌روزرسانی شماره همراه
                        if driver_mobile:
                            person_content_type = ContentType.objects.get_for_model(Person)
                            phone_number, created = PhoneNumber.objects.get_or_create(
                                content_type=person_content_type,
                                object_id=driver_person.national_id,
                                phone_type='mobile',
                                defaults={'number': driver_mobile, 'is_primary': True}
                            )
                            if not created:
                                phone_number.number = driver_mobile
                                phone_number.save()
                        
                        transport.driver = driver_person
                    
                    # اگر راننده وجود دارد، از حساب بانکی موجود استفاده می‌کنیم
                    if transport.driver and driver_account_number:
                        financial_banking, created = FinancialBanking.objects.get_or_create(
                            person=transport.driver
                        )
                        
                        # بررسی وجود حساب
                        bank_account = BankAccount.objects.filter(
                            financial_banking=financial_banking,
                            account_number=driver_account_number
                        ).first()
                        
                        if not bank_account:
                            # اگر حساب پیدا نشد، یک حساب جدید ایجاد می‌کنیم
                            BankAccount.objects.create(
                                financial_banking=financial_banking,
                                account_number=driver_account_number,
                                bank_name='نامشخص'
                            )
                    
                    # اگر اطلاعات کامیون ناقص است، تکمیل می‌کنیم
                    if plate_part1 and plate_part2 and plate_part3 and plate_part4:
                        # ساخت پلاک کامل با فرمت: 11|345ح12
                        # حرف در وسط: 3 رقم + حرف + 2 رقم
                        plate_middle = f"{plate_part2}{plate_part3}{plate_part4}"  # 345ح12
                        plate_number = f"{plate_part1}|{plate_middle}"  # 11|345ح12
                        
                        existing_truck = transport.truck_infos.first()
                        if existing_truck:
                            # به‌روزرسانی اطلاعات موجود
                            existing_truck.plate_number = plate_number
                            if vehicle_type:
                                existing_truck.vehicle_type = vehicle_type
                            if loading_type:
                                existing_truck.loading_type = loading_type
                            existing_truck.save()
                            truck_info = existing_truck
                        else:
                            truck_info = TruckInfo.objects.create(
                                plate_number=plate_number,
                                transport=transport,
                                vehicle_type=vehicle_type or None,
                                loading_type=loading_type or None,
                            )
                    
                    # به‌روزرسانی وزن‌های Transport
                    transport.gross_weight = gross_weight
                    transport.empty_weight = empty_weight
                    transport.net_weight = net_weight
                    transport.save(update_fields=['gross_weight', 'empty_weight', 'net_weight'])
                    
                    # به‌روزرسانی وزن خالص هر ProductInfo و انبار مبدأ مربوط به آن
                    for product_info in product_infos_qs:
                        product_data = product_info_data.get(product_info.id)
                        if product_data and product_data['weight'] > 0:
                            # ذخیره وزن خالص محاسبه شده از توزین مرحله‌ای
                            product_info.net_weight = product_data['weight']
                            product_info.packaging_type = packaging_type
                            # تبدیل انبارها به نام (چون ProductInfo از CharField استفاده می‌کند)
                            if product_data['origin_warehouse_obj']:
                                product_info.origin_warehouse = product_data['origin_warehouse_obj'].name
                            if destination_warehouse_obj:
                                product_info.destination_warehouse = destination_warehouse_obj.name
                            product_info.save(update_fields=['net_weight', 'packaging_type', 'origin_warehouse', 'destination_warehouse'])
                    
                    # ایجاد StockEntry برای commit موجودی انبار
                    # گروه‌بندی ProductInfoها بر اساس انبار مبدأ و ایجاد StockEntry جداگانه برای هر انبار
                    product_infos = transport.product_infos.all()
                    if product_infos.exists() and destination_warehouse_obj:
                        # دریافت ContentType برای Product و RawMaterial
                        product_ct = ContentType.objects.get_for_model(Product)
                        raw_material_ct = ContentType.objects.get_for_model(RawMaterial)
                        
                        # گروه‌بندی ProductInfoها بر اساس انبار مبدأ
                        product_infos_by_origin = {}
                        for product_info in product_infos:
                            # استفاده از net_weight اگر موجود باشد، در غیر این صورت از weight
                            product_weight_check = product_info.net_weight if product_info.net_weight else (product_info.weight or 0)
                            if product_weight_check <= 0:
                                continue
                            
                            # دریافت انبار مبدأ از product_info_data
                            product_data = product_info_data.get(product_info.id)
                            if not product_data:
                                continue
                            
                            origin_warehouse_obj = product_data['origin_warehouse_obj']
                            if not origin_warehouse_obj:
                                continue
                            
                            if origin_warehouse_obj.id not in product_infos_by_origin:
                                product_infos_by_origin[origin_warehouse_obj.id] = {
                                    'warehouse': origin_warehouse_obj,
                                    'product_infos': []
                                }
                            
                            product_infos_by_origin[origin_warehouse_obj.id]['product_infos'].append(product_info)
                        
                        # ایجاد StockEntry جداگانه برای هر انبار مبدأ
                        for origin_warehouse_id, origin_data in product_infos_by_origin.items():
                            origin_warehouse_obj = origin_data['warehouse']
                            origin_product_infos = origin_data['product_infos']
                            
                            # ایجاد یک StockEntry برای این انبار مبدأ
                            stock_entry = StockEntry.objects.create(
                                transaction_date=timezone.now(),
                                entry_type=StockEntry.StockEntryType.SALE,
                                notes=f'خروج کالا برای حمل {waybill_number} - انتقال از انبار {origin_warehouse_obj.name} به انبار {destination_warehouse_obj.name}',
                                is_committed=False
                            )
                            
                            # پردازش هر ProductInfo در این انبار مبدأ
                            for product_info in origin_product_infos:
                                # تعیین نوع آیتم (محصول یا مواد اولیه)
                                item = None
                                is_product = False
                                content_type = None
                                
                                if product_info.product:
                                    item = product_info.product
                                    is_product = True
                                    content_type = product_ct
                                elif product_info.raw_material:
                                    item = product_info.raw_material
                                    is_product = False
                                    content_type = raw_material_ct
                                
                                if not item or not content_type:
                                    bug_logger.warning(f"ProductInfo {product_info.id} برای حمل {waybill_number} فاقد محصول یا مواد اولیه است")
                                    continue
                                
                                # استفاده از net_weight اگر موجود باشد، در غیر این صورت از weight
                                product_weight = product_info.net_weight if product_info.net_weight else (product_info.weight or 0)
                                
                                if product_weight <= 0:
                                    continue
                                
                                
                                # -------------------------------------------------------------------------
                                # FIFO Tracing: Link to Parent (Production/Purchase) Entries
                                # -------------------------------------------------------------------------
                                try:
                                    remaining_needed = product_weight
                                    
                                    # Find valid parent candidates:
                                    # 1. Production (Finished Good) or Purchase (Trading) or Opening
                                    # 2. Must contain the specific Item (TargetStock matches matches to_object_id)
                                    # 3. Must be in the SOURCE warehouse
                                    # 4. Must be committed
                                    candidates = StockEntry.objects.filter(
                                        entry_type__in=[
                                            StockEntry.StockEntryType.PRODUCTION, 
                                            StockEntry.StockEntryType.PURCHASE,
                                            StockEntry.StockEntryType.OPENING,
                                            StockEntry.StockEntryType.RETURN_IN
                                        ],
                                        target_stocks__to_content_type=content_type,
                                        target_stocks__to_object_id=item.id,
                                        target_stocks__to_warehouse=origin_warehouse_obj,
                                        is_committed=True
                                    ).distinct().order_by('transaction_date')

                                    for candidate in candidates:
                                        if remaining_needed <= 0:
                                            break
                                            
                                        # Check how much is available in this parent entry
                                        available = candidate.get_remaining_quantity()
                                        if available <= 0:
                                            continue
                                        
                                        take = min(remaining_needed, available)
                                        
                                        # Create or Update Link
                                        link, created_link = StockEntryParent.objects.get_or_create(
                                            parent=candidate,
                                            child=stock_entry,
                                            defaults={'quantity': 0}
                                        )
                                        # Use F expression to avoid race condition if possible, but we need 'take' value
                                        link.quantity = models.F('quantity') + take
                                        link.save()
                                        
                                        remaining_needed -= take
                                        bug_logger.info(f"FIFO Sales: Took {take} from Parent {candidate.id} for {item.name} from warehouse {origin_warehouse_obj.name}")

                                except Exception as e:
                                    bug_logger.warning(f"FIFO Tracing failed for sale of {item.name} from warehouse {origin_warehouse_obj.name}: {e}")
                                # -------------------------------------------------------------------------
                                
                                # ایجاد SourceStock (کاهش از انبار مبدا)
                                SourceStock.objects.create(
                                    stock_entry=stock_entry,
                                    from_content_type=content_type,
                                    from_object_id=item.id,
                                    from_warehouse=origin_warehouse_obj,
                                    quantity=product_weight
                                )
                                
                                # ایجاد TargetStock (افزایش به انبار مقصد)
                                TargetStock.objects.create(
                                    stock_entry=stock_entry,
                                    to_content_type=content_type,
                                    to_object_id=item.id,
                                    to_warehouse=destination_warehouse_obj,
                                    quantity=product_weight
                                )
                            
                            # Commit کردن StockEntry برای اعمال تغییرات در موجودی انبار
                            try:
                                stock_entry.commit()
                                bug_logger.info(f"StockEntry {stock_entry.id} برای حمل {waybill_number} از انبار {origin_warehouse_obj.name} با موفقیت commit شد")
                            except Exception as e:
                                bug_logger.error(f"خطا در commit کردن StockEntry {stock_entry.id} برای حمل {waybill_number} از انبار {origin_warehouse_obj.name}: {str(e)}")
                                raise
                    
                    # ثبت زمان خروج خودرو
                    schedule_info, created = LoadingScheduleInfo.objects.get_or_create(
                        transport=transport
                    )
                    schedule_info.vehicle_exit_time = timezone.now()
                    schedule_info.save(update_fields=['vehicle_exit_time'])
                    
                    # تغییر وضعیت حمل به pending_waybill (در انتظار بارنامه)
                    transport.status = 'pending_waybill'
                    transport.loading_date = timezone.now().date()
                    transport.save()
                    
                    # بررسی تغییر وضعیت تخصیص
                    if transport.allocation:
                        allocation = transport.allocation
                        if allocation and allocation.allocation_status == 'pending_vehicle_recruitment':
                            # بررسی اینکه آیا همه حمل‌های تخصیص به pending_waybill رسیدند
                            all_transports = Transport.objects.filter(allocation=allocation)
                            all_transports_count = all_transports.count()
                            pending_waybill_transports_count = all_transports.filter(status='pending_waybill').count()
                            
                            # اگر همه حمل‌ها به pending_waybill رسیدند، تخصیص را به pending_loading_completion ببر
                            if all_transports_count > 0 and all_transports_count == pending_waybill_transports_count:
                                allocation.allocation_status = 'pending_loading_completion'
                                allocation.save(update_fields=['allocation_status'])
                                bug_logger.info(f"وضعیت تخصیص {allocation.allocation_number} به 'در انتظار تکمیل بارگیری‌های تخصیص' تغییر کرد")
                                
                    bug_logger.info(f"خروج کالا برای حمل {waybill_number} ثبت شد")
                    messages.success(request, f'خروج کالا برای حمل {waybill_number} با موفقیت ثبت شد.')
                    audit_logger.activity(f"خروج کالا برای حمل {waybill_number} ثبت شد توسط کاربر {request.user.username}")
                    
                    return redirect('distribution:loading_exit_list')
                    
            except Exception as e:
                bug_logger.error(f"خطا در ثبت خروج کالا: {str(e)}")
                messages.error(request, f'خطا در ثبت خروج کالا: {str(e)}')
        else:
            # نمایش خطاهای فرم
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            
            # تنظیم مجدد queryset و choices برای نمایش فرم با خطا
            # این تنظیمات قبلاً انجام شده، اما برای اطمینان دوباره انجام می‌دهیم
            if customer_warehouse:
                form.fields['destination_warehouse'].queryset = Warehouse.objects.filter(
                    pk=customer_warehouse.pk
                )
            else:
                form.fields['destination_warehouse'].queryset = Warehouse.objects.filter(
                    warehouse_type='consumer'
                )
            
            if driver_account_choices:
                form.fields['driver_account_number'].choices = driver_account_choices
                form.fields['driver_account_number'].required = False
            else:
                form.fields['driver_account_number'].choices = [('', '-- حساب بانکی یافت نشد --')]
                form.fields['driver_account_number'].required = False
                form.fields['driver_account_number'].widget.attrs.pop('disabled', None)
            
            # آماده‌سازی context برای نمایش مجدد فرم با خطا
            driver_name = None
            driver_national_id = None
            driver_mobile = None
            if transport.driver:
                driver_name = transport.driver.name
                driver_national_id = transport.driver.national_id
                person_content_type = ContentType.objects.get_for_model(Person)
                mobile_phone = PhoneNumber.objects.filter(
                    content_type=person_content_type,
                    object_id=transport.driver.national_id,
                    phone_type='mobile'
                ).first()
                if mobile_phone:
                    driver_mobile = mobile_phone.number
            
            truck_info = transport.truck_infos.first()
            plate_number = None
            vehicle_type = None
            if truck_info:
                plate_number = truck_info.plate_number
                vehicle_type = truck_info.get_vehicle_type_display() if truck_info.vehicle_type else None
            
            # دریافت اطلاعات محصول - همه ProductInfoها
            product_infos = transport.product_infos.all()
            product_info_list = []
            product_name = None
            
            for product_info in product_infos:
                item_name = None
                item_type_display = None
                
                if product_info.product:
                    item_name = product_info.product.name
                    item_type_display = 'محصول'
                elif product_info.raw_material:
                    item_name = product_info.raw_material.name
                    item_type_display = 'مواد اولیه'
                
                if item_name:
                    packaging_type_display = product_info.get_packaging_type_display() if product_info.packaging_type else None
                    product_info_list.append({
                        'id': product_info.id,
                        'name': item_name,
                        'weight': product_info.weight,
                        'packaging_type': packaging_type_display,
                        'item_type': item_type_display,
                        'unit': 'کیلوگرم',
                    })
            
            # برای سازگاری با کد قبلی، اولین محصول را به عنوان product_name نگه می‌داریم
            if product_info_list:
                product_name = product_info_list[0]['name']
            elif product_infos.exists():
                product_name = 'نامشخص'
            
            order_number = None
            if transport.allocation:
                allocation = transport.allocation
                if allocation and allocation.order:
                    order_number = allocation.order.order_number if hasattr(allocation.order, 'order_number') else None
            
            accessible_person_fields = get_accessible_person_fields(request.user)
            
            context = {
                'form': form,
                'transport': transport,
                'driver_name': driver_name,
                'driver_national_id': driver_national_id,
                'driver_mobile': driver_mobile,
                'plate_number': plate_number,
                'vehicle_type': vehicle_type,
                'product_name': product_name or 'نامشخص',
                'product_info_list': product_info_list,
                'order_number': order_number or 'نامشخص',
                'accessible_person_fields': accessible_person_fields,
                'page_title': f'ثبت خروج کالا - {transport.waybill_number}',
            }
            return render(request, 'distribution/loading_exit_detail.html', context)
    else:
        # برای GET request، فرم را با داده‌های موجود پر می‌کنیم
        initial_data = {}
        
        # دریافت انبار مشتری از طریق Allocation -> Order -> Customer
        customer_warehouse = None
        if transport.allocation:
            allocation = transport.allocation
            if allocation and allocation.order and allocation.order.customer:
                customer = allocation.order.customer
                if customer.warehouse:
                    customer_warehouse = customer.warehouse
        
        # دریافت اطلاعات ProductInfo موجود
        product_info = transport.product_infos.first()
        if product_info:
            initial_data['packaging_type'] = product_info.packaging_type
            
            if product_info.destination_warehouse and customer_warehouse:
                if product_info.destination_warehouse == customer_warehouse.name:
                    initial_data['destination_warehouse'] = customer_warehouse
            elif customer_warehouse:
                initial_data['destination_warehouse'] = customer_warehouse
        
        # تنظیم وزن خالی اولیه از Transport.empty_weight
        if transport.empty_weight:
            initial_data['initial_empty_weight'] = transport.empty_weight
        
        # اگر انبار مقصد در initial_data نیست، از انبار مشتری استفاده می‌کنیم
        if 'destination_warehouse' not in initial_data and customer_warehouse:
            initial_data['destination_warehouse'] = customer_warehouse
        
        # دریافت اطلاعات راننده
        driver_account_choices = []
        if transport.driver:
            initial_data['driver_national_id'] = transport.driver.national_id
            initial_data['driver_name'] = transport.driver.name
            initial_data['driver_description'] = transport.driver.description
            
            person_content_type = ContentType.objects.get_for_model(Person)
            mobile_phone = PhoneNumber.objects.filter(
                content_type=person_content_type,
                object_id=transport.driver.national_id,
                phone_type='mobile'
            ).first()
            if mobile_phone:
                initial_data['driver_mobile'] = mobile_phone.number
            
            # دریافت حساب‌های بانکی راننده
            financial_banking = FinancialBanking.objects.filter(person=transport.driver).first()
            if financial_banking:
                bank_accounts = BankAccount.objects.filter(financial_banking=financial_banking)
                for account in bank_accounts:
                    account_display = f"{account.account_number}"
                    if account.bank_name:
                        account_display += f" ({account.bank_name})"
                    driver_account_choices.append((account.account_number, account_display))
                
                # اگر حساب وجود دارد، اولین حساب را به عنوان پیش‌فرض انتخاب می‌کنیم
                if bank_accounts.exists():
                    initial_data['driver_account_number'] = bank_accounts.first().account_number
        
        # دریافت اطلاعات کامیون
        truck_info = transport.truck_infos.first()
        if truck_info:
            plate_parts = truck_info.plate_number.split('|')
            if len(plate_parts) == 2:
                plate_part1 = plate_parts[0]  # 11
                plate_middle = plate_parts[1]  # 345ح12
                
                # استخراج حرف و اعداد از وسط: 345ح12 -> 345 و ح و 12
                # فرمت: 3 رقم + حرف + 2 رقم
                plate_middle_match = re.match(r'^(\d{3})([ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی])(\d{2})$', plate_middle)
                if plate_middle_match:
                    initial_data['plate_part1'] = plate_part1
                    initial_data['plate_part2'] = plate_middle_match.group(1)  # 345
                    initial_data['plate_part3'] = plate_middle_match.group(2)  # ح
                    initial_data['plate_part4'] = plate_middle_match.group(3)   # 12
            initial_data['vehicle_type'] = truck_info.vehicle_type
            initial_data['loading_type'] = truck_info.loading_type
        
        # ایجاد فرم با مقداردهی اولیه
        form = LoadingExitForm(initial=initial_data)
        
        # تنظیم queryset و choices برای فیلدهای داینامیک
        # انبار مقصد: انبار مشتری
        if customer_warehouse:
            form.fields['destination_warehouse'].queryset = Warehouse.objects.filter(
                pk=customer_warehouse.pk
            )
        else:
            form.fields['destination_warehouse'].queryset = Warehouse.objects.filter(
                warehouse_type='consumer'
            )
        
        # حساب‌های بانکی راننده
        if driver_account_choices:
            form.fields['driver_account_number'].choices = driver_account_choices
            form.fields['driver_account_number'].required = False
        else:
            # اگر حساب وجود ندارد، فیلد را اختیاری می‌کنیم
            form.fields['driver_account_number'].choices = [('', '-- حساب بانکی یافت نشد --')]
            form.fields['driver_account_number'].required = False
            form.fields['driver_account_number'].widget.attrs['disabled'] = True
    
    # آماده‌سازی اطلاعات برای نمایش
    driver_name = None
    driver_national_id = None
    driver_mobile = None
    if transport.driver:
        driver_name = transport.driver.name
        driver_national_id = transport.driver.national_id
        person_content_type = ContentType.objects.get_for_model(Person)
        mobile_phone = PhoneNumber.objects.filter(
            content_type=person_content_type,
            object_id=transport.driver.national_id,
            phone_type='mobile'
        ).first()
        if mobile_phone:
            driver_mobile = mobile_phone.number
    
    truck_info = transport.truck_infos.first()
    plate_number = None
    vehicle_type = None
    if truck_info:
        plate_number = truck_info.plate_number
        vehicle_type = truck_info.get_vehicle_type_display() if truck_info.vehicle_type else None
    
    # اگر vehicle_type در TruckInfo وجود نداشت، از Transport.vehicle_type_official استفاده کن
    if not vehicle_type and transport.vehicle_type_official:
        vehicle_type = transport.get_vehicle_type_official_display()
    
    # دریافت اطلاعات محصول - همه ProductInfoها
    product_infos = transport.product_infos.all()
    product_info_list = []
    product_name = None
    
    for product_info in product_infos:
        item_name = None
        item_type_display = None
        
        if product_info.product:
            item_name = product_info.product.name
            item_type_display = 'محصول'
        elif product_info.raw_material:
            item_name = product_info.raw_material.name
            item_type_display = 'مواد اولیه'
        
        if item_name:
            packaging_type_display = product_info.get_packaging_type_display() if product_info.packaging_type else None
            product_info_list.append({
                'id': product_info.id,
                'name': item_name,
                'weight': product_info.weight,
                'packaging_type': packaging_type_display,
                'item_type': item_type_display,
                'unit': 'کیلوگرم',
            })
    
    # برای سازگاری با کد قبلی، اولین محصول را به عنوان product_name نگه می‌داریم
    if product_info_list:
        product_name = product_info_list[0]['name']
    elif product_infos.exists():
        # اگر ProductInfo وجود دارد اما محصول مشخص نیست
        product_name = 'نامشخص'
    
    # دریافت شماره سفارش
    order_number = None
    if transport.allocation:
        allocation = transport.allocation
        if allocation and allocation.order:
            order_number = allocation.order.order_number if hasattr(allocation.order, 'order_number') else None
    
    # بررسی دسترسی فیلدها
    accessible_person_fields = get_accessible_person_fields(request.user)
    
    # دریافت لیست انبارهای مبدأ (انبارهای ثانویه)
    origin_warehouses = Warehouse.objects.filter(warehouse_type='secondary').order_by('name')
    
    context = {
        'form': form,
        'transport': transport,
        'driver_name': driver_name,
        'driver_national_id': driver_national_id,
        'driver_mobile': driver_mobile,
        'plate_number': plate_number,
        'vehicle_type': vehicle_type,
        'product_name': product_name or 'نامشخص',
        'product_info_list': product_info_list,
        'order_number': order_number or 'نامشخص',
        'accessible_person_fields': accessible_person_fields,
        'origin_warehouses': origin_warehouses,
        'page_title': f'ثبت خروج کالا - {transport.waybill_number}',
    }
    return render(request, 'distribution/loading_exit_detail.html', context)


@login_required
def create_bank_account_ajax_view(request, waybill_number):
    """
    ایجاد حساب بانکی جدید با AJAX
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'فقط POST مجاز است'}, status=405)
    
    transport = get_object_or_404(Transport, waybill_number=waybill_number)
    
    if not transport.driver:
        return JsonResponse({'success': False, 'error': 'راننده برای این حمل تعریف نشده است'}, status=400)
    
    account_number = request.POST.get('account_number', '').strip()
    shaba_number = request.POST.get('shaba_number', '').strip()
    bank_name = request.POST.get('bank_name', '').strip()
    
    # اعتبارسنجی
    if not account_number:
        return JsonResponse({'success': False, 'error': 'شماره حساب الزامی است'}, status=400)
    
    # اعتبارسنجی شماره حساب (16 رقم)
    if not re.match(r'^\d{16}$', account_number):
        return JsonResponse({'success': False, 'error': 'شماره حساب باید دقیقاً 16 رقم باشد'}, status=400)
    
    if not bank_name:
        return JsonResponse({'success': False, 'error': 'نام بانک الزامی است'}, status=400)
    
    # اعتبارسنجی شماره شبا
    if shaba_number:
        if not re.match(r'^IR\d{24}$', shaba_number):
            return JsonResponse({'success': False, 'error': 'شماره شبا باید با فرمت IR123456789012345678901234 باشد (IR + 24 رقم)'}, status=400)
    
    try:
        with transaction.atomic():
            # دریافت یا ایجاد FinancialBanking
            financial_banking, created = FinancialBanking.objects.get_or_create(
                person=transport.driver
            )
            
            # بررسی تکراری نبودن شماره حساب
            existing_account = BankAccount.objects.filter(
                financial_banking=financial_banking,
                account_number=account_number
            ).first()
            
            if existing_account:
                return JsonResponse({'success': False, 'error': 'این شماره حساب قبلاً ثبت شده است'}, status=400)
            
            # ایجاد حساب جدید
            bank_account = BankAccount.objects.create(
                financial_banking=financial_banking,
                account_number=account_number,
                shaba_number=shaba_number or None,
                bank_name=bank_name
            )
            
            # آماده‌سازی پاسخ
            account_display = f"{bank_account.account_number}"
            if bank_account.bank_name:
                account_display += f" ({bank_account.bank_name})"
            
            return JsonResponse({
                'success': True,
                'account_number': bank_account.account_number,
                'account_display': account_display,
                'message': 'حساب با موفقیت ایجاد شد'
            })
            
    except Exception as e:
        bug_logger.error(f"خطا در ایجاد حساب بانکی: {str(e)}")
        return JsonResponse({'success': False, 'error': f'خطا در ایجاد حساب: {str(e)}'}, status=500)

