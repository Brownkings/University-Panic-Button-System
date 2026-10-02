from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('logout/', views.logout_view, name='logout'),
    path('role-redirect/', views.role_redirect_view, name='role_redirect'),
    path('admin/users/', views.user_management_view, name='user_management'),
    path('admin/users/<int:user_id>/update-role/', views.update_user_role_view, name='update_user_role'),
    path('admin/users/<int:user_id>/toggle-status/', views.toggle_user_status_view, name='toggle_user_status'),
]
