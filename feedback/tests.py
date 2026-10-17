import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import Role, User
from alerts.models import EmergencyAlert, Location
from feedback.models import Feedback, UsabilityMetric


class FeedbackAndUsabilityTests(TestCase):
    """
    Validates user feedback collection and usability telemetry (feedback app):
    - User feedback submission with rating and comments
    - Linking feedback to specific emergency alerts
    - Usability evaluation runner view (Phase 4 rubric compliance)
    - Stopwatch telemetry logging API endpoint
    - Model string representations
    """

    def setUp(self):
        self.client = Client()

        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student")

        self.student = User.objects.create_user(
            username="student_tester",
            full_name="Brown Nkosi",
            institutional_id="202474004",
            email="student@campus.ac.za",
            contact_number="+27712345678",
            role=self.role_student,
            password="Password123!",
            is_verified=True
        )

        self.alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_RESOLVED,
            alert_type=EmergencyAlert.TYPE_STANDARD
        )
        Location.objects.create(
            alert=self.alert,
            latitude=Decimal("-28.742050"),
            longitude=Decimal("24.765100"),
            description="East Campus Residence"
        )

    def test_feedback_create_view_get(self):
        """GET feedback form renders successfully with recent feedback records."""
        self.client.login(username="student_tester", password="Password123!")
        response = self.client.get(reverse('feedback_general'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('recent_feedbacks', response.context)

    def test_feedback_create_view_post_unlinked(self):
        """POST general feedback without specific alert linkage."""
        self.client.login(username="student_tester", password="Password123!")
        post_data = {
            'rating': 5,
            'comments': 'Campus patrol officers arrived very quickly.'
        }
        response = self.client.post(reverse('feedback_general'), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user_dashboard'))

        fb = Feedback.objects.filter(user=self.student).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.comments, 'Campus patrol officers arrived very quickly.')
        self.assertIsNone(fb.alert)

    def test_feedback_create_view_post_linked_alert(self):
        """POST feedback explicitly tied to an EmergencyAlert."""
        self.client.login(username="student_tester", password="Password123!")
        post_data = {
            'alert_id': self.alert.id,
            'rating': 4,
            'comments': 'Resolved safely, thanks team.'
        }
        response = self.client.post(reverse('feedback_create', args=[self.alert.id]), data=post_data)
        self.assertEqual(response.status_code, 302)

        fb = Feedback.objects.filter(alert=self.alert).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 4)
        self.assertEqual(fb.alert, self.alert)

    def test_feedback_string_representation(self):
        """Verifies Feedback model string output."""
        fb = Feedback.objects.create(
            user=self.student,
            rating=5,
            comments="Excellent service"
        )
        self.assertEqual(str(fb), f"Feedback #{fb.id} (5 Stars) by Brown Nkosi")

    def test_usability_runner_view_get(self):
        """GET usability evaluation runner displays metrics table and SUS benchmarks."""
        self.client.login(username="student_tester", password="Password123!")
        UsabilityMetric.objects.create(
            user=self.student,
            task_name="Trigger Emergency Alert",
            completion_time_seconds=1.85,
            is_successful=True,
            error_count=0,
            sus_score=92.5
        )
        response = self.client.get(reverse('usability_test'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('metrics', response.context)
        self.assertIn('avg_sus', response.context)
        self.assertEqual(len(response.context['metrics']), 1)

    def test_api_record_usability_metric_success(self):
        """POST /feedback/usability/record/ successfully saves metric."""
        self.client.login(username="student_tester", password="Password123!")
        payload = {
            'task_name': 'Cancel False Alarm within 3s',
            'completion_time_seconds': 2.10,
            'is_successful': True,
            'error_count': 0,
            'sus_score': 88.0
        }
        response = self.client.post(
            reverse('api_record_usability_metric'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        metric = UsabilityMetric.objects.get(id=data['metric_id'])
        self.assertEqual(metric.task_name, 'Cancel False Alarm within 3s')
        self.assertEqual(metric.completion_time_seconds, 2.10)
        self.assertTrue(metric.is_successful)
        self.assertEqual(metric.sus_score, 88.0)

    def test_api_record_usability_metric_invalid_payload(self):
        """POST malformed payload returns 400 error."""
        self.client.login(username="student_tester", password="Password123!")
        response = self.client.post(
            reverse('api_record_usability_metric'),
            data="NOT_JSON",
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_usability_metric_string_representation(self):
        """Verifies UsabilityMetric string output."""
        metric = UsabilityMetric.objects.create(
            user=self.student,
            task_name="Acknowledge Alert",
            completion_time_seconds=3.4,
            is_successful=True,
            error_count=0
        )
        self.assertEqual(str(metric), "Usability Test: Acknowledge Alert - 3.4s (Errors: 0)")
