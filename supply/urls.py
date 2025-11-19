from django.urls import path
from .views.views import supply_home_view, define_basic_material_view

app_name = 'supply'

urlpatterns = [
    path('', supply_home_view, name='home'),
    path('definebasicmat/', define_basic_material_view, name='define_basic_material'),
]
