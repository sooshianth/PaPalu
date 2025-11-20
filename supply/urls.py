from django.urls import path
from .views.views import (
    supply_home_view,
    define_basic_material_view,
    price_inquiry_modal_view,
    create_supplier_view,
    supplier_list_view,
    supplier_detail_view,
    supplier_edit_view,
)

app_name = 'supply'

urlpatterns = [
    path('', supply_home_view, name='home'),
    path('definebasicmat/', define_basic_material_view, name='define_basic_material'),
    path('price-inquiries/<str:raw_material_id>/', price_inquiry_modal_view, name='price_inquiry_modal'),
    path('suppliers/', supplier_list_view, name='supplier_list'),
    path('suppliers/<str:national_id>/', supplier_detail_view, name='supplier_detail'),
    path('suppliers/<str:national_id>/edit/', supplier_edit_view, name='supplier_edit'),
    path('createsupplier/', create_supplier_view, name='create_supplier'),
]
