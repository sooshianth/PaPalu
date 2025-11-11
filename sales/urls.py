from django.urls import path
from sales.views import customer_views, order_views

app_name = 'sales'

urlpatterns = [
    # مسیرهای مشتری
    path('customer/create/', customer_views.create_customer_view, name='create_customer'),
    path('customer/list/', customer_views.customer_list_view, name='customer_list'),
    # مسیرهای سفارش
    path('order/create/', order_views.create_order_view, name='order_create'),
]