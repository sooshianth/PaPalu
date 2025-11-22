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
from .views.purchase_order_views import (
    purchase_order_management_view,
    create_procurement_purchase_order_view,
    procurement_purchase_order_detail_view,
    edit_procurement_purchase_order_view,
    delete_procurement_purchase_order_view,
    transition_procurement_purchase_order_status_view,
    confirm_procurement_purchase_order_payment_view,
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
    # Purchase Order Management
    path('purchaseordermanagement/', purchase_order_management_view, name='purchase_order_management'),
    path('purchaseorders/create/', create_procurement_purchase_order_view, name='create_procurement_purchase_order'),
    path('purchaseorders/<str:order_number>/', procurement_purchase_order_detail_view, name='procurement_purchase_order_detail'),
    path('purchaseorders/<str:order_number>/edit/', edit_procurement_purchase_order_view, name='edit_procurement_purchase_order'),
    path('purchaseorders/<str:order_number>/delete/', delete_procurement_purchase_order_view, name='delete_procurement_purchase_order'),
    path('purchaseorders/<str:order_number>/transition/<str:new_status>/', transition_procurement_purchase_order_status_view, name='transition_procurement_purchase_order_status'),
    path('purchaseorders/<str:order_number>/confirm-payment/', confirm_procurement_purchase_order_payment_view, name='confirm_procurement_purchase_order_payment'),
]
