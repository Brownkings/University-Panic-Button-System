from django.urls import path
from . import views

urlpatterns = [
    path('feedback/', views.feedback_create_view, name='feedback_general'),
    path('feedback/<int:alert_id>/', views.feedback_create_view, name='feedback_create'),
    path('usability-test/', views.usability_test_view, name='usability_test'),
    path('feedback/usability/record/', views.api_record_usability_metric, name='api_record_usability_metric'),
]
