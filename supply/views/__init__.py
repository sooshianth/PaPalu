"""
Supply Views Module
این ماژول شامل تمام view های مربوط به دامنه تامین است
ساختار ماژولار برای بهبود نگهداری و خوانایی کد
"""

# Supplier Views
from .supplier_views import (
    supply_home_view,
    create_supplier_view,
    supplier_list_view,
    supplier_detail_view,
    supplier_edit_view,
)

# Raw Material Views
from .raw_material_views import (
    define_basic_material_view,
    price_inquiry_modal_view,
)

# Purchase Order Views
from .purchase_order_views import (
    purchase_order_management_view,
    create_procurement_purchase_order_view,
    procurement_purchase_order_detail_view,
    edit_procurement_purchase_order_view,
    delete_procurement_purchase_order_view,
    transition_procurement_purchase_order_status_view,
    confirm_procurement_purchase_order_payment_view,
)

# Purchase Transport Views
from .purchase_transport_views import (
    purchase_transport_list_view,
    create_purchase_transport_view,
    purchase_transport_detail_view,
    edit_purchase_transport_view,
    delete_purchase_transport_view,
    transition_purchase_transport_status_view,
    get_purchase_order_info_api,
)

# Car Entrance Views
from .carentrance_views import (
    car_entrance_list_view,
    register_driver_for_transport_view,
    mark_vehicle_entered_view,
    driver_lookup_api,
    car_exit_list_view,
    mark_vehicle_exited_view,
)

# Warehouse Delivery Views
from .warehouse_delivery_views import (
    warehouse_delivery_list_view,
    warehouse_delivery_detail_view,
    guard_vehicle_exit_view,
)

# Logistic Confirmation Views
from .logistic_confirmation_views import (
    logistic_confirmation_list_view,
    logistic_confirmation_detail_view,
)

# Upload Fare Payment Documents Views
from .upload_fare_payment_docs_views import (
    upload_fare_payment_docs_list_view,
    upload_fare_payment_docs_detail_view,
)

__all__ = [
    # Supplier Views
    'supply_home_view',
    'create_supplier_view',
    'supplier_list_view',
    'supplier_detail_view',
    'supplier_edit_view',
    # Raw Material Views
    'define_basic_material_view',
    'price_inquiry_modal_view',
    # Purchase Order Views
    'purchase_order_management_view',
    'create_procurement_purchase_order_view',
    'procurement_purchase_order_detail_view',
    'edit_procurement_purchase_order_view',
    'delete_procurement_purchase_order_view',
    'transition_procurement_purchase_order_status_view',
    'confirm_procurement_purchase_order_payment_view',
    # Purchase Transport Views
    'purchase_transport_list_view',
    'create_purchase_transport_view',
    'purchase_transport_detail_view',
    'edit_purchase_transport_view',
    'delete_purchase_transport_view',
    'transition_purchase_transport_status_view',
    'get_purchase_order_info_api',
    # Car Entrance Views
    'car_entrance_list_view',
    'register_driver_for_transport_view',
    'mark_vehicle_entered_view',
    'driver_lookup_api',
    'car_exit_list_view',
    'mark_vehicle_exited_view',
    # Warehouse Delivery Views
    'warehouse_delivery_list_view',
    'warehouse_delivery_detail_view',
    'guard_vehicle_exit_view',
    # Logistic Confirmation Views
    'logistic_confirmation_list_view',
    'logistic_confirmation_detail_view',
    # Upload Fare Payment Documents Views
    'upload_fare_payment_docs_list_view',
    'upload_fare_payment_docs_detail_view',
]

