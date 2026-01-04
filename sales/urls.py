from django.urls import path
from sales.views import (
    customer_views,
    order_views,
    product_view,
    product_price_view,
    proforma_list_view,
    proforma_approve_view,
    transaction_receipt_view,
    transaction_receipt_approve_view,
    allocation_list_view,
    allocation_approve_view,
    unload_approval_view,
    settlement_view,
    settlement_approval_view,
    invoice_list_view,
)

app_name = 'sales'

urlpatterns = [
    # مسیرهای مشتری
    path('customer/create/', customer_views.create_customer_view, name='create_customer'),
    path('customer/list/', customer_views.customer_list_view, name='customer_list'),
    path('customer/<str:national_id>/', customer_views.customer_detail_view, name='customer_detail'),
    path('customer/<str:national_id>/edit/', customer_views.edit_customer_view, name='edit_customer'),
    # مسیرهای سفارش
    path('order/create/', order_views.create_order_view, name='order_create'),
    path('order/list/', order_views.order_list_view, name='order_list'),
    path('order/<str:order_number>/', order_views.order_detail_view, name='order_detail'),
    path('order/<str:order_number>/edit/', order_views.edit_order_view, name='order_edit'),
    path('order/<str:order_number>/change-history/', order_views.order_change_history_view, name='order_change_history'),
    
    # مسیرهای پیش فاکتور
    path('proforma/list/', proforma_list_view.proforma_list_view, name='proforma_list'),
    path('proforma/create/', proforma_list_view.proforma_create_view, name='proforma_create'),
    path('proforma/<int:proforma_id>/', proforma_list_view.proforma_detail_view, name='proforma_detail'),
    path('proforma/<int:proforma_id>/download-pdf/', proforma_list_view.proforma_download_pdf, name='proforma_download_pdf'),
    
    # مسیرهای فاکتور
    path('invoice/list/', invoice_list_view.invoice_list_view, name='invoice_list'),
    path('invoice/create/', invoice_list_view.invoice_create_view, name='invoice_create'),
    path('invoice/<int:invoice_id>/', invoice_list_view.invoice_detail_view, name='invoice_detail'),
    path('invoice/<int:invoice_id>/download-pdf/', invoice_list_view.invoice_download_pdf, name='invoice_download_pdf'),
    
    # API برای دریافت اطلاعات سفارش
    path('api/order/<str:order_number>/customer/', proforma_list_view.get_order_customer_api, name='get_order_customer_api'),
    # API برای دریافت ملاحظات شرکت
    path('api/company/notes/<str:note_type>/', proforma_list_view.get_company_notes_api, name='get_company_notes_api'),
    # API برای دریافت و ویرایش اطلاعات مشتری
    path('api/customer/<str:customer_id>/info/', proforma_list_view.get_customer_info_for_edit_api, name='get_customer_info_for_edit_api'),
    path('api/customer/<str:customer_id>/update/', proforma_list_view.update_customer_info_api, name='update_customer_info_api'),
    path('api/purchase-order/<str:order_number>/customer/', invoice_list_view.get_order_customer_api, name='get_purchase_order_customer_api'),
    
    # API برای جستجوی مشتری‌ها
    path('api/customers/search/', order_views.customer_search_api, name='customer_search_api'),
    
    # API برای دریافت اطلاعات محصول (واحد و قیمت)
    path('api/products/<int:product_id>/info/', order_views.product_info_api, name='product_info_api'),
    
    # API برای جستجوی سفارش‌ها
    path('api/orders/search/', proforma_list_view.order_search_api, name='order_search_api'),
    path('api/purchase-orders/search/', invoice_list_view.order_search_api, name='purchase_order_search_api'),
    # API برای دریافت شماره پیش فاکتور بعدی
    path('api/proforma/next-number/', proforma_list_view.get_next_proforma_number_api, name='get_next_proforma_number_api'),
    
    # API برای جستجوی محصولات
    path('api/products/search/', product_price_view.product_search_api, name='product_search_api'),
    
    # مسیرهای تأیید پیش فاکتور
    path('approve-proforma/list/', proforma_approve_view.approve_proforma_list_view, name='approve_proforma_list'),
    path('approve-proforma/<str:order_number>/upload/', proforma_approve_view.approve_proforma_upload_view, name='approve_proforma_upload'),

    # مسیرهای ثبت رسید تراکنش فروش
    path('transaction-receipts/orders/', transaction_receipt_view.transaction_receipt_order_list_view, name='transaction_receipt_order_list'),
    path('transaction-receipts/<str:order_number>/upload/', transaction_receipt_view.transaction_receipt_upload_view, name='transaction_receipt_upload'),
    path('transaction-receipts/<str:order_number>/<int:document_id>/edit/', transaction_receipt_view.transaction_receipt_edit_view, name='transaction_receipt_edit'),
    path('transaction-receipts/<str:order_number>/<int:document_id>/<str:action>/', transaction_receipt_view.transaction_receipt_approve_reject_view, name='transaction_receipt_approve_reject'),
    
    # مسیرهای تأیید تراکنش فروش
    path('approve-transaction-receipt/list/', transaction_receipt_approve_view.approve_transaction_receipt_list_view, name='approve_transaction_receipt_list'),
    path('approve-transaction-receipt/<str:order_number>/', transaction_receipt_approve_view.approve_transaction_receipt_detail_view, name='approve_transaction_receipt_detail'),
    
    # مسیرهای تخصیص
    path('allocation/list/', allocation_list_view.allocation_list_view, name='allocation_list'),
    path('allocation/<str:order_number>/create/', allocation_list_view.allocation_create_view, name='allocation_create'),
    path('allocation/<str:order_number>/<str:allocation_number>/edit/', allocation_list_view.allocation_edit_view, name='allocation_edit'),
    path('api/delivery-info/<str:postal_code>/', allocation_list_view.get_delivery_info_api, name='get_delivery_info_api'),
    path('api/allocation/<str:order_number>/postal-codes/search/', allocation_list_view.postal_code_search_api, name='postal_code_search_api'),
    path('api/allocation/<str:order_number>/delivery-address/create/', allocation_list_view.create_delivery_address_api, name='create_delivery_address_api'),
    path('api/allocation/<str:order_number>/delivery-info/<str:postal_code>/rendered/', allocation_list_view.get_delivery_info_rendered_api, name='get_delivery_info_rendered_api'),
    path('api/delivery-address/<str:postal_code>/delete/', allocation_list_view.delete_delivery_address_api, name='delete_delivery_address_api'),
    
    # مسیرهای تأیید تخصیص
    path('approve-allocation/list/', allocation_approve_view.approve_allocation_list_view, name='approve_allocation_list'),
    path('approve-allocation/<str:order_number>/', allocation_approve_view.approve_allocation_detail_view, name='approve_allocation_detail'),
    path('approve-allocation/<str:order_number>/<str:allocation_number>/inquiry/', allocation_approve_view.approve_allocation_inquiry_view, name='approve_allocation_inquiry'),
    path('approve-allocation/<str:order_number>/reject/', allocation_approve_view.reject_allocations_view, name='reject_allocations'),
    
    # مسیرهای مدیریت تخصیص‌های رد شده
    path('manage-allocations/list/', allocation_approve_view.manage_allocations_list_view, name='manage_allocations_list'),
    path('manage-allocations/<str:order_number>/', allocation_approve_view.manage_allocations_detail_view, name='manage_allocations_detail'),
    path('manage-allocations/<str:order_number>/approve-all/', allocation_approve_view.approve_all_rejected_allocations_view, name='approve_all_rejected_allocations'),
    
    # مسیرهای تایید تخلیه
    path('unload-approval/list/', unload_approval_view.unload_approval_list_view, name='unload_approval_list'),
    path('unload-approval/<str:order_number>/', unload_approval_view.unload_approval_detail_view, name='unload_approval_detail'),
    
    # مسیرهای تسویه
    path('settlement/list/', settlement_view.settlement_list_view, name='settlement_list'),
    path('settlement/<str:order_number>/', settlement_view.settlement_detail_view, name='settlement_detail'),
    path('settlement/<str:order_number>/skip/', settlement_view.skip_settlement_view, name='skip_settlement'),
    
    # مسیرهای تایید تسویه کامل
    path('settlement-approval/list/', settlement_approval_view.settlement_approval_list_view, name='settlement_approval_list'),
    path('settlement-approval/<str:order_number>/', settlement_approval_view.settlement_approval_detail_view, name='settlement_approval_detail'),

    path('create/', product_view.create_product_view, name='create_product'),
    
    # لیست محصولات
    path('list/', product_view.product_list_view, name='product_list'),
    path('', product_view.product_list_view, name='product_list_default'),
    
    # جزئیات محصول
    path('<int:product_id>/', product_view.product_detail_view, name='product_detail'),
    
    # ویرایش محصول
    path('<int:product_id>/edit/', product_view.edit_product_view, name='edit_product'),
    
    # حذف محصول
    path('<int:product_id>/delete/', product_view.delete_product_view, name='delete_product'),
    
    # قیمت‌گذاری محصول
    path('price/list/', product_price_view.product_price_list_view, name='product_price_list'),
    path('price/create/', product_price_view.set_product_price_view, name='set_product_price'),
    path('<int:product_id>/set-price/', product_price_view.set_product_price_view, name='set_product_price_with_id'),
    
    # جستجوی AJAX
    path('search/ajax/', product_view.product_search_ajax, name='product_search_ajax'),
    path('raw-materials/ajax/', product_view.get_raw_materials_ajax, name='get_raw_materials_ajax'),
    
    # تولید شناسه‌های پیشنهادی AJAX
    path('api/generate-product-code/', product_view.generate_product_code_ajax, name='generate_product_code_ajax'),
    path('api/generate-formula-id/', product_view.generate_formula_id_ajax, name='generate_formula_id_ajax'),
]