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
    SALES_VIEW_ORDER_DETAIL = 'sales.view_order_detail', 'مشاهده جزئیات سفارش فروش'
    SALES_EDIT_ORDER = 'sales.edit_order', 'ویرایش سفارش فروش'
    SALES_PRODUCT_PRICE_LIST = 'sales.product_price_list', 'لیست قیمت محصولات'
    SALES_SET_PRODUCT_PRICE = 'sales.set_product_price', 'قیمت‌گذاری محصول'
    SALES_CREATE_PRODUCT = 'sales.create_product', 'ایجاد محصول'
    SALES_VIEW_PRODUCT_LIST = 'sales.view_product_list', 'مشاهده لیست محصولات'
    SALES_VIEW_PRODUCT_DETAIL = 'sales.view_product_detail', 'مشاهده جزئیات محصول'
    SALES_EDIT_PRODUCT = 'sales.edit_product', 'ویرایش محصول'
    SALES_DELETE_PRODUCT = 'sales.delete_product', 'حذف محصول'
    SALES_ISSUE_PROFORMA = 'sales.issue_proforma', 'صدور پیش فاکتور فروش'
    SALES_APPROVE_PROFORMA = 'sales.approve_proforma', 'تایید پیش فاکتور فروش'
    SALES_APPROVE_PROFORMA_PRICE = 'sales.approve_proforma_price', 'جزییات و پی‌دی‌اف پیش فاکتور'
    SALES_TRANSACTION_RECEIPT = 'sales.transaction_receipt', 'رسید تراکنش فروش'
    SALES_APPROVE_TRANSACTION = 'sales.approve_transaction', 'تایید تراکنش فروش'
    SALES_ALLOCATION = 'sales.allocation', 'تخصیص فروش'
    SALES_VIEW_ALLOCATION_LIST = 'sales.view_allocation_list', 'مشاهده لیست تخصیص‌ها'
    SALES_APPROVE_ALLOCATION = 'sales.approve_allocation', 'تایید تخصیص فروش'
    SALES_APPROVE_UNLOAD = 'sales.approve_unload', 'تایید تخلیه سفارش'
    SALES_SETTLEMENT = 'sales.settlement', 'تسویه سفارش فروش'
    SALES_APPROVE_SETTLEMENT = 'sales.approve_settlement', 'تایید تسویه کامل فروش'
    SALES_ISSUE_INVOICE = 'sales.issue_invoice', 'صدور فاکتور فروش'
    
    
    
    # Supply (تامین)
    SUPPLY_CREATE_SUPPLIER = 'supply.create_supplier', 'ایجاد شخص فروشنده'
    SUPPLY_CREATE_ORDER = 'supply.create_order', 'ایجاد سفارش خرید'
    SUPPLY_DEFINE_RAW_MATERIAL = 'supply.define_raw_material', 'تعریف مواد اولیه'
    # SUPPLY_DEFINE_ALLOCATION = 'supply.define_allocation', 'تعریف تخصیص خریدی'
    SUPPLY_DEFINE_TRANSPORTATION = 'supply.define_transportation', 'تعریف حمل خرید'
    # SUPPLY_TRACK_DISCREPANCY = 'supply.track_discrepancy', 'پیگیری اختلاف خرید'
    # SUPPLY_TRANSACTION_DOCUMENTS = 'supply.transaction_documents', 'اسناد تراکنش خرید'
    # SUPPLY_UPLOAD_PROFORMA = 'supply.upload_proforma', 'بارگذاری پیش فاکتور و درخواست پرداخت خرید'
    SUPPLY_REGISTER_VEHICLE_EXIT = 'supply.register_vehicle_exit', 'ثبت خروج خودرو'
    SUPPLY_CAR_ENTRANCE = 'supply.car_entrance', 'ورود خودرو به کارخانه'
    # SUPPLY_REGISTER_WAYBILL = 'supply.register_waybill', 'بارگذاری بارنامه'
    SUPPLY_WAREHOUSE_DELIVERY = 'supply.warehouse_delivery', 'تحویل انبار'
    SUPPLY_LOGISTIC_CONFIRMATION = 'supply.logistic_confirmation', 'تایید لجستیک'
    SUPPLY_VIEW_REJECTED_TRANSPORTS = 'supply.view_rejected_transports', 'مشاهده حمل‌های ارجاع به مدیریت'
    SUPPLY_UPLOAD_FREIGHT_PAYMENT_DOCS = 'supply.upload_freight_payment_docs', 'بارگذاری اسناد پرداخت کرایه'
    SUPPLY_SETTLEMENT = 'supply.settlement', 'تسویه سفارش خرید'
    SUPPLY_APPROVE_SETTLEMENT = 'supply.approve_settlement', 'تایید تسویه کامل خرید'

    # SUPPLY_REGISTER_SYSTEM_WAYBILL = 'supply.register_system_waybill', 'ثبت سیستمی اطلاعات بارنامه'
    # SUPPLY_REGISTER_GROSS_WEIGHT = 'supply.register_gross_weight', 'ثبت وزن پر'
    # SUPPLY_REGISTER_NET_WEIGHT = 'supply.register_net_weight', 'وزن خالی'
    # SUPPLY_APPROVE_DELIVERY = 'supply.approve_delivery', 'تایید تحویل'
    # SUPPLY_APPROVE_PROFORMA = 'supply.approve_proforma', 'تایید پیش فاکتور تامین'
    # SUPPLY_APPROVE_FREIGHT_PAYMENT = 'supply.approve_freight_payment', 'تایید پرداخت کرایه'
    # SUPPLY_UPLOAD_PAYMENT_DOCUMENTS = 'supply.upload_payment_documents', 'بارگذاری اسناد پرداخت کرایه'
    
    # Production (تولید)
    PRODUCTION_DECLARATION = 'production.declaration', 'اعلام تولید'
    PRODUCTION_DECLARATION_CRUD = 'production.declaration_crud', 'اعلام تولید جدید'
    PRODUCTION_DECLARATION_ARCHIVED = 'production.declaration_archived', 'اعلام تولید بایگانی شده'
    WAREHOUSE_PRODUCTION_LIST = 'production.warehouse_production_list', 'مشاهده لیست اظهار تولید'
    PRODUCTION_SUBMIT_REPORT = 'production.submit_report', 'اظهار تولید'
    PRODUCTION_APPROVE_REPORT = 'production.approve_report', 'تایید اظهار تولید'
    PRODUCTION_MANAGER_SOLVE_ISSUES = 'production.manager_solve_issues', 'مدیریت حل مشکلات تولید'
    WAREHOUSE_PRODUCTION_DETAIL = 'production.warehouse_production_detail', 'مشاهده جزئیات اظهار تولید'
    PRODUCTION_REGISTER_NEW_SCHEDULE = 'production.register_new_schedule', 'ثبت برنامه تولید جدید'
    WAREHOUSE_APPROVE_PRODUCTION = 'production.warehouse_approve_production', 'تایید اظهار تولید'
    WAREHOUSE_DISAPPROVE_PRODUCTION = 'production.warehouse_disapprove_production', 'رد اظهار تولید'
    STOCK_ENTRY_DETAIL = 'production.stock_entry_detail', 'مشاهده جزئیات ورود انبار'
    # PRODUCTION_QUALITY_CONTROL_FORMS = 'production.quality_control_forms', 'فرم های کنترل کیفیت'
    PRODUCTION_REJECT_SCHEDULE = 'production.reject_schedule', 'رد برنامه تولید'
    PRODUCTION_REVERT_SCHEDULE = 'production.revert_schedule', 'بازگشت از تولید'
    PRODUCTION_ARCHIVE = 'production.archive', 'آرشیو تولید'
    PRODUCTION_PROGRAM_LIST = 'production.program_list', 'مشاهده لیست برنامه‌های تولید'
    PRODUCTION_VIEW_WAREHOUSE = 'production.view_warehouse', 'مشاهده انبار'

    # Distribution (توزیع)
    # DISTRIBUTION_PRINT_WAYBILL = 'distribution.print_waybill', 'چاپ بارنامه'
    # DISTRIBUTION_APPROVE_EXIT = 'distribution.approve_exit', 'تایید خروج'
    # DISTRIBUTION_ISSUE_WAYBILL = 'distribution.issue_waybill', 'صدور و اپلود بارنامه'
    # DISTRIBUTION_APPROVE_LOADING = 'distribution.approve_loading', 'تایید بارگیری'
    # DISTRIBUTION_NOTIFY_CARRIER = 'distribution.notify_carrier', 'اعلام به باربری'
    # DISTRIBUTION_RECRUIT_VEHICLE = 'distribution.recruit_vehicle', 'جذب خودرو'
    # DISTRIBUTION_CREATE_TRANSPORTATION = 'distribution.create_transportation', 'ایجاد حمل'
    # DISTRIBUTION_CREATE_DRIVER = 'distribution.create_driver', 'ایجاد شخص راننده'
    # DISTRIBUTION_SEND_WEIGHT_INFO = 'distribution.send_weight_info', 'ارسال اطلاعات وزنی به باربری'
    
    # Distribution - ویوهای دقیق
    DISTRIBUTION_VIEW_SHIPPING_ANNOUNCEMENT_LIST = 'distribution.view_shipping_announcement_list', 'مشاهده لیست اعلام بار'
    DISTRIBUTION_PROCESS_SHIPPING_ANNOUNCEMENT = 'distribution.process_shipping_announcement', 'پردازش اعلام بار'
    DISTRIBUTION_VIEW_VEHICLE_ENTRY_LIST = 'distribution.view_vehicle_entry_list', 'مشاهده لیست ورود خودرو'
    DISTRIBUTION_REGISTER_VEHICLE_ENTRY = 'distribution.register_vehicle_entry', 'ثبت ورود خودرو'
    DISTRIBUTION_VIEW_VEHICLE_RECRUITMENT_LIST = 'distribution.view_vehicle_recruitment_list', 'مشاهده لیست جذب خودرو'
    DISTRIBUTION_CREATE_TRANSPORT = 'distribution.create_transport', 'ایجاد حمل جدید'
    # DISTRIBUTION_COMPLETE_VEHICLE_RECRUITMENT = 'distribution.complete_vehicle_recruitment', 'تکمیل جذب خودرو'
    DISTRIBUTION_VIEW_LOADING_EXIT_LIST = 'distribution.view_loading_exit_list', 'مشاهده لیست خروج کالا'
    DISTRIBUTION_REGISTER_LOADING_EXIT = 'distribution.register_loading_exit', 'ثبت خروج کالا'
    DISTRIBUTION_VIEW_WAYBILL_LIST = 'distribution.view_waybill_list', 'مشاهده لیست حمل‌های در انتظار بارنامه'
    DISTRIBUTION_REGISTER_WAYBILL = 'distribution.register_waybill', 'ثبت اطلاعات بارنامه'
    DISTRIBUTION_VIEW_EXIT_LIST = 'distribution.view_exit_list', 'مشاهده لیست حمل‌های در انتظار خروج'
    DISTRIBUTION_PRINT_WAYBILL_PDF = 'distribution.print_waybill_pdf', 'چاپ PDF بارنامه'
    DISTRIBUTION_MARK_VEHICLE_EXITED = 'distribution.mark_vehicle_exited', 'ثبت خروج خودرو'

    # Access (دسترسی‌ها)
    ACCESS_FIELD_ACCESS_BULK_UPLOAD = 'access.field_access_bulk_upload', 'آپلود دسته‌ای دسترسی فیلدها'


# Add category order as a class attribute after class definition
# Format: (category_id, display_name)
TaskChoices.CATEGORY_ORDER = [
    ('general', 'عمومی'),
    ('sales', 'فروش'),
    ('supply', 'تامین'),
    ('production', 'تولید'),
    ('distribution', 'توزیع'),
    ('access', 'دسترسی‌ها'),
]


class TaskPermission(models.Model):
    """
    یک مجموعه از تسک‌ها (نام + لیست کد تسک‌ها).
    از طریق ManyToMany روی Role می‌تواند به چند نقش اختصاص داده شود.
    """
    name = models.CharField(max_length=100, unique=True)
    tasks = models.JSONField(default=list)

    class Meta:
        verbose_name = 'RBAC | مجوز دسترسی تسک'
        verbose_name_plural = 'RBAC | مجوزهای دسترسی تسک'

    def __str__(self):
        return self.name
