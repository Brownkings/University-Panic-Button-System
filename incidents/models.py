from django.db import models
from django.conf import settings


class IncidentReport(models.Model):
    """
    IncidentReport entity as specified in Phase 3 Section 3.4.
    Allows students/staff to submit detailed reports with category, description,
    campus location, and optional media file upload.
    """
    CATEGORY_THEFT = 'THEFT'
    CATEGORY_HARASSMENT = 'HARASSMENT'
    CATEGORY_VANDALISM = 'VANDALISM'
    CATEGORY_MEDICAL = 'MEDICAL'
    CATEGORY_SUSPICIOUS = 'SUSPICIOUS_ACTIVITY'
    CATEGORY_HAZARD = 'SAFETY_HAZARD'
    CATEGORY_OTHER = 'OTHER'

    CATEGORY_CHOICES = [
        (CATEGORY_THEFT, 'Theft / Burglary'),
        (CATEGORY_HARASSMENT, 'Harassment / GBV'),
        (CATEGORY_VANDALISM, 'Property Vandalism'),
        (CATEGORY_MEDICAL, 'Medical Emergency / Injury'),
        (CATEGORY_SUSPICIOUS, 'Suspicious Activity / Intruder'),
        (CATEGORY_HAZARD, 'Campus Safety Hazard (Fire/Electrical)'),
        (CATEGORY_OTHER, 'Other Incident'),
    ]

    STATUS_SUBMITTED = 'SUBMITTED'
    STATUS_REVIEW = 'UNDER_REVIEW'
    STATUS_ACTION = 'ACTION_TAKEN'
    STATUS_CLOSED = 'CLOSED'

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_REVIEW, 'Under Investigation'),
        (STATUS_ACTION, 'Action Taken'),
        (STATUS_CLOSED, 'Resolved & Closed'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='incident_reports')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    location_name = models.CharField(max_length=150, help_text="Campus area (e.g. Science Block Floor 2, East Res, Sports Grounds)")
    description = models.TextField(help_text="Detailed narrative of the incident")
    media_file = models.FileField(upload_to='incidents/%Y/%m/', blank=True, null=True, help_text="Optional photo/video evidence")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED, db_index=True)
    admin_notes = models.TextField(blank=True, help_text="Security / Admin resolution log")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Incident #{self.id} [{self.get_category_display()}] - {self.user.full_name}"
