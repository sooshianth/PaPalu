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
    raw_material_list_view,
    price_inquiry_modal_view,
    raw_material_detail_view,
    raw_material_edit_view,
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
    supplier_search_api,
    raw_material_search_api,
    raw_material_info_api,
    driver_search_api,
    create_driver_api,
    get_order_materials_api,
    get_driver_bank_accounts_api,
    create_driver_bank_account_api,
    get_driver_plate_numbers_api,
    get_supplier_bank_accounts_api,
    create_supplier_bank_account_api,
    # Car Entrance Views
    car_entrance_list_view,
    register_driver_for_transport_view,
    driver_lookup_api,
    # car_exit_list_view,
    # mark_vehicle_exited_view,
    # Warehouse Delivery Views
    warehouse_delivery_list_view,
    warehouse_delivery_detail_view,
    guard_vehicle_exit_view,
    # Logistic Confirmation Views
    logistic_confirmation_list_view,
    logistic_confirmation_detail_view,
    rejected_transports_list_view,
    rejected_transport_detail_view,
    # Supply Settlement Views
    supply_settlement_list_view,
    supply_settlement_detail_view,
    skip_supply_settlement_view,
    supply_settlement_approval_list_view,
    supply_settlement_approval_detail_view,

)

app_name = 'supply'

urlpatterns = [
    path('', supply_home_view, name='home'),
    path('raw-materials/', raw_material_list_view, name='raw_material_list'),
    path('raw-materials/<str:raw_material_id>/', raw_material_detail_view, name='raw_material_detail'),
    path('raw-materials/<str:raw_material_id>/edit/', raw_material_edit_view, name='raw_material_edit'),
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
    path('api/supplier-search/', supplier_search_api, name='supplier_search_api'),
    path('api/raw-material-search/', raw_material_search_api, name='raw_material_search_api'),
    path('api/raw-material-info/<int:raw_material_id>/', raw_material_info_api, name='raw_material_info_api'),
    path('api/driver-search/', driver_search_api, name='driver_search_api'),
    path('api/driver-create/', create_driver_api, name='create_driver_api'),
    path('api/order-materials/<str:order_number>/', get_order_materials_api, name='get_order_materials_api'),
    path('api/driver-bank-accounts/<int:driver_id>/', get_driver_bank_accounts_api, name='get_driver_bank_accounts_api'),
    path('api/driver-bank-account-create/', create_driver_bank_account_api, name='create_driver_bank_account_api'),
    path('api/driver-plate-numbers/<int:driver_id>/', get_driver_plate_numbers_api, name='get_driver_plate_numbers_api'),
    path('api/supplier-bank-accounts/<int:order_id>/', get_supplier_bank_accounts_api, name='get_supplier_bank_accounts_api'),
    path('api/supplier-bank-account-create/', create_supplier_bank_account_api, name='create_supplier_bank_account_api'),
    # Car Entrance (Gatekeeper)
    path('carentrance/', car_entrance_list_view, name='carentrance'),
    path('carentrance/<str:transport_number>/register/', register_driver_for_transport_view, name='carentrance_register_driver'),
    path('api/driver-lookup/', driver_lookup_api, name='driver_lookup_api'),
    # Car Exit (Gatekeeper)
    # path('carexit/', car_exit_list_view, name='carexit'),
    # path('carexit/<str:transport_number>/mark-exited/', mark_vehicle_exited_view, name='carexit_mark_exited'),
    # Warehouse Delivery
    path('warehouse-delivery/', warehouse_delivery_list_view, name='warehouse_delivery'),
    path('warehouse-delivery/<str:transport_number>/', warehouse_delivery_detail_view, name='warehouse_delivery_detail'),
    path('warehouse-delivery/<str:transport_number>/guard-exit/', guard_vehicle_exit_view, name='guard_vehicle_exit'),
    # Logistic Confirmation
    path('logistic-confirmation/', logistic_confirmation_list_view, name='logistic_confirmation_list'),
    path('logistic-confirmation/<str:transport_number>/', logistic_confirmation_detail_view, name='logistic_confirmation_detail'),
    path('rejected-transports/', rejected_transports_list_view, name='rejected_transports_list'),
    path('rejected-transports/<str:transport_number>/', rejected_transport_detail_view, name='rejected_transport_detail'),
    # Supply Settlement
    path('supply-settlement/', supply_settlement_list_view, name='supply_settlement_list'),
    path('supply-settlement/<str:order_number>/', supply_settlement_detail_view, name='supply_settlement_detail'),
    path('supply-settlement/<str:order_number>/skip/', skip_supply_settlement_view, name='skip_supply_settlement'),
    path('supply-settlement-approval/', supply_settlement_approval_list_view, name='supply_settlement_approval_list'),
    path('supply-settlement-approval/<str:order_number>/', supply_settlement_approval_detail_view, name='supply_settlement_approval_detail'),

]
