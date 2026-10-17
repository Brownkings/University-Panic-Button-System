import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import Role, User
from alerts.models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification
from alerts.views import haversine_meters, compass_bearing, is_within_kimberley


class AlertMathAndUtilityTests(TestCase):
    """Validates core GIS geospatial calculations, bearings, and coordinate bounding."""

    def test_haversine_meters(self):
        # Known distance between two points on SPU campus (~150m)
        dist = haversine_meters(-28.742050, 24.765100, -28.741500, 24.766000)
        self.assertTrue(50 < dist < 300)

        # Same point distance is 0.0
        dist_zero = haversine_meters(-28.742050, 24.765100, -28.742050, 24.765100)
        self.assertEqual(dist_zero, 0.0)

    def test_compass_bearing(self):
        # North bearing
        bearing_north = compass_bearing(-28.750000, 24.765000, -28.740000, 24.765000)
        self.assertTrue(bearing_north.startswith('N'))

        # South bearing
        bearing_south = compass_bearing(-28.740000, 24.765000, -28.750000, 24.765000)
        self.assertTrue(bearing_south.startswith('S'))

    def test_is_within_kimberley(self):
        self.assertTrue(is_within_kimberley(-28.742050, 24.765100))
        self.assertFalse(is_within_kimberley(0.0, 0.0))
        self.assertFalse(is_within_kimberley(95.0, 24.0)) # Out of range latitude
        self.assertFalse(is_within_kimberley('invalid', 'data'))


class EmergencyAlertWorkflowTests(TestCase):
    """
    Validates the Emergency Alert system (alerts app):
    - Panic button trigger API workflow
    - Rate limit protection
    - User dashboard active alert telemetry
    - Security CAD console RBAC and live polling
    - Status lifecycle transitions and officer response binding
    - Patrol vehicle telemetry broadcast
    """

    def setUp(self):
        self.client = Client()

        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student")
        self.role_security = Role.objects.create(role_name=Role.SECURITY, description="Security")
        self.role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin")

        self.student = User.objects.create_user(
            username="student_panic",
            full_name="Brown Nkosi",
            institutional_id="202474004",
            email="student@campus.ac.za",
            contact_number="+27712345678",
            role=self.role_student,
            password="Password123!",
            is_verified=True
        )

        self.sec_user = User.objects.create_user(
            username="sec_officer1",
            full_name="Officer Dlamini",
            institutional_id="SEC001",
            email="officer1@security.ac.za",
            contact_number="+27829991111",
            role=self.role_security,
            password="Password123!",
            is_staff=True,
            is_verified=True
        )

        self.officer = SecurityOfficer.objects.create(
            user=self.sec_user,
            officer_name="Officer Dlamini",
            badge_number="SPU-SEC-001",
            on_duty=True,
            latitude=Decimal("-28.741000"),
            longitude=Decimal("24.764000"),
            accuracy_meters=4.0
        )

    def test_trigger_alert_api_creates_records(self):
        """Verifies trigger_alert_api creates EmergencyAlert, Location, PanicDevice, and Notification."""
        self.client.login(username="student_panic", password="Password123!")

        payload = {
            'alert_type': EmergencyAlert.TYPE_MEDICAL,
            'latitude': -28.742050,
            'longitude': 24.765100,
            'accuracy': 5.0,
            'description': 'Main Library Ground Floor'
        }

        response = self.client.post(
            reverse('trigger_alert_api'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], EmergencyAlert.STATUS_SENT)
        self.assertEqual(data['redirect_url'], '/dashboard/')

        # Verify DB records
        alert = EmergencyAlert.objects.get(id=data['alert_id'])
        self.assertEqual(alert.user, self.student)
        self.assertEqual(alert.alert_type, EmergencyAlert.TYPE_MEDICAL)
        self.assertEqual(alert.status, EmergencyAlert.STATUS_SENT)

        # 1:1 Location check
        self.assertIsNotNone(alert.location)
        self.assertEqual(float(alert.location.latitude), -28.742050)
        self.assertEqual(float(alert.location.longitude), 24.765100)
        self.assertIn("Main Library", alert.location.description)

        # PanicDevice linkage
        self.assertIsNotNone(alert.panic_device)

        # Multi-channel notification generated
        notif = Notification.objects.filter(alert=alert).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.delivery_status, Notification.STATUS_DELIVERED)

    def test_trigger_alert_rate_limiting(self):
        """User cannot trigger more than 3 active alerts within 5 minutes."""
        self.client.login(username="student_panic", password="Password123!")

        payload = {
            'alert_type': EmergencyAlert.TYPE_STANDARD,
            'latitude': -28.742050,
            'longitude': 24.765100,
            'accuracy': 5.0,
            'description': 'Campus Gate 1'
        }

        # First 3 alerts succeed
        for _ in range(3):
            resp = self.client.post(reverse('trigger_alert_api'), data=json.dumps(payload), content_type='application/json')
            self.assertEqual(resp.status_code, 200)

        # 4th alert fails with 429 Rate Limit
        resp4 = self.client.post(reverse('trigger_alert_api'), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp4.status_code, 429)
        self.assertIn('Rate limit reached', resp4.json()['error'])

    def test_trigger_alert_non_post_rejected(self):
        self.client.login(username="student_panic", password="Password123!")
        response = self.client.get(reverse('trigger_alert_api'))
        self.assertEqual(response.status_code, 405)

    def test_user_dashboard_view_authenticated(self):
        """User dashboard displays active alert and alert history."""
        self.client.login(username="student_panic", password="Password123!")

        # Create alert
        alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_STANDARD
        )
        Location.objects.create(
            alert=alert,
            latitude=Decimal("-28.742000"),
            longitude=Decimal("24.765000"),
            description="Residence Block C"
        )

        response = self.client.get(reverse('user_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_alert'], alert)
        self.assertIn(alert, list(response.context['alerts_history']))

    def test_security_dashboard_access_control(self):
        """Student denied (403), officer allowed (200), mobile UA redirected (302)."""
        # Student access denied
        self.client.login(username="student_panic", password="Password123!")
        resp_student = self.client.get(reverse('security_dashboard'))
        self.assertEqual(resp_student.status_code, 403)

        # Security officer access allowed
        self.client.login(username="sec_officer1", password="Password123!")
        resp_officer = self.client.get(reverse('security_dashboard'))
        self.assertEqual(resp_officer.status_code, 200)

        # Mobile app client header redirect
        resp_mobile = self.client.get(reverse('security_dashboard'), HTTP_USER_AGENT='Mozilla/5.0 UPBSStudentPortal/2.0')
        self.assertEqual(resp_mobile.status_code, 302)
        self.assertRedirects(resp_mobile, reverse('home'))

    def test_api_live_alerts_polling(self):
        """Security officer polls /alerts/api/live/ and receives active queue telemetry."""
        # Create active alert
        alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_CRIME
        )
        Location.objects.create(
            alert=alert,
            latitude=Decimal("-28.742100"),
            longitude=Decimal("24.765200"),
            description="Science Lab Hallway"
        )

        self.client.login(username="sec_officer1", password="Password123!")

        # Poll with officer GPS heartbeat query parameters
        resp = self.client.get(
            reverse('api_live_alerts') + "?lat=-28.741000&lng=24.764000&acc=5.0"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn('alerts', data)
        self.assertIn('current_officer', data)
        self.assertIn('on_duty_officers', data)

        alert_entry = next((a for a in data['alerts'] if a['id'] == alert.id), None)
        self.assertIsNotNone(alert_entry)
        self.assertEqual(alert_entry['alert_type'], 'Active Threat / Crime')
        self.assertIn('my_distance_to_victim_m', alert_entry)
        self.assertIn('my_bearing_to_victim', alert_entry)

    def test_api_update_alert_status_workflow(self):
        """Full lifecycle update: SENT -> RECEIVED -> DISPATCHED -> RESOLVED."""
        alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_FIRE
        )
        Location.objects.create(
            alert=alert,
            latitude=Decimal("-28.742500"),
            longitude=Decimal("24.764800"),
            description="Student Cafeteria"
        )

        self.client.login(username="sec_officer1", password="Password123!")

        # 1. Acknowledge (RECEIVED)
        resp1 = self.client.post(
            reverse('api_update_alert_status', args=[alert.id]),
            data=json.dumps({'status': EmergencyAlert.STATUS_RECEIVED}),
            content_type='application/json'
        )
        self.assertEqual(resp1.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, EmergencyAlert.STATUS_RECEIVED)

        # 2. Dispatch (DISPATCHED)
        resp2 = self.client.post(
            reverse('api_update_alert_status', args=[alert.id]),
            data=json.dumps({
                'status': EmergencyAlert.STATUS_DISPATCHED,
                'officer_lat': -28.741500,
                'officer_lng': 24.764200,
                'officer_accuracy': 4.5
            }),
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, EmergencyAlert.STATUS_DISPATCHED)

        # 3. Resolve (RESOLVED)
        resp3 = self.client.post(
            reverse('api_update_alert_status', args=[alert.id]),
            data=json.dumps({
                'status': EmergencyAlert.STATUS_RESOLVED,
                'response_notes': 'Fire extinguisher deployed, situation contained.'
            }),
            content_type='application/json'
        )
        self.assertEqual(resp3.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, EmergencyAlert.STATUS_RESOLVED)
        self.assertIsNotNone(alert.resolved_at)

        # Verify AlertResponse entry was updated
        response_rec = AlertResponse.objects.filter(alert=alert, officer=self.officer).first()
        self.assertIsNotNone(response_rec)
        self.assertEqual(response_rec.status, AlertResponse.STATUS_RESOLVED)
        self.assertEqual(response_rec.response_notes, 'Fire extinguisher deployed, situation contained.')

        # Verify IncidentReport was automatically synchronized with officer resolution notes
        from incidents.models import IncidentReport
        incident = IncidentReport.objects.filter(description__startswith=f"CAD Emergency Incident #{alert.id} ").first()
        self.assertIsNotNone(incident)
        self.assertEqual(incident.status, IncidentReport.STATUS_CLOSED)
        self.assertIn('Fire extinguisher deployed, situation contained.', incident.admin_notes)

    def test_api_update_officer_location(self):
        """Officer updates hardware tablet telemetry coordinates."""
        self.client.login(username="sec_officer1", password="Password123!")

        payload = {
            'latitude': -28.740500,
            'longitude': 24.763200,
            'accuracy': 3.5
        }
        resp = self.client.post(
            reverse('api_update_officer_location'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        self.officer.refresh_from_db()
        self.assertEqual(float(self.officer.latitude), -28.740500)
        self.assertEqual(float(self.officer.longitude), 24.763200)

    def test_kimberley_map_tile_bounds(self):
        """Map tile endpoint handles valid and out-of-bounds requests safely."""
        # Out-of-bounds zoom level returns 404
        resp_invalid = self.client.get(reverse('kimberley_map_tile', kwargs={'z': 0, 'x': 1, 'y': 1}))
        self.assertEqual(resp_invalid.status_code, 404)

        # Valid zoom returns redirect to OSM or local tile
        resp_valid = self.client.get(reverse('kimberley_map_tile', kwargs={'z': 16, 'x': 37245, 'y': 36502}))
        self.assertIn(resp_valid.status_code, [200, 302])
