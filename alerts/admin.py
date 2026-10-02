from django.contrib import admin
from .models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification


class LocationInline(admin.StackedInline):
    model = Location
    can_delete = False
    max_num = 1


class AlertResponseInline(admin.TabularInline):
    model = AlertResponse
    extra = 1


@admin.register(EmergencyAlert)
class EmergencyAlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'alert_type', 'status', 'timestamp', 'get_location_desc')
    list_filter = ('status', 'alert_type', 'timestamp')
    search_fields = ('user__full_name', 'user__institutional_id', 'location__description')
    inlines = [LocationInline, AlertResponseInline]

    def get_location_desc(self, obj):
        return obj.location.description if hasattr(obj, 'location') else "No GPS"
    get_location_desc.short_description = "Location"


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'alert', 'description', 'latitude', 'longitude', 'accuracy_meters')
    search_fields = ('description', 'alert__id')


@admin.register(SecurityOfficer)
class SecurityOfficerAdmin(admin.ModelAdmin):
    list_display = ('id', 'officer_name', 'badge_number', 'on_duty', 'current_post')
    list_filter = ('on_duty',)
    search_fields = ('officer_name', 'badge_number')


@admin.register(AlertResponse)
class AlertResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'alert', 'officer', 'status', 'dispatched_at', 'acknowledged_at')
    list_filter = ('status', 'dispatched_at')
    search_fields = ('officer__officer_name', 'officer__badge_number', 'alert__id')


@admin.register(PanicDevice)
class PanicDeviceAdmin(admin.ModelAdmin):
    list_display = ('id', 'device_identifier', 'device_type', 'user', 'is_active', 'last_active')
    list_filter = ('device_type', 'is_active')
    search_fields = ('device_identifier', 'user__username')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'alert', 'channel', 'recipient', 'delivery_status', 'sent_at')
    list_filter = ('channel', 'delivery_status')
    search_fields = ('recipient', 'message')
