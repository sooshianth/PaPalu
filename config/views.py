# views for custom error handlers (404, 500)
from django.shortcuts import render


def custom_page_not_found_view(request, exception):
    """صفحهٔ سفارشی برای خطای 404 - صفحه یافت نشد."""
    return render(
        request,
        '404.html',
        {'exception': exception, 'error_code': 404},
        status=404,
    )


def custom_server_error_view(request):
    """صفحهٔ سفارشی برای خطای 500 - خطای سرور."""
    return render(
        request,
        '500.html',
        {'error_code': 500},
        status=500,
    )
