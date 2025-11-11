from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

def redirect_to_login(request):
    """هدایت به صفحه لاگین برای کاربران غیر لاگین شده"""
    return redirect('unified_login')

@login_required
def home_view(request):
    """صفحه اصلی بعد از لاگین"""
    return render(request, 'home.html', {
        'user': request.user
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('permissions/', include('perm_manager.urls')),
    path('authentication/', include('authentication.urls')),
    path('home/', home_view, name='home'),
    path('', redirect_to_login, name='root'),
    path('accounting/', include('accounting.urls')),
    path('custody/', include('custody.urls')),
    path('distribution/', include('distribution.urls')),
    path('production/', include('production.urls')),
    path('sales/', include('sales.urls')),
    path('warehousing/', include('warehousing.urls')),
    path('access/', include('access.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
