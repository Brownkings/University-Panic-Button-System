from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import Role, User
from incidents.models import IncidentReport


class IncidentReportingTests(TestCase):
    """
    Validates the Incident Reporting system (incidents app):
    - Incident persistence & data integrity
    - File upload size limit (10MB enforcement)
    - Form validation & error handling
    - Student view isolation (private case view)
    - Authorization boundaries for incident details (RBAC)
    - String representation and model metadata
    """

    def setUp(self):
        self.client = Client()

        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student")
        self.role_security = Role.objects.create(role_name=Role.SECURITY, description="Security")
        self.role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin")

        self.student1 = User.objects.create_user(
            username="student_alice",
            full_name="Alice Smith",
            institutional_id="202474001",
            email="alice@student.ac.za",
            contact_number="+27711112222",
            role=self.role_student,
            password="Password123!",
            is_verified=True
        )

        self.student2 = User.objects.create_user(
            username="student_bob",
            full_name="Bob Jones",
            institutional_id="202474002",
            email="bob@student.ac.za",
            contact_number="+27722223333",
            role=self.role_student,
            password="Password123!",
            is_verified=True
        )

        self.sec_officer = User.objects.create_user(
            username="officer_charlie",
            full_name="Officer Charlie",
            institutional_id="SEC201",
            email="charlie@security.ac.za",
            contact_number="+27823334444",
            role=self.role_security,
            password="Password123!",
            is_staff=True,
            is_verified=True
        )

        self.admin_user = User.objects.create_user(
            username="admin_dan",
            full_name="Dan Administrator",
            institutional_id="ADM101",
            email="dan@admin.ac.za",
            contact_number="+27824445555",
            role=self.role_admin,
            password="Password123!",
            is_staff=True,
            is_superuser=True,
            is_verified=True
        )

    def test_incident_persistence_success(self):
        """Verifies successful incident persistence without file upload."""
        self.client.login(username="student_alice", password="Password123!")
        post_data = {
            'category': IncidentReport.CATEGORY_THEFT,
            'location_name': 'Science Block Floor 2 Lab B',
            'description': 'Laptop missing from student workstation between 14:00 and 15:00.'
        }
        response = self.client.post(reverse('incident_create'), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('incident_create'))

        report = IncidentReport.objects.filter(location_name='Science Block Floor 2 Lab B').first()
        self.assertIsNotNone(report)
        self.assertEqual(report.user, self.student1)
        self.assertEqual(report.category, IncidentReport.CATEGORY_THEFT)
        self.assertEqual(report.status, IncidentReport.STATUS_SUBMITTED)
        self.assertEqual(report.description, 'Laptop missing from student workstation between 14:00 and 15:00.')
        self.assertFalse(bool(report.media_file))

    def test_incident_persistence_with_media_upload(self):
        """Verifies successful incident persistence with valid media file under 10MB."""
        self.client.login(username="student_alice", password="Password123!")
        test_file = SimpleUploadedFile("evidence_photo.jpg", b"JPEG_BINARY_DATA", content_type="image/jpeg")
        post_data = {
            'category': IncidentReport.CATEGORY_VANDALISM,
            'location_name': 'East Residence Entrance Gate',
            'description': 'Graffiti and broken lock on pedestrian turnstile.',
            'media_file': test_file
        }
        response = self.client.post(reverse('incident_create'), data=post_data)
        self.assertEqual(response.status_code, 302)

        report = IncidentReport.objects.filter(location_name='East Residence Entrance Gate').first()
        self.assertIsNotNone(report)
        self.assertTrue(bool(report.media_file))
        self.assertIn("evidence_photo", report.media_file.name)

    def test_incident_file_upload_size_limit_10mb_rejected(self):
        """Verifies that uploaded files exceeding 10 MB are strictly rejected with user error."""
        self.client.login(username="student_alice", password="Password123!")
        oversized_content = b"x" * (10 * 1024 * 1024 + 1024) # 10MB + 1KB
        oversized_file = SimpleUploadedFile("huge_recording.mp4", oversized_content, content_type="video/mp4")
        post_data = {
            'category': IncidentReport.CATEGORY_HAZARD,
            'location_name': 'Central Cafeteria Kitchen',
            'description': 'Water leak near electrical panel.',
            'media_file': oversized_file
        }
        response = self.client.post(reverse('incident_create'), data=post_data)
        self.assertEqual(response.status_code, 200) # Re-renders form on validation failure
        self.assertContains(response, "Uploaded file exceeds the maximum limit of 10 MB.")
        self.assertFalse(IncidentReport.objects.filter(location_name='Central Cafeteria Kitchen').exists())

    def test_incident_missing_required_fields_rejected(self):
        """Verifies that missing location or description fields are rejected."""
        self.client.login(username="student_alice", password="Password123!")
        post_data = {
            'category': IncidentReport.CATEGORY_OTHER,
            'location_name': '', # Missing
            'description': 'Something happened.'
        }
        response = self.client.post(reverse('incident_create'), data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please fill in all required fields")
        self.assertEqual(IncidentReport.objects.count(), 0)

    def test_student_view_isolation(self):
        """Verifies that students only see their own submitted reports, not those of other students."""
        report_alice = IncidentReport.objects.create(
            user=self.student1,
            category=IncidentReport.CATEGORY_THEFT,
            location_name="Library Quiet Study Room 4",
            description="Alice's private report"
        )
        report_bob = IncidentReport.objects.create(
            user=self.student2,
            category=IncidentReport.CATEGORY_HARASSMENT,
            location_name="Sports Pavilion Walkway",
            description="Bob's private report"
        )

        # Alice logs in: should see her report, but NOT Bob's report
        self.client.login(username="student_alice", password="Password123!")
        response = self.client.get(reverse('incident_create'))
        self.assertEqual(response.status_code, 200)
        user_reports = list(response.context['user_reports'])
        self.assertIn(report_alice, user_reports)
        self.assertNotIn(report_bob, user_reports)

    def test_student_detail_view_isolation(self):
        """Verifies student cannot access another student's incident report detail directly."""
        report_bob = IncidentReport.objects.create(
            user=self.student2,
            category=IncidentReport.CATEGORY_HARASSMENT,
            location_name="Sports Pavilion Walkway",
            description="Bob's confidential report"
        )

        # Alice attempts to access Bob's report detail
        self.client.login(username="student_alice", password="Password123!")
        response = self.client.get(reverse('incident_detail', args=[report_bob.id]))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('incident_create'))

        # Bob accesses his own report detail
        self.client.login(username="student_bob", password="Password123!")
        response_bob = self.client.get(reverse('incident_detail', args=[report_bob.id]))
        self.assertEqual(response_bob.status_code, 200)
        self.assertEqual(response_bob.context['report'], report_bob)

    def test_security_and_admin_detail_view_access(self):
        """Security personnel and administrators can view any incident report detail."""
        report_alice = IncidentReport.objects.create(
            user=self.student1,
            category=IncidentReport.CATEGORY_THEFT,
            location_name="Library Quiet Study Room 4",
            description="Theft report"
        )

        # Security officer access
        self.client.login(username="officer_charlie", password="Password123!")
        resp_sec = self.client.get(reverse('incident_detail', args=[report_alice.id]))
        self.assertEqual(resp_sec.status_code, 200)

        # Admin access
        self.client.login(username="admin_dan", password="Password123!")
        resp_adm = self.client.get(reverse('incident_detail', args=[report_alice.id]))
        self.assertEqual(resp_adm.status_code, 200)

    def test_incident_string_representation(self):
        """Verifies human-readable string representation of IncidentReport."""
        report = IncidentReport.objects.create(
            user=self.student1,
            category=IncidentReport.CATEGORY_THEFT,
            location_name="Admin Lobby",
            description="Wallet lost or stolen"
        )
        self.assertEqual(
            str(report),
            f"Incident #{report.id} [Theft / Burglary] - Alice Smith"
        )
