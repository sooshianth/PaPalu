from django.db import models


class TaskChoices(models.TextChoices):
    """
    Task choices organized by category.
    Format: CATEGORY_TASK_NAME = 'category.task_name', 'Display Label'
    """
    
    # General
    GENERAL_VIEW_DASHBOARD = 'general.view_dashboard', 'مشاهده داشبورد'
    
    # Sales (فروش)
    SALES_CREATE_CUSTOMER = 'sales.create_customer', 'ایجاد شخص مشتری'
    SALES_CREATE_ORDER = 'sales.create_order', 'ایجاد سفارش فروش'
    SALES_VIEW_ORDER_LIST = 'sales.view_order_list', 'مشاهده لیست سفارش‌های فروش'
    SALES_ISSUE_PROFORMA = 'sales.issue_proforma', 'صدور پیش فاکتور فروش'
    SALES_APPROVE_PROFORMA = 'sales.approve_proforma', 'تایید پیش فاکتور فروش'
    SALES_TRANSACTION_RECEIPT = 'sales.transaction_receipt', 'رسید تراکنش فروش'
    SALES_ALLOCATION = 'sales.allocation', 'تخصیص فروش'
    SALES_APPROVE_UNLOAD = 'sales.approve_unload', 'تایید تخلیه سفارش'
    SALES_TRACK_DISCREPANCY = 'sales.track_discrepancy', 'پیگیری اختلاف فروش'
    SALES_APPROVE_TRANSACTION = 'sales.approve_transaction', 'تایید تراکنش فروش'
    SALES_APPROVE_SETTLEMENT = 'sales.approve_settlement', 'تایید تسویه کامل فروش'
    SALES_ISSUE_INVOICE = 'sales.issue_invoice', 'صدور فاکتور فروش'
    SALES_DEFINE_PRODUCT = 'sales.define_product', 'تعریف محصول'
    SALES_APPROVE_ALLOCATION = 'sales.approve_allocation', 'تایید تخصیص فروش'
    SALES_APPROVE_PROFORMA_PRICE = 'sales.approve_proforma_price', 'تایید پیش فاکتور فروش(قیمت و مشخصات)'
    SALES_PRODUCT_PRICE_LIST = 'sales.product_price_list', 'لیست قیمت محصولات'
    
    
    # Supply (تامین)
    SUPPLY_CREATE_SUPPLIER = 'supply.create_supplier', 'ایجاد شخص فروشنده'
    SUPPLY_CREATE_ORDER = 'supply.create_order', 'ایجاد سفارش خرید'
    SUPPLY_DEFINE_RAW_MATERIAL = 'supply.define_raw_material', 'تعریف مواد اولیه'
    SUPPLY_DEFINE_ALLOCATION = 'supply.define_allocation', 'تعریف تخصیص خریدی'
    SUPPLY_DEFINE_TRANSPORTATION = 'supply.define_transportation', 'تعریف حمل خرید'
    SUPPLY_TRACK_DISCREPANCY = 'supply.track_discrepancy', 'پیگیری اختلاف خرید'
    SUPPLY_TRANSACTION_DOCUMENTS = 'supply.transaction_documents', 'اسناد تراکنش خرید'
    SUPPLY_UPLOAD_PROFORMA = 'supply.upload_proforma', 'بارگذاری پیش فاکتور و درخواست پرداخت خرید'
    SUPPLY_REGISTER_VEHICLE_EXIT = 'supply.register_vehicle_exit', 'ثبت خروج خودرو'
    SUPPLY_REGISTER_DRIVER = 'supply.register_driver', 'ثبت شخص راننده تامین'
    SUPPLY_REGISTER_WAYBILL = 'supply.register_waybill', 'بارگذاری بارنامه'
    SUPPLY_REGISTER_SYSTEM_WAYBILL = 'supply.register_system_waybill', 'ثبت سیستمی اطلاعات بارنامه'
    SUPPLY_REGISTER_GROSS_WEIGHT = 'supply.register_gross_weight', 'ثبت وزن پر'
    SUPPLY_REGISTER_NET_WEIGHT = 'supply.register_net_weight', 'وزن خالی'
    SUPPLY_APPROVE_QUALITY_INSPECTOR = 'supply.approve_quality_inspector', 'تایید ناظر کیفی جهت تخلیه'
    SUPPLY_MATCH_WAYBILL_INFORMATION = 'supply.match_waybill_information', 'تطبیق اطلاعات عکس بارنامه با اطلاعات ثبت شده'
    SUPPLY_MATCH_WEIGHT_FREIGHT = 'supply.match_weight_freight', 'تطبیق وزن و کرایه'
    SUPPLY_APPROVE_DELIVERY = 'supply.approve_delivery', 'تایید تحویل'
    SUPPLY_APPROVE_PROFORMA = 'supply.approve_proforma', 'تایید پیش فاکتور تامین'
    SUPPLY_APPROVE_FREIGHT_PAYMENT = 'supply.approve_freight_payment', 'تایید پرداخت کرایه'
    SUPPLY_UPLOAD_PAYMENT_DOCUMENTS = 'supply.upload_payment_documents', 'بارگذاری اسناد پرداخت کرایه'
    SUPPLY_APPROVE_SETTLEMENT = 'supply.approve_settlement', 'تایید تسویه کامل'
    SUPPLY_PREPAY_PROFORMA = 'supply.prepay_proforma', 'پرداخت پیش فاکتور خرید'
    
    # Production (تولید)
    PRODUCTION_SUBMIT_REPORT = 'production.submit_report', 'اظهار تولید'
    PRODUCTION_APPROVE_REPORT = 'production.approve_report', 'تایید اظهار تولید'
    PRODUCTION_REGISTER_NEW_SCHEDULE = 'production.register_new_schedule', 'ثبت برنامه تولید جدید'
    PRODUCTION_QUALITY_CONTROL_FORMS = 'production.quality_control_forms', 'فرم های کنترل کیفیت'
    
    # Distribution (توزیع)
    DISTRIBUTION_ALLOCATE_INVENTORY = 'distribution.allocate_inventory', 'اختصاص موجودی محصول به تخصیص'
    DISTRIBUTION_READY_FOR_SHIPMENT = 'distribution.ready_for_shipment', 'تخصیص آماده ارسال'
    DISTRIBUTION_REGISTER_NET_WEIGHT = 'distribution.register_net_weight', 'ثبت وزن خالی'
    DISTRIBUTION_REGISTER_GROSS_WEIGHT = 'distribution.register_gross_weight', 'ثبت وزن پر'
    DISTRIBUTION_UPLOAD_DELIVERY_RECEIPT = 'distribution.upload_delivery_receipt', 'اپلود رسید تحویل بار از راننده'
    DISTRIBUTION_VALIDATE_VEHICLE_ENTRY = 'distribution.validate_vehicle_entry', 'صحت سنجی و اعلام ورود خودرو'
    DISTRIBUTION_PRINT_WAYBILL = 'distribution.print_waybill', 'چاپ بارنامه'
    DISTRIBUTION_APPROVE_EXIT = 'distribution.approve_exit', 'تایید خروج'
    DISTRIBUTION_ISSUE_WAYBILL = 'distribution.issue_waybill', 'صدور و اپلود بارنامه'
    DISTRIBUTION_APPROVE_LOADING = 'distribution.approve_loading', 'تایید بارگیری'
    DISTRIBUTION_NOTIFY_CARRIER = 'distribution.notify_carrier', 'اعلام به باربری'
    DISTRIBUTION_RECRUIT_VEHICLE = 'distribution.recruit_vehicle', 'جذب خودرو'
    DISTRIBUTION_CREATE_TRANSPORTATION = 'distribution.create_transportation', 'ایجاد حمل'
    DISTRIBUTION_CREATE_DRIVER = 'distribution.create_driver', 'ایجاد شخص راننده'
    DISTRIBUTION_SEND_WEIGHT_INFO = 'distribution.send_weight_info', 'ارسال اطلاعات وزنی به باربری'


# Add category order as a class attribute after class definition
# Format: (category_id, display_name)
TaskChoices.CATEGORY_ORDER = [
    ('general', 'عمومی'),
    ('sales', 'فروش'),
    ('supply', 'تامین'),
    ('production', 'تولید'),
    ('distribution', 'توزیع'),
]


class TaskPermission(models.Model):
    name = models.CharField(max_length=100, unique=True)
    tasks = models.JSONField(default=list)

    def __str__(self):
        return self.name
