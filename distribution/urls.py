from django.urls import path
from distribution.views.shipping_announcement_view import (
    shipping_announcement_list_view,
    shipping_announcement_process_view,
    shipping_announcement_single_view
)

app_name = 'distribution'

urlpatterns = [
    path('shipping-announcement/', shipping_announcement_list_view, name='shipping_announcement_list'),
    path('shipping-announcement/process/', shipping_announcement_process_view, name='shipping_announcement_process'),
    path('shipping-announcement/single/', shipping_announcement_single_view, name='shipping_announcement_single'),
]