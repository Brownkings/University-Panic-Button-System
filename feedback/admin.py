from django.contrib import admin
from .models import Feedback, UsabilityMetric


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'rating', 'alert', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__full_name', 'comments')


@admin.register(UsabilityMetric)
class UsabilityMetricAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_name', 'user', 'completion_time_seconds', 'is_successful', 'error_count', 'sus_score', 'recorded_at')
    list_filter = ('task_name', 'is_successful', 'recorded_at')
    search_fields = ('task_name', 'user__username')
