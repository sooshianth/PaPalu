from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from production.views import program_views  # kept for names, no direct routes

def redirect_to_login(request):
    """هدایت به صفحه لاگین برای کاربران غیر لاگین شده"""
    return redirect('unified_login')

def home_view(request):
    """صفحه اصلی بعد از لاگین"""
    if request.user.is_authenticated:
        return render(request, 'home.html', {
            'user': request.user
        })
    else:
        return redirect_to_login(request)
        
urlpatterns = [
    path('admin/', admin.site.urls),
    path('data-exflow/', include('data_exflow.urls')),
    path('permissions/', include('perm_manager.urls')),
    path('sms/', include('sms_api.urls')),
    path('authentication/', include('authentication.urls')),
    path('home/', home_view, name='home'),
    path('', home_view, name='root'),
    path('accounting/', include('accounting.urls')),
    path('distribution/', include('distribution.urls')),
    path('supply/', include('supply.urls')),
    path('production/', include('production.urls')),  # Use only namespaced production routes
    # Backward-compatible alias: some users attempt /product/create -> map to program create
    # path('product/create/', program_views.create_program_view, name='product_create_alias'),
    path('sales/', include('sales.urls')),
    path('warehousing/', include('warehousing.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)