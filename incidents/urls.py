from django.urls import path
from . import views

urlpatterns = [
    path('incidents/new/', views.incident_create_view, name='incident_create'),
    path('incidents/<int:report_id>/', views.incident_detail_view, name='incident_detail'),
]
