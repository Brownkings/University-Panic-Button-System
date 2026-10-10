from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home_view, name='home'),
    path('dashboard/', views.user_dashboard_view, name='user_dashboard'),
    path('security/dashboard/', views.security_dashboard_view, name='security_dashboard'),
    path('alerts/trigger/', views.trigger_alert_api, name='trigger_alert_api'),
    path('alerts/api/live/', views.api_live_alerts, name='api_live_alerts'),
    path('alerts/api/status/<int:alert_id>/', views.api_alert_status, name='api_alert_status'),
    path('alerts/api/update-status/<int:alert_id>/', views.api_update_alert_status, name='api_update_alert_status'),
    path('alerts/tiles/kimberley/<int:z>/<int:x>/<int:y>.png', views.kimberley_map_tile, name='kimberley_map_tile'),
]
