"""
UPBS Project Root URL Configuration
Connects accounts, alerts, incidents, analytics, and feedback apps.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda req: redirect('home'), name='root_redirect'),
    path('', include('accounts.urls')),
    path('', include('alerts.urls')),
    path('', include('incidents.urls')),
    path('', include('analytics.urls')),
    path('', include('feedback.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
