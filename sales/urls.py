from django.urls import path
from sales.views import customer_views, order_views, product_view

app_name = 'sales'

urlpatterns = [
    # مسیرهای مشتری
    path('customer/create/', customer_views.create_customer_view, name='create_customer'),
    path('customer/list/', customer_views.customer_list_view, name='customer_list'),
    # مسیرهای سفارش
    path('order/create/', order_views.create_order_view, name='order_create'),
    path('order/list/', order_views.order_list_view, name='order_list'),

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
    
    # جستجوی AJAX
    path('search/ajax/', product_view.product_search_ajax, name='product_search_ajax'),
]