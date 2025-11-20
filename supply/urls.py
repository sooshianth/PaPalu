from django.urls import path
from .views.views import (
    supply_home_view,
    define_basic_material_view,
    price_inquiry_modal_view,
)

app_name = 'supply'

urlpatterns = [
    path('', supply_home_view, name='home'),
    path('definebasicmat/', define_basic_material_view, name='define_basic_material'),
    path('price-inquiries/<str:raw_material_id>/', price_inquiry_modal_view, name='price_inquiry_modal'),
]
