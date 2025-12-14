from django.urls import path
from distribution.views.shipping_announcement_view import (
    shipping_announcement_list_view,
    shipping_announcement_process_view,
    shipping_announcement_single_view
)
from distribution.views.vehicle_recruitment_view import (
    vehicle_recruitment_list_view,
    create_transport_view,
    complete_vehicle_recruitment_view
)
from distribution.views.vehicle_entry_view import (
    vehicle_entry_list_view,
    register_vehicle_entry_view,
    get_driver_info_by_national_id_view
)
from distribution.views.loading_exit_view import (
    loading_exit_list_view,
    register_loading_exit_view,
    create_bank_account_ajax_view
)
from distribution.views.waybill_registration_view import (
    waybill_list_view,
    register_waybill_view
)
from distribution.views.exit_list_view import (
    exit_list_view,
    print_waybill_pdf_view,
    mark_vehicle_exited_view
)

app_name = 'distribution'

urlpatterns = [
    path('shipping-announcement/', shipping_announcement_list_view, name='shipping_announcement_list'),
    path('shipping-announcement/process/', shipping_announcement_process_view, name='shipping_announcement_process'),
    path('shipping-announcement/single/', shipping_announcement_single_view, name='shipping_announcement_single'),
    path('vehicle-recruitment/', vehicle_recruitment_list_view, name='vehicle_recruitment_list'),
    path('vehicle-recruitment/<str:allocation_number>/create-transport/', create_transport_view, name='create_transport'),
    path('vehicle-recruitment/<str:allocation_number>/complete/', complete_vehicle_recruitment_view, name='complete_vehicle_recruitment'),
    path('vehicle-entry/', vehicle_entry_list_view, name='vehicle_entry_list'),
    path('vehicle-entry/<str:waybill_number>/register/', register_vehicle_entry_view, name='register_vehicle_entry'),
    path('vehicle-entry/get-driver-info/', get_driver_info_by_national_id_view, name='get_driver_info_by_national_id'),
    path('loading-exit/', loading_exit_list_view, name='loading_exit_list'),
    path('loading-exit/<str:waybill_number>/register/', register_loading_exit_view, name='register_loading_exit'),
    path('loading-exit/<str:waybill_number>/create-account/', create_bank_account_ajax_view, name='create_bank_account_ajax'),
    path('waybill/', waybill_list_view, name='waybill_list'),
    path('waybill/<str:waybill_number>/register/', register_waybill_view, name='register_waybill'),
    path('exit/', exit_list_view, name='exit_list'),
    path('exit/<str:waybill_number>/print-pdf/', print_waybill_pdf_view, name='print_waybill_pdf'),
    path('exit/<str:waybill_number>/mark-exited/', mark_vehicle_exited_view, name='mark_vehicle_exited'),
]