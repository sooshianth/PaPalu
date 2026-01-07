from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django_jalali.db import models as jmodels
from core.PersonFolder import Person


class Order(models.Model):
    """مدل سفارش"""

    ORDER_TYPE_CHOICES = [
        ('purchase', 'خرید'),
        ('sale', 'فروش'),
    ]
    
    SOURCE_CHOICES = [
        ('api', 'API'),
        ('expert', 'کارشناس'),
    ]
    
    STATUS_CHOICES = [
        # وضعیت‌های سفارش فروش
        ('pending_proforma_issue', 'در انتظار صدور پیش فاکتور'),
        ('pending_customer_proforma_upload', 'در انتظار آپلود پیش فاکتور مشتری'),
        # بعد از آپلود تأیید پیش فاکتور، سفارش به این وضعیت می‌رود
        ('pending_transaction_receipt_upload', 'در انتظار بارگذاری رسید تراکنش'),
        # بعد از تکمیل بارگذاری رسیدها، سفارش به این وضعیت می‌رود
        ('pending_accounting_approval', 'در انتظار تایید حسابداری'),
        ('pending_allocation', 'در انتظار تخصیص'),
        ('pending_allocation_approval', 'در انتظار تأیید تخصیص'),
        ('pending_factory', 'در انتظار کارخانه'),
        ('pending_unloading_approval', 'در انتظار تایید تخلیه'),
        ('pending_settlement', 'در انتظار تسویه'),
        ('pending_settlement_approval', 'در انتظار تایید تسویه کامل'),
        # وضعیت‌های سفارش خرید تامینی
        ('draft', 'پیش‌نویس'),
        ('awaiting_transport_def', 'در انتظار تعریف حمل'),
        ('awaiting_vehicle_entry', 'در انتظار ورود خودرو'),
        ('awaiting_delivery', 'در انتظار تحویل بار'),
        ('awaiting_wh_reconciliation', 'در انتظار تطبیق اطلاعات انبار'),
        ('awaiting_final_settlement', 'در انتظار تسویه نهایی'),
        ('completed', 'تکمیل سفارش'),
        # وضعیت‌های مشترک
        ('cancelled', 'لغو شده'),
        ('archived', 'بایگانی شده'),
    ]
    
    FREIGHT_PAYMENT_CHOICES = [
        ('calculated_in_invoice', 'کرایه محاسبه شده در فی'),
        ('pay_to_supplier', 'پرداخت به شرکت فروشنده'),
        ('pay_to_driver', 'پرداخت به راننده'),
    ]
    
    
    # شماره سفارش
    order_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='شماره سفارش'
    )
    
    # مشتری/تامین‌کننده (بسته به نوع سفارش)
    customer = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name='orders',
        verbose_name='مشتری/تامین‌کننده',
        null=True,
        blank=True,
        help_text='برای سفارش فروش: مشتری، برای سفارش خرید: تامین‌کننده'
    )
    
    # نوع سفارش(خرید/فروش)
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='نوع سفارش'
    )
    
    # منبع ثبت سفارش (api/کارشناس)
    registration_source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        null=True,
        blank=True,
        verbose_name='منبع ثبت سفارش'
    )
    
    # وضعیت
    status = models.CharField(
        max_length=100,
        choices=STATUS_CHOICES,
        default='pending',
        null=True,
        blank=True,
        verbose_name='وضعیت'
    )
    
    # تاریخ ایجاد
    creation_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name='تاریخ ایجاد'
    )
    
    # کاربر ثبت کننده
    registered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_orders',
        verbose_name='کاربر ثبت کننده'
    )
    
    # نوع پرداخت کرایه
    freight_payment_type = models.CharField(
        max_length=30,
        choices=FREIGHT_PAYMENT_CHOICES,
        null=True,
        blank=True,
        verbose_name='نوع پرداخت کرایه'
    )
    
    # وزن کل ارسال (محاسبه شده از اقلام)
    total_shipment_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل ارسال',
        help_text='مجموع وزن اقلام ارسال شده'
    )
    
    # وزن کل تحویل (محاسبه شده از اقلام)
    total_delivery_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='وزن کل تحویل',
        help_text='مجموع وزن اقلام تحویل شده'
    )
    
    # شماره سند حسابداری ثبت شده
    accounting_document_number = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='شماره سند حسابداری ثبت شده'
    )
    
    # فیلدهای مربوط به سفارش خرید تامینی
    subtotal_without_freight = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        verbose_name='جمع قیمت بدون کرایه',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    freight_cost = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        verbose_name='هزینه کرایه',
        validators=[MinValueValidator(0)],
        null=True,
        blank=True
    )
    vat_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='درصد مالیات بر ارزش افزوده',
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    payment_confirmed = models.BooleanField(
        default=False,
        verbose_name='پرداخت تایید شده'
    )
    pre_invoice_file = models.FileField(
        upload_to='procurement/preinvoices/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='فایل پیش‌فاکتور'
    )
    pre_invoice_approved = models.BooleanField(
        default=False,
        verbose_name='پیش‌فاکتور تایید شد'
    )
    external_system_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='شناسه یکتا در سیستم دامپروش/کی‌اچ/انبار/لبه‌ژنت'
    )
    
    # فی تمام شده خرید (محاسبه شده پس از تکمیل سفارش)
    final_unit_price = models.DecimalField(
        max_digits=50,
        decimal_places=2,
        verbose_name='فی تمام شده خرید (ریال/کیلوگرم)',
        null=True,
        blank=True,
        help_text='محاسبه شده: (هزینه پرداخت اولیه + مجموع کرایه‌های حمل‌ها) / (مجموع وزن‌های خالص حمل‌ها)'
    )
    
    # Timestamps
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد',
        null=True,
        blank=True
    )
    
    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name='تاریخ بروزرسانی',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'سفارش | سفارش ها'
        verbose_name_plural = 'سفارش | سفارش ها'
        ordering = ['-created_at']
    
    def __str__(self):
        customer_name = self.customer.name if self.customer else 'بدون مشتری'
        return f"{self.order_number} - {customer_name} - {self.get_order_type_display()}"
    
    @property
    def supplier(self):
        """Property برای سازگاری با کد قدیمی - برمی‌گرداند customer"""
        return self.customer
    
    @property
    def materials(self):
        """Property برای سازگاری با کد قدیمی - برمی‌گرداند order_items"""
        return self.order_items
    
    @property
    def transports(self):
        """Property برای سازگاری با کد قدیمی - برمی‌گرداند transports از طریق allocations"""
        from core.TransportFolder.TransportModel import Transport
        return Transport.objects.filter(allocation__order=self)
    
    def get_total_amount(self):
        """
        محاسبه مبلغ کل سفارش از مجموع اقلام
        """
        from django.db.models import Sum
        total = self.order_items.aggregate(total=Sum('total_purchase_cost'))['total']
        return total or 0
    
    def is_fully_allocated(self):
        """
        بررسی اینکه آیا تمام مواد اولیه سفارش به حمل‌ها تخصیص داده شده‌اند
        """
        for item in self.order_items.all():
            if not item.is_fully_allocated():
                return False
        return True
    
    def get_total_order_weight(self):
        """
        محاسبه مجموع وزن تمام مواد اولیه سفارش (به کیلوگرم)
        """
        from decimal import Decimal
        total_weight = Decimal('0')
        for item in self.order_items.all():
            total_weight += Decimal(str(item.get_weight_in_kg()))
        return total_weight
    
    def get_total_allocated_weight(self):
        """
        محاسبه مجموع وزن تخصیص یافته در تمام حمل‌ها (به کیلوگرم)
        """
        from decimal import Decimal
        total_weight = Decimal('0')
        for item in self.order_items.all():
            # تبدیل مقدار تخصیص یافته به کیلوگرم بر اساس واحد
            allocated = item.get_allocated_quantity()
            if item.weight_unit == 'kg':
                total_weight += allocated
            elif item.weight_unit == 'ton':
                total_weight += allocated * Decimal('1000')
            elif item.weight_unit == 'bag' and item.bag_weight:
                total_weight += allocated * Decimal(str(item.bag_weight))
            elif item.weight_unit == 'piece':
                total_weight += allocated
        return total_weight
    
    def get_remaining_weight(self):
        """
        محاسبه وزن باقیمانده برای تخصیص (به کیلوگرم)
        """
        return self.get_total_order_weight() - self.get_total_allocated_weight()
    
    def can_create_transport(self):
        """
        بررسی امکان ایجاد حمل جدید - اگر هنوز مواد اولیه تخصیص نیافته وجود داشته باشد
        """
        return self.get_remaining_weight() > 0
    
    def _calculate_final_unit_price(self):
        """
        محاسبه فی تمام شده خرید پس از تکمیل سفارش
        فرمول: (هزینه پرداخت اولیه + مجموع کرایه‌های هر حمل) / (مجموع وزن‌های خالص حمل‌ها)
        این متد برای استفاده داخلی است و مقدار را محاسبه می‌کند
        """
        from decimal import Decimal
        from django.db.models import Sum
        
        # فقط برای سفارش‌های خرید و فقط وقتی که سفارش تکمیل شده است
        if self.order_type != 'purchase' or self.status != self.STATUS_COMPLETED:
            return None
        
        # هزینه پرداخت اولیه
        initial_payment = self.subtotal_without_freight or Decimal('0')
        
        # مجموع کرایه‌های حمل‌ها
        from core.TransportFolder.TransportModel import Transport
        transports = Transport.objects.filter(allocation__order=self)
        
        # استفاده از total_freight اگر موجود باشد، در غیر این صورت از freight_payment
        total_freight = Decimal('0')
        for transport in transports:
            if transport.total_freight:
                total_freight += transport.total_freight
            elif transport.freight_payment:
                total_freight += transport.freight_payment
        
        # مجموع وزن‌های خالص حمل‌ها
        # ابتدا سعی می‌کنیم از net_weight در Transport استفاده کنیم
        total_net_weight = transports.aggregate(
            total=Sum('net_weight')
        )['total'] or Decimal('0')
        
        # اگر net_weight در Transport نبود، از RawMaterialInfo استفاده می‌کنیم
        if total_net_weight == 0:
            from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
            total_net_weight = RawMaterialInfo.objects.filter(
                transport__allocation__order=self
            ).aggregate(
                total=Sum('net_weight')
            )['total'] or Decimal('0')
        
        # اگر وزن خالص صفر باشد، نمی‌توانیم تقسیم کنیم
        if total_net_weight == 0:
            return None
        
        # محاسبه فی تمام شده خرید
        total_cost = initial_payment + total_freight
        final_unit_price = total_cost / total_net_weight
        
        # گرد کردن به 2 رقم اعشار
        return final_unit_price.quantize(Decimal('0.01'))
    
    def get_final_unit_price(self):
        """
        دریافت فی تمام شده خرید از فیلد ذخیره شده
        اگر فیلد خالی باشد و سفارش تکمیل شده است، محاسبه و ذخیره می‌کند
        """
        # اگر فیلد ذخیره شده وجود دارد، از آن استفاده کن
        if self.final_unit_price is not None:
            return self.final_unit_price
        
        # اگر فیلد خالی است و سفارش تکمیل شده است، محاسبه و ذخیره کن
        if self.order_type == 'purchase' and self.status == self.STATUS_COMPLETED:
            calculated_price = self._calculate_final_unit_price()
            if calculated_price is not None:
                # ذخیره بدون فراخوانی save برای جلوگیری از حلقه بی‌نهایت
                Order.objects.filter(pk=self.pk).update(final_unit_price=calculated_price)
                self.final_unit_price = calculated_price
                return calculated_price
        
        return None
    
    def get_final_unit_price_details(self):
        """
        دریافت جزئیات محاسبه فی تمام شده خرید
        شامل: قیمت اول پرداختی، مجموع کرایه‌ها، مجموع وزن خالص حمل‌ها، وزن سفارش
        """
        from decimal import Decimal
        from django.db.models import Sum
        
        # فقط برای سفارش‌های خرید
        if self.order_type != 'purchase':
            return None
        
        # قیمت اول پرداختی
        initial_payment = self.subtotal_without_freight or Decimal('0')
        
        # مجموع کرایه‌های حمل‌ها
        from core.TransportFolder.TransportModel import Transport
        transports = Transport.objects.filter(allocation__order=self)
        
        total_freight = Decimal('0')
        for transport in transports:
            if transport.total_freight:
                total_freight += transport.total_freight
            elif transport.freight_payment:
                total_freight += transport.freight_payment
        
        # مجموع وزن‌های خالص حمل‌ها
        total_net_weight = transports.aggregate(
            total=Sum('net_weight')
        )['total'] or Decimal('0')
        
        # اگر net_weight در Transport نبود، از RawMaterialInfo استفاده می‌کنیم
        if total_net_weight == 0:
            from core.TransportFolder.RawMaterialInfoModel import RawMaterialInfo
            total_net_weight = RawMaterialInfo.objects.filter(
                transport__allocation__order=self
            ).aggregate(
                total=Sum('net_weight')
            )['total'] or Decimal('0')
        
        # وزن سفارش (مجموع وزن تمام مواد اولیه سفارش)
        order_total_weight = self.get_total_order_weight()
        
        # فی تمام شده خرید
        final_unit_price = self.get_final_unit_price()
        
        # محاسبه تفاوت وزن
        weight_difference = order_total_weight - total_net_weight
        
        return {
            'initial_payment': initial_payment,
            'total_freight': total_freight,
            'total_net_weight': total_net_weight,
            'order_total_weight': order_total_weight,
            'weight_difference': weight_difference,
            'final_unit_price': final_unit_price,
            'total_cost': initial_payment + total_freight,
        }
    
    @staticmethod
    def generate_order_number(order_type='sale'):
        """
        تولید خودکار شماره سفارش بر اساس نوع سفارش
        - برای سفارش فروش (sale): از 100000 شروع می‌شود و دونه دونه افزایش می‌یابد
        - برای سفارش خرید (purchase): از PF000001 شروع می‌شود و دونه دونه افزایش می‌یابد
        """
        if order_type == 'purchase':
            # برای سفارش‌های خرید: فرمت PO000001
            last_order = Order.objects.filter(
                order_type='purchase',
                order_number__startswith='PO-'
            ).order_by('-order_number').first()
            
            if last_order:
                try:
                    # استخراج عدد از PO000001
                    last_num_str = last_order.order_number[3:]  # حذف PO- از ابتدا
                    last_num = int(last_num_str)
                    return f"PO-{last_num + 1:06d}"
                except (ValueError, TypeError):
                    return 'PO-000001'
            else:
                return 'PO-000001'
        else:
            # برای سفارش‌های فروش: فرمت عددی از 100000
            # فقط سفارش‌های فروش که شماره آن‌ها عددی است و >= 100000
            from django.db.models import IntegerField
            from django.db.models.functions import Cast
            
            # فیلتر سفارش‌های فروش که شماره آن‌ها عددی است
            sale_orders = Order.objects.filter(
                order_type='sale'
            ).exclude(
                order_number__startswith='PO-'
            ).exclude(
                order_number__startswith='PO-'
            )
            
            # پیدا کردن آخرین شماره با تبدیل به عدد
            last_order = None
            max_number = 99999  # کمتر از 100000
            
            for order in sale_orders:
                try:
                    order_num = int(order.order_number)
                    if order_num >= 100000 and order_num > max_number:
                        max_number = order_num
                        last_order = order
                except (ValueError, TypeError):
                    continue
            
            if last_order and max_number >= 100000:
                return str(max_number + 1)
            else:
                return '100000'
    
    # Constants for purchase order statuses
    STATUS_DRAFT = 'draft'
    STATUS_AWAITING_TRANSPORT_DEFINITION = 'awaiting_transport_def'
    STATUS_AWAITING_VEHICLE_ENTRY = 'awaiting_vehicle_entry'
    STATUS_AWAITING_DELIVERY = 'awaiting_delivery'
    STATUS_AWAITING_WAREHOUSE_RECONCILIATION = 'awaiting_wh_reconciliation'
    STATUS_AWAITING_FINAL_SETTLEMENT = 'awaiting_final_settlement'
    STATUS_COMPLETED = 'completed'
    
    # Workflow for purchase orders
    WORKFLOW_ALLOWED = {
        STATUS_DRAFT: {STATUS_AWAITING_TRANSPORT_DEFINITION},
        STATUS_AWAITING_TRANSPORT_DEFINITION: {STATUS_AWAITING_VEHICLE_ENTRY},
        STATUS_AWAITING_VEHICLE_ENTRY: {STATUS_AWAITING_DELIVERY},
        STATUS_AWAITING_DELIVERY: {STATUS_AWAITING_WAREHOUSE_RECONCILIATION},
        STATUS_AWAITING_WAREHOUSE_RECONCILIATION: {STATUS_AWAITING_FINAL_SETTLEMENT},
        STATUS_AWAITING_FINAL_SETTLEMENT: {STATUS_COMPLETED},
    }
    
    def can_delete(self):
        """بررسی امکان حذف سفارش (فقط در وضعیت پیش‌نویس)"""
        return self.status == self.STATUS_DRAFT and self.order_type == 'purchase'
    
    def delete(self, *args, **kwargs):
        """حذف سفارش با بررسی وضعیت"""
        if not self.can_delete():
            raise ValueError('حذف سفارش فقط در وضعیت پیش‌نویس مجاز است.')
        return super().delete(*args, **kwargs)
    
    def transition(self, new_status, user=None, note=None):
        """تغییر وضعیت سفارش با ثبت لاگ"""
        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError('وضعیت جدید نامعتبر است.')
        
        # فقط برای سفارش‌های خرید workflow را اعمال کن
        if self.order_type == 'purchase':
            allowed = self.WORKFLOW_ALLOWED.get(self.status, set())
            if new_status not in allowed:
                raise ValueError('مسیر تغییر وضعیت غیرمجاز است.')
        
        old_status = self.status
        self.status = new_status
        with transaction.atomic():
            self.save()
            OrderStatusLog.objects.create(
                order=self,
                old_status=old_status or '',
                new_status=new_status,
                changed_by=user,
                note=note or ''
            )
    
    def save(self, *args, **kwargs):
        """ذخیره سفارش با منطق خودکار"""
        creating = self._state.adding
        
        # تولید شماره سفارش برای سفارش‌های خرید و فروش
        if creating and not self.order_number and self.order_type:
            self.order_number = self.generate_order_number(self.order_type)
        
        # تنظیم وضعیت پیش‌فرض برای سفارش‌های خرید
        if creating and self.order_type == 'purchase' and not self.status:
            self.status = self.STATUS_DRAFT
        
        # تغییر خودکار وضعیت وقتی پیش‌فاکتور تایید می‌شود
        if self.pre_invoice_approved and self.status == self.STATUS_DRAFT and self.order_type == 'purchase':
            self.status = self.STATUS_AWAITING_TRANSPORT_DEFINITION
        
        # محاسبه و ذخیره فی تمام شده خرید هنگام تکمیل سفارش
        if self.order_type == 'purchase' and self.status == self.STATUS_COMPLETED:
            calculated_final_unit_price = self._calculate_final_unit_price()
            if calculated_final_unit_price is not None:
                self.final_unit_price = calculated_final_unit_price
        elif self.order_type == 'purchase' and self.status != self.STATUS_COMPLETED:
            # اگر سفارش از وضعیت completed خارج شد، فیلد را پاک کن
            self.final_unit_price = None
        
        super().save(*args, **kwargs)


class OrderStatusLog(models.Model):
    """لاگ تغییر وضعیت سفارش"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_logs'
    )
    old_status = models.CharField(max_length=100)
    new_status = models.CharField(max_length=100)
    changed_at = jmodels.jDateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_status_changes'
    )
    note = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'لاگ وضعیت سفارش'
        verbose_name_plural = 'لاگ‌های وضعیت سفارش'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.order.order_number}: {self.old_status} -> {self.new_status}"


class OrderChangeLog(models.Model):
    """لاگ تغییرات فیلدهای سفارش"""
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='change_logs'
    )
    field_name = models.CharField(
        max_length=100,
        verbose_name='نام فیلد'
    )
    field_label = models.CharField(
        max_length=200,
        verbose_name='برچسب فیلد',
        null=True,
        blank=True
    )
    old_value = models.TextField(
        verbose_name='مقدار قبلی',
        null=True,
        blank=True
    )
    new_value = models.TextField(
        verbose_name='مقدار جدید',
        null=True,
        blank=True
    )
    changed_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ تغییر'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_field_changes',
        verbose_name='تغییر دهنده'
    )
    note = models.TextField(
        blank=True,
        null=True,
        verbose_name='یادداشت'
    )

    class Meta:
        verbose_name = 'لاگ تغییرات سفارش'
        verbose_name_plural = 'لاگ‌های تغییرات سفارش'
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.order.order_number}: {self.field_name} - {self.changed_at}"