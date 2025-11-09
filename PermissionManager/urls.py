from django.urls import path
from . import views

app_name = 'permission_manager'

urlpatterns = [
    path('', views.task_permissions_view, name='home'),
    path('task-permissions/', views.task_permissions_view, name='task_permissions'),
    path('roles/', views.roles_view, name='roles'),
    path('users/', views.users_view, name='users'),
    
    # API endpoints
    path('api/save-task-permissions/', views.save_task_permissions, name='api_save_task_permissions'),
    path('api/add-task-permission/', views.add_task_permission, name='api_add_task_permission'),
    path('api/delete-task-permission/', views.delete_task_permission, name='api_delete_task_permission'),
]
