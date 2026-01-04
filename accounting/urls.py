from django.urls import path
from accounting.views import (
    upload_fare_payment_docs_list_view,
    upload_fare_payment_docs_detail_view,
    uploaded_fare_payment_docs_list_view,
    uploaded_fare_payment_docs_detail_view,
)

app_name = 'accounting'

urlpatterns = [
    # Upload Fare Payment Documents
    path('upload-fare-payment-docs/', upload_fare_payment_docs_list_view, name='upload_fare_payment_docs_list'),
    path('upload-fare-payment-docs/<str:transport_number>/', upload_fare_payment_docs_detail_view, name='upload_fare_payment_docs_detail'),
    # Uploaded Fare Payment Documents List
    path('uploaded-fare-payment-docs/', uploaded_fare_payment_docs_list_view, name='uploaded_fare_payment_docs_list'),
    path('uploaded-fare-payment-docs/<str:transport_number>/', uploaded_fare_payment_docs_detail_view, name='uploaded_fare_payment_docs_detail'),
]
