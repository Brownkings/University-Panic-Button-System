from django.db import models
from django.conf import settings
from django.utils import timezone


class PanicDevice(models.Model):
    """
    PanicDevice entity as specified in Phase 3 ERD Section 3.3.
    Represents hardware or software panic trigger source (Web PWA, Physical IoT Button, Mobile).
    """
    DEVICE_TYPES = [
        ('WEB_CLIENT', 'Web Browser Client'),
        ('MOBILE_PWA', 'Mobile PWA Client'),
        ('PHYSICAL_IOT', 'Physical IoT Hardware Button'),
    ]

    device_identifier = models.CharField(max_length=100, unique=True, help_text="Unique hardware/device token")
    device_type = models.CharField(max_length=50, choices=DEVICE_TYPES, default='WEB_CLIENT')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='panic_devices')
    is_active = models.BooleanField(default=True)
    last_active = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_device_type_display()} - {self.device_identifier} ({self.user.username})"


class EmergencyAlert(models.Model):
    """
    EmergencyAlert entity as specified in Phase 3 Section 3.4.
    Core event generated when panic button is activated.
    """
    STATUS_SENT = 'SENT'
    STATUS_RECEIVED = 'RECEIVED'
    STATUS_DISPATCHED = 'DISPATCHED'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_RECEIVED, 'Received by Security'),
        (STATUS_DISPATCHED, 'Officer Dispatched'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_CANCELLED, 'Cancelled (False Alarm)'),
    ]

    TYPE_STANDARD = 'STANDARD'
    TYPE_SILENT = 'SILENT'
    TYPE_MEDICAL = 'MEDICAL'
    TYPE_FIRE = 'FIRE'
    TYPE_CRIME = 'CRIME'

    ALERT_TYPE_CHOICES = [
        (TYPE_STANDARD, 'Standard Emergency'),
        (TYPE_SILENT, 'Silent Panic'),
        (TYPE_MEDICAL, 'Medical Emergency'),
        (TYPE_FIRE, 'Fire Outbreak'),
        (TYPE_CRIME, 'Active Threat / Crime'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alerts')
    panic_device = models.ForeignKey(PanicDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name='alerts')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SENT, db_index=True)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, default=TYPE_STANDARD)
    cancellation_reason = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Alert #{self.id} [{self.get_alert_type_display()}] - {self.user.full_name} ({self.status})"


class Location(models.Model):
    """
    Location entity as specified in Phase 3 Section 3.4 & 3.5.
    One-to-One relationship with EmergencyAlert to pinpoint exact coordinates and campus description.
    """
    alert = models.OneToOneField(EmergencyAlert, on_delete=models.CASCADE, related_name='location')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="GPS Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, help_text="GPS Longitude")
    accuracy_meters = models.FloatField(null=True, blank=True, help_text="Horizontal accuracy radius in meters")
    description = models.CharField(max_length=255, help_text="Campus building/room or geographic description")

    def __str__(self):
        return f"Location for Alert #{self.alert_id}: {self.description} ({self.latitude}, {self.longitude})"


class SecurityOfficer(models.Model):
    """
    SecurityOfficer entity as specified in Phase 3 Section 3.3.
    Campus security personnel responsible for responding to alerts.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='officer_profile')
    officer_name = models.CharField(max_length=100)
    badge_number = models.CharField(max_length=30, unique=True)
    on_duty = models.BooleanField(default=True, db_index=True)
    current_post = models.CharField(max_length=100, blank=True, default="Central Security Desk")

    def save(self, *args, **kwargs):
        if not self.officer_name and self.user:
            self.officer_name = self.user.full_name or self.user.username
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Officer {self.officer_name} (Badge: {self.badge_number})"


class AlertResponse(models.Model):
    """
    Associative entity handling the Many-to-Many relationship between
    EmergencyAlert and SecurityOfficer (Phase 3 Section 3.5).
    Allows multiple officers per alert and flexible operational dispatch.
    """
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_EN_ROUTE = 'EN_ROUTE'
    STATUS_ON_SCENE = 'ON_SCENE'
    STATUS_RESOLVED = 'RESOLVED'

    RESPONSE_STATUS_CHOICES = [
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_EN_ROUTE, 'En Route'),
        (STATUS_ON_SCENE, 'On Scene'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, related_name='responses')
    officer = models.ForeignKey(SecurityOfficer, on_delete=models.CASCADE, related_name='assigned_alerts')
    dispatched_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    response_notes = models.TextField(blank=True, help_text="Field report or action taken by security officer")
    status = models.CharField(max_length=20, choices=RESPONSE_STATUS_CHOICES, default=STATUS_ASSIGNED)

    class Meta:
        unique_together = ('alert', 'officer')

    def __str__(self):
        return f"Response for Alert #{self.alert_id} by Officer {self.officer.badge_number} ({self.status})"


class Notification(models.Model):
    """
    Notification entity as specified in Phase 3 Section 3.3.
    Triggers multi-channel delivery (SMS, In-App audio, Email) for rapid dispatch.
    """
    CHANNEL_SMS = 'SMS'
    CHANNEL_IN_APP = 'IN_APP'
    CHANNEL_EMAIL = 'EMAIL'

    CHANNEL_CHOICES = [
        (CHANNEL_SMS, 'SMS Alert'),
        (CHANNEL_IN_APP, 'In-App System Alert'),
        (CHANNEL_EMAIL, 'Email Dispatch'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_FAILED, 'Failed'),
    ]

    alert = models.ForeignKey(EmergencyAlert, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.CharField(max_length=100, help_text="Recipient phone number or user address")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_SMS)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DELIVERED)

    def __str__(self):
        return f"{self.channel} to {self.recipient} [{self.delivery_status}]"
