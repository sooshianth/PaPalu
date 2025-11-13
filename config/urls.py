from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from production.views import program_views  # direct access to program views at root-level

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
    path('permissions/', include('perm_manager.urls')),
    path('authentication/', include('authentication.urls')),
    path('home/', home_view, name='home'),
    path('', home_view, name='root'),
    path('accounting/', include('accounting.urls')),
    path('custody/', include('custody.urls')),
    path('distribution/', include('distribution.urls')),
    path('production/', include('production.urls')),  # Ensure production URLs are included
    # Direct shortcuts (so /program/create works without /production/ prefix)
    path('program/create/', program_views.create_program_view, name='program_create_direct'),
    path('program/list/', program_views.program_list_view, name='program_list_direct'),
    path('program/<int:program_id>/edit/', program_views.edit_program_view, name='program_edit_direct'),
    # Backward-compatible alias: some users attempt /product/create -> map to program create
    path('product/create/', program_views.create_program_view, name='product_create_alias'),
    path('sales/', include('sales.urls')),
    path('warehousing/', include('warehousing.urls')),
    path('access/', include('access.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)