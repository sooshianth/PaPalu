from django.urls import path
from . import views

app_name = 'permission_manager'

urlpatterns = [
    path('', views.permissions_home_view, name='home'),
    path('task-permissions/', views.task_permissions_view, name='task_permissions'),
    path('roles/', views.roles_view, name='roles'),
    path('users/', views.users_view, name='users'),
    
    # API endpoints
    path('api/save-task-permissions/', views.save_task_permissions, name='api_save_task_permissions'),
    path('api/add-task-permission/', views.add_task_permission, name='api_add_task_permission'),
    path('api/delete-task-permission/', views.delete_task_permission, name='api_delete_task_permission'),
    path('api/add-role/', views.add_role, name='api_add_role'),
    path('api/update-role/', views.update_role, name='api_update_role'),
    path('api/delete-role/', views.delete_role, name='api_delete_role'),
    path('api/save-user-assignments/', views.save_user_assignments, name='save_user_assignments'),
]
