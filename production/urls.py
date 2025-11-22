from django.urls import path
from .views import program_views
from .views import production_declaration_view
from .views import cargo_announcement
from .views import warehouse_production_view

app_name = 'production'

urlpatterns = [
    path('program/create/', program_views.create_program_view, name='program_create'),
    path('program/<int:program_id>/edit/', program_views.edit_program_view, name='program_edit'),
    path('program/list/', program_views.program_list_view, name='program_list'),
    path('program/drafts/', program_views.program_drafts_view, name='program_drafts'),
    path('announcement/', cargo_announcement.cargo_announcement_view, name='cargo_announcement'),
    path('declaration/', production_declaration_view.production_declaration_view, name='production_declaration'),
    path('declaration/crud/', production_declaration_view.production_program_crud_view, name='program_crud_create'),
    path('declaration/crud/<int:program_id>/', production_declaration_view.production_program_crud_view, name='program_crud'),
    path('declaration/archived/', production_declaration_view.archived_programs_view, name='archived_programs'),
    
    # Warehouse production declaration views
    path('warehouse/declaration/', warehouse_production_view.warehouse_production_list, name='warehouse_production_list'),
    path('warehouse/declaration/<int:program_id>/', warehouse_production_view.warehouse_production_detail, name='warehouse_production_detail'),
    path('warehouse/declaration/<int:program_id>/approve/', warehouse_production_view.warehouse_approve_program, name='warehouse_approve_program'),
    path('warehouse/declaration/<int:program_id>/disapprove/', warehouse_production_view.warehouse_disapprove_program, name='warehouse_disapprove_program'),
    path('api/stock-entry/<int:entry_id>/', warehouse_production_view.get_stock_entry_detail, name='api_stock_entry_detail'),
]