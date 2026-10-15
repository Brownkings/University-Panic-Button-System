from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('verify-email/<str:uidb64>/<str:token>/', views.verify_email_link_view, name='verify_email_link'),
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/done/', views.password_reset_done_view, name='password_reset_done'),
    path('password-reset-confirm/<str:uidb64>/<str:token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset-complete/', views.password_reset_complete_view, name='password_reset_complete'),
    path('logout/', views.logout_view, name='logout'),
    path('role-redirect/', views.role_redirect_view, name='role_redirect'),
    path('admin/users/', views.user_management_view, name='user_management'),
    path('admin/users/create/', views.admin_create_user_view, name='admin_create_user'),
    path('admin/users/<int:user_id>/update-role/', views.update_user_role_view, name='update_user_role'),
    path('admin/users/<int:user_id>/toggle-status/', views.toggle_user_status_view, name='toggle_user_status'),
    path('admin/users/<int:user_id>/send-reset/', views.admin_send_reset_email_view, name='admin_send_reset_email'),
]
