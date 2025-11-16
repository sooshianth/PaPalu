from django.urls import path
from . import views

app_name = 'permission_manager'

urlpatterns = [
    path('', views.permissions_home_view, name='home'),
    path('task-permissions/', views.task_permissions_view, name='task_permissions'),
    path('field-permissions/', views.field_permissions_view, name='field_permissions'),
    path('roles/', views.roles_view, name='roles'),
    path('users/', views.users_view, name='users'),
    
    # API endpoints - Task Permissions
    path('api/save-task-permissions/', views.save_task_permissions, name='api_save_task_permissions'),
    path('api/add-task-permission/', views.add_task_permission, name='api_add_task_permission'),
    path('api/delete-task-permission/', views.delete_task_permission, name='api_delete_task_permission'),
    
    # API endpoints - Field Permissions
    path('api/add-field-permission/', views.add_field_permission, name='api_add_field_permission'),
    path('api/delete-field-permission/', views.delete_field_permission, name='api_delete_field_permission'),
    path('api/save-field-permissions/', views.save_field_permissions, name='api_save_field_permissions'),
    path('api/add-managed-field/', views.add_managed_field, name='api_add_managed_field'),
    path('api/delete-managed-field/', views.delete_managed_field, name='api_delete_managed_field'),
    
    # API endpoints - Roles and Users
    path('api/add-role/', views.add_role, name='api_add_role'),
    path('api/update-role/', views.update_role, name='api_update_role'),
    path('api/delete-role/', views.delete_role, name='api_delete_role'),
    path('api/save-user-assignments/', views.save_user_assignments, name='save_user_assignments'),
]
