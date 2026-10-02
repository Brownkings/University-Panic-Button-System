from django.urls import path
from . import views

urlpatterns = [
    path('analytics/reports/', views.reports_analytics_view, name='reports_analytics'),
    path('analytics/export-csv/', views.export_reports_csv, name='export_reports_csv'),
]
