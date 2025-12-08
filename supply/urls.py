"""
URL Configuration for Supply Domain
ساختار ماژولار برای مدیریت بهتر URL ها در دامنه تامین
"""
from django.urls import path

# Import all views from modular structure
from .views import (
    # Supplier Views
    supply_home_view,
    create_supplier_view,
    supplier_list_view,
    supplier_detail_view,
    supplier_edit_view,
    # Raw Material Views
    define_basic_material_view,
    price_inquiry_modal_view,
    # Purchase Order Views
    purchase_order_management_view,
    create_procurement_purchase_order_view,
    procurement_purchase_order_detail_view,
    edit_procurement_purchase_order_view,
    delete_procurement_purchase_order_view,
    transition_procurement_purchase_order_status_view,
    confirm_procurement_purchase_order_payment_view,
    # Purchase Transport Views
    purchase_transport_list_view,
    create_purchase_transport_view,
    purchase_transport_detail_view,
    edit_purchase_transport_view,
    delete_purchase_transport_view,
    transition_purchase_transport_status_view,
    get_purchase_order_info_api,
    # Car Entrance Views
    car_entrance_list_view,
    register_driver_for_transport_view,
    mark_vehicle_entered_view,
    driver_lookup_api,
    car_exit_list_view,
    mark_vehicle_exited_view,
    # Warehouse Delivery Views
    warehouse_delivery_list_view,
    warehouse_delivery_detail_view,
    guard_vehicle_exit_view,
    # Logistic Confirmation Views
    logistic_confirmation_list_view,
    logistic_confirmation_detail_view,
    # Upload Fare Payment Documents Views
    upload_fare_payment_docs_list_view,
    upload_fare_payment_docs_detail_view,
)

app_name = 'supply'

urlpatterns = [
    path('', supply_home_view, name='home'),
    path('definebasicmat/', define_basic_material_view, name='define_basic_material'),
    path('price-inquiries/<str:raw_material_id>/', price_inquiry_modal_view, name='price_inquiry_modal'),
    path('suppliers/', supplier_list_view, name='supplier_list'),
    path('suppliers/<str:national_id>/', supplier_detail_view, name='supplier_detail'),
    path('suppliers/<str:national_id>/edit/', supplier_edit_view, name='supplier_edit'),
    # path('createsupplier/', create_supplier_view, name='create_supplier'),  # Deprecated: supplier creation is now inline in supplier_list
    # Purchase Order Management
    path('purchaseordermanagement/', purchase_order_management_view, name='purchase_order_management'),
    path('purchaseorders/create/', create_procurement_purchase_order_view, name='create_procurement_purchase_order'),
    path('purchaseorders/<str:order_number>/', procurement_purchase_order_detail_view, name='procurement_purchase_order_detail'),
    path('purchaseorders/<str:order_number>/edit/', edit_procurement_purchase_order_view, name='edit_procurement_purchase_order'),
    path('purchaseorders/<str:order_number>/delete/', delete_procurement_purchase_order_view, name='delete_procurement_purchase_order'),
    path('purchaseorders/<str:order_number>/transition/<str:new_status>/', transition_procurement_purchase_order_status_view, name='transition_procurement_purchase_order_status'),
    path('purchaseorders/<str:order_number>/confirm-payment/', confirm_procurement_purchase_order_payment_view, name='confirm_procurement_purchase_order_payment'),
    # Purchase Transport Management
    path('purchasetransport/', purchase_transport_list_view, name='purchase_transport_list'),
    path('purchasetransport/create/', create_purchase_transport_view, name='create_purchase_transport'),
    path('purchasetransport/<str:transport_number>/', purchase_transport_detail_view, name='purchase_transport_detail'),
    path('purchasetransport/<str:transport_number>/edit/', edit_purchase_transport_view, name='edit_purchase_transport'),
    path('purchasetransport/<str:transport_number>/delete/', delete_purchase_transport_view, name='delete_purchase_transport'),
    path('purchasetransport/<str:transport_number>/transition/<str:new_status>/', transition_purchase_transport_status_view, name='transition_purchase_transport_status'),
    # API
    path('api/purchase-order-info/<str:order_number>/', get_purchase_order_info_api, name='get_purchase_order_info_api'),
    # Car Entrance (Gatekeeper)
    path('carentrance/', car_entrance_list_view, name='carentrance'),
    path('carentrance/<str:transport_number>/register/', register_driver_for_transport_view, name='carentrance_register_driver'),
    path('carentrance/<str:transport_number>/mark-entered/', mark_vehicle_entered_view, name='carentrance_mark_entered'),
    path('api/driver-lookup/', driver_lookup_api, name='driver_lookup_api'),
    # Car Exit (Gatekeeper)
    path('carexit/', car_exit_list_view, name='carexit'),
    path('carexit/<str:transport_number>/mark-exited/', mark_vehicle_exited_view, name='carexit_mark_exited'),
    # Warehouse Delivery
    path('warehouse-delivery/', warehouse_delivery_list_view, name='warehouse_delivery'),
    path('warehouse-delivery/<str:transport_number>/', warehouse_delivery_detail_view, name='warehouse_delivery_detail'),
    path('warehouse-delivery/<str:transport_number>/guard-exit/', guard_vehicle_exit_view, name='guard_vehicle_exit'),
    # Logistic Confirmation
    path('logistic-confirmation/', logistic_confirmation_list_view, name='logistic_confirmation_list'),
    path('logistic-confirmation/<str:transport_number>/', logistic_confirmation_detail_view, name='logistic_confirmation_detail'),
    # Upload Fare Payment Documents
    path('upload-fare-payment-docs/', upload_fare_payment_docs_list_view, name='upload_fare_payment_docs_list'),
    path('upload-fare-payment-docs/<str:transport_number>/', upload_fare_payment_docs_detail_view, name='upload_fare_payment_docs_detail'),
]
