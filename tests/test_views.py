import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import Role, User
from alerts.models import EmergencyAlert, Location, SecurityOfficer, AlertResponse
from incidents.models import IncidentReport
from feedback.models import Feedback, UsabilityMetric


class UPBSViewTests(TestCase):
    """
    Validates end-to-end view controllers, API endpoints, RBAC permissions, and state transitions.
    """

    def setUp(self):
        self.client = Client()

        # Roles
        self.role_student = Role.objects.create(role_name=Role.STUDENT)
        self.role_security = Role.objects.create(role_name=Role.SECURITY)
        self.role_admin = Role.objects.create(role_name=Role.ADMIN)

        # Student user
        self.student = User.objects.create_user(
            username="student_user",
            full_name="Brown Nkosi",
            institutional_id="202474004",
            email="student@campus.ac.za",
            contact_number="+27712345678",
            role=self.role_student,
            password="password123",
            is_verified=True
        )

        # Security Officer
        self.sec_user = User.objects.create_user(
            username="security_user",
            full_name="Sgt. Dlamini",
            institutional_id="SEC100",
            email="officer@campus.ac.za",
            contact_number="+27829991111",
            role=self.role_security,
            password="password123",
            is_staff=True,
            is_verified=True
        )
        self.officer = SecurityOfficer.objects.create(
            user=self.sec_user,
            officer_name="Sgt. Dlamini",
            badge_number="BADGE-100",
            on_duty=True
        )

        # Admin user
        self.admin_user = User.objects.create_user(
            username="admin_user",
            full_name="Campus Admin",
            institutional_id="ADM001",
            email="admin@campus.ac.za",
            contact_number="+27820000000",
            role=self.role_admin,
            password="password123",
            is_staff=True,
            is_superuser=True,
            is_verified=True
        )

    def test_unauthenticated_redirect(self):
        """Unauthenticated requests must redirect to login."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_student_login_and_role_redirect(self):
        """Student login redirects to emergency panic home."""
        login_success = self.client.login(username='student_user', password='password123')
        self.assertTrue(login_success)

        response = self.client.get(reverse('role_redirect'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_security_login_and_role_redirect(self):
        """Security login redirects to security console."""
        self.client.login(username='security_user', password='password123')
        response = self.client.get(reverse('role_redirect'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('security_dashboard'))

    def test_trigger_emergency_alert_api(self):
        """Tests emergency panic button trigger POST endpoint."""
        self.client.login(username='student_user', password='password123')

        payload = {
            'alert_type': 'MEDICAL',
            'latitude': -28.742050,
            'longitude': 24.765100,
            'accuracy': 4.5,
            'description': 'Student Center Hall B'
        }

        response = self.client.post(
            reverse('trigger_alert_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'SENT')

        # Verify DB records created
        alert = EmergencyAlert.objects.get(id=data['alert_id'])
        self.assertEqual(alert.user, self.student)
        self.assertEqual(alert.alert_type, 'MEDICAL')
        self.assertEqual(alert.location.description, 'Student Center Hall B')

    def test_security_access_control(self):
        """Students must not be allowed to access security console."""
        self.client.login(username='student_user', password='password123')
        response = self.client.get(reverse('security_dashboard'))
        self.assertEqual(response.status_code, 403)

        # Security officer should have full access
        self.client.login(username='security_user', password='password123')
        response = self.client.get(reverse('security_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_alert_lifecycle_state_machine(self):
        """Tests transitions: SENT -> RECEIVED -> DISPATCHED -> RESOLVED."""
        # Create alert as student
        alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_STANDARD
        )
        Location.objects.create(
            alert=alert,
            latitude=Decimal("-28.742000"),
            longitude=Decimal("24.765000"),
            description="Residence"
        )

        # Login as security officer to progress alert
        self.client.login(username='security_user', password='password123')

        # 1. Acknowledge
        resp = self.client.post(
            reverse('api_update_alert_status', args=[alert.id]),
            data=json.dumps({'status': 'RECEIVED'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'RECEIVED')

        # 2. Dispatch
        resp = self.client.post(
            reverse('api_update_alert_status', args=[alert.id]),
            data=json.dumps({'status': 'DISPATCHED'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'DISPATCHED')

        # 3. Resolve with notes
        resp = self.client.post(
            reverse('api_update_alert_status', args=[alert.id]),
            data=json.dumps({'status': 'RESOLVED', 'response_notes': 'All clear on site'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, 'RESOLVED')
        self.assertIsNotNone(alert.resolved_at)

    def test_incident_report_submission(self):
        """Tests incident report submission with form validation."""
        self.client.login(username='student_user', password='password123')

        post_data = {
            'category': 'THEFT',
            'location_name': 'Library Level 1',
            'description': 'Backpack left unattended was removed.'
        }

        response = self.client.post(reverse('incident_create'), data=post_data)
        self.assertEqual(response.status_code, 302) # Redirects upon success
        self.assertTrue(IncidentReport.objects.filter(location_name='Library Level 1').exists())

    def test_usability_metric_recording(self):
        """Tests stopwatch and error recording for Phase 4 usability evaluation."""
        self.client.login(username='student_user', password='password123')

        payload = {
            'task_name': 'Locate & Trigger Panic Button',
            'completion_time_seconds': 1.65,
            'error_count': 0,
            'is_successful': True,
            'sus_score': 95.0
        }

        response = self.client.post(
            reverse('api_record_usability_metric'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(UsabilityMetric.objects.filter(id=data['metric_id']).exists())
