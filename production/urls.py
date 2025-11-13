from django.urls import path
from .views import program_views

app_name = 'production'

urlpatterns = [
    path('program/create/', program_views.create_program_view, name='program_create'),
    path('program/<int:program_id>/edit/', program_views.edit_program_view, name='program_edit'),
    path('program/list/', program_views.program_list_view, name='program_list'),
]