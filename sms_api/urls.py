from django.urls import path
from . import views

app_name = 'sms_api'

urlpatterns = [
    path('queue/', views.sms_queue, name='sms_queue'),
    path('logs/', views.sms_log, name='sms_log'),
    
    # عملیات روی پیامک‌ها
    path('delete/<int:sms_id>/', views.delete_sms, name='delete_sms'),
    path('suspend/<int:sms_id>/', views.suspend_sms, name='suspend_sms'),
    path('resume/<int:sms_id>/', views.resume_sms, name='resume_sms'),
    path('send-now/<int:sms_id>/', views.send_sms_now, name='send_now'),
    path('retry/<int:sms_id>/', views.retry_sms, name='retry_sms'),
    path('process-queue/', views.process_sms_queue_manually, name='process_queue'),
      
    
] 