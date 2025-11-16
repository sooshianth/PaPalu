from django.urls import path
from sales.views import (
    customer_views,
    order_views,
    product_view,
    product_price_view,
    proforma_view,
    approve_proforma_view,
    transaction_receipt_view,
)

app_name = 'sales'

urlpatterns = [
    # مسیرهای مشتری
    path('customer/create/', customer_views.create_customer_view, name='create_customer'),
    path('customer/list/', customer_views.customer_list_view, name='customer_list'),
    # مسیرهای سفارش
    path('order/create/', order_views.create_order_view, name='order_create'),
    path('order/list/', order_views.order_list_view, name='order_list'),
    
    # مسیرهای پیش فاکتور
    path('proforma/list/', proforma_view.proforma_list_view, name='proforma_list'),
    path('proforma/create/', proforma_view.proforma_create_view, name='proforma_create'),
    path('proforma/<int:proforma_id>/', proforma_view.proforma_detail_view, name='proforma_detail'),
    path('proforma/<int:proforma_id>/download-pdf/', proforma_view.proforma_download_pdf, name='proforma_download_pdf'),
    
    # API برای دریافت اطلاعات سفارش
    path('api/order/<str:order_number>/customer/', proforma_view.get_order_customer_api, name='get_order_customer_api'),
    
    # مسیرهای تأیید پیش فاکتور
    path('approve-proforma/list/', approve_proforma_view.approve_proforma_list_view, name='approve_proforma_list'),
    path('approve-proforma/<str:order_number>/upload/', approve_proforma_view.approve_proforma_upload_view, name='approve_proforma_upload'),

    # مسیرهای ثبت رسید تراکنش فروش
    path('transaction-receipts/orders/', transaction_receipt_view.transaction_receipt_order_list_view, name='transaction_receipt_order_list'),
    path('transaction-receipts/<str:order_number>/upload/', transaction_receipt_view.transaction_receipt_upload_view, name='transaction_receipt_upload'),

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
]