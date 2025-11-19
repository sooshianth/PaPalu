from django.urls import path
from .views.field_access import field_access_bulk_upload_view, download_field_access_template

app_name = 'access'

urlpatterns = [
    path('field-access/bulk-upload/', field_access_bulk_upload_view, name='field_access_bulk_upload'),
    path('field-access/template.xlsx', download_field_access_template, name='field_access_template'),
]