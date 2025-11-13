from django.urls import path
from .views import program_views
from .views import production_declaration_view

app_name = 'production'

urlpatterns = [
    path('program/create/', program_views.create_program_view, name='program_create'),
    path('program/<int:program_id>/edit/', program_views.edit_program_view, name='program_edit'),
    path('program/list/', program_views.program_list_view, name='program_list'),
    path('declaration/', production_declaration_view.production_declaration_view, name='production_declaration'),
    path('declaration/crud/', production_declaration_view.production_program_crud_view, name='program_crud_create'),
    path('declaration/crud/<int:program_id>/', production_declaration_view.production_program_crud_view, name='program_crud'),
]