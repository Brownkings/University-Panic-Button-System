from django.contrib import admin
from .models import IncidentReport


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'category', 'user', 'location_name', 'status', 'created_at', 'has_media')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('user__full_name', 'location_name', 'description')

    def has_media(self, obj):
        return bool(obj.media_file)
    has_media.boolean = True
    has_media.short_description = "Evidence"
