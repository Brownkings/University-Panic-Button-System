from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'role_name', 'description')
    search_fields = ('role_name',)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'full_name', 'institutional_id', 'email', 'role', 'is_verified', 'is_staff')
    list_filter = ('role', 'is_verified', 'is_staff', 'is_superuser')
    search_fields = ('username', 'full_name', 'institutional_id', 'email')
    ordering = ('institutional_id',)

    fieldsets = UserAdmin.fieldsets + (
        ('UPBS Student/Staff Profile', {
            'fields': ('full_name', 'institutional_id', 'contact_number', 'role', 'is_verified', 'otp_code')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('UPBS Student/Staff Profile', {
            'fields': ('full_name', 'institutional_id', 'contact_number', 'role', 'email')
        }),
    )
