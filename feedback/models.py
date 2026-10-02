from django.db import models
from django.conf import settings
from alerts.models import EmergencyAlert


class Feedback(models.Model):
    """
    Feedback entity as specified in Phase 3 Section 3.4.
    Collects user satisfaction ratings and suggestions to support continuous iterative design.
    """
    RATING_CHOICES = [
        (1, '1 - Very Dissatisfied (Unacceptable response)'),
        (2, '2 - Dissatisfied (Slow or unclear)'),
        (3, '3 - Neutral (Adequate response)'),
        (4, '4 - Satisfied (Fast & professional)'),
        (5, '5 - Very Satisfied (Exceptional rapid response)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedbacks')
    alert = models.ForeignKey(
        EmergencyAlert,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='feedbacks',
        help_text="Optional link to specific emergency alert"
    )
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=5)
    comments = models.TextField(help_text="User feedback, suggestions, or critique")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback #{self.id} ({self.rating} Stars) by {self.user.full_name}"


class UsabilityMetric(models.Model):
    """
    Built-in model to satisfy NPRT630 Phase 4 Marking Rubric:
    'Measure task completion times, error rates, user satisfaction.'
    Enables tracking of empirical metrics during live demonstrations and user testing.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    task_name = models.CharField(max_length=100)
    completion_time_seconds = models.FloatField(help_text="Time taken to finish task in seconds")
    is_successful = models.BooleanField(default=True)
    error_count = models.PositiveIntegerField(default=0, help_text="Number of erroneous clicks or validation retries")
    sus_score = models.FloatField(null=True, blank=True, help_text="System Usability Scale score (0-100)")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Usability Test: {self.task_name} - {self.completion_time_seconds}s (Errors: {self.error_count})"
