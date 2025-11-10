from django.urls import path
from .views.login_view import unified_login_view
from .views.logout_view import logout_view

urlpatterns = [
    path('login/', unified_login_view, name='unified_login'),
    path('logout/', logout_view, name='logout'),
]

