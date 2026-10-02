from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from accounts.models import Role, User
from alerts.models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification
from incidents.models import IncidentReport
from feedback.models import Feedback, UsabilityMetric


class UPBSModelTests(TestCase):
    """
    Validates all Phase 3 ERD entities and relational integrity constraints.
    """

    def setUp(self):
        # Setup roles
        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student Role")
        self.role_security = Role.objects.create(role_name=Role.SECURITY, description="Security Role")
        self.role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin Role")

        # Setup users
        self.student = User.objects.create_user(
            username="test_student",
            full_name="Brown Nkosi",
            institutional_id="202474004",
            email="202474004@student.ac.za",
            contact_number="+27712345678",
            role=self.role_student,
            password="testpassword123"
        )

        self.sec_user = User.objects.create_user(
            username="test_officer",
            full_name="Officer Thabo",
            institutional_id="SEC901",
            email="thabo@security.ac.za",
            contact_number="+27821112222",
            role=self.role_security,
            password="testpassword123"
        )

        self.officer = SecurityOfficer.objects.create(
            user=self.sec_user,
            officer_name="Officer Thabo",
            badge_number="BADGE-007",
            on_duty=True
        )

    def test_user_and_role_properties(self):
        """Test Role-Based Access Control properties."""
        self.assertTrue(self.student.is_student)
        self.assertFalse(self.student.is_security)
        self.assertFalse(self.student.is_admin_user)

        self.assertTrue(self.sec_user.is_security)
        self.assertFalse(self.sec_user.is_student)

    def test_emergency_alert_and_location_one_to_one(self):
        """Test 1:1 EmergencyAlert -> Location relationship as specified in Phase 3 ERD."""
        alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_STANDARD
        )

        location = Location.objects.create(
            alert=alert,
            latitude=Decimal("-28.742050"),
            longitude=Decimal("24.765100"),
            accuracy_meters=5.0,
            description="Main Campus Library Floor 2"
        )

        self.assertEqual(alert.location, location)
        self.assertEqual(location.alert, alert)
        self.assertEqual(str(location.latitude), "-28.742050")

    def test_alert_response_many_to_many(self):
        """Test M:N EmergencyAlert <-> SecurityOfficer handled via AlertResponse table."""
        alert = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_MEDICAL
        )

        response = AlertResponse.objects.create(
            alert=alert,
            officer=self.officer,
            status=AlertResponse.STATUS_ASSIGNED,
            response_notes="Dispatched first aid unit"
        )

        self.assertIn(response, alert.responses.all())
        self.assertIn(response, self.officer.assigned_alerts.all())

    def test_incident_report_creation(self):
        """Test IncidentReport entity attributes and choices."""
        report = IncidentReport.objects.create(
            user=self.student,
            category=IncidentReport.CATEGORY_THEFT,
            location_name="Computer Science Lab",
            description="Bag taken from desk."
        )
        self.assertEqual(report.status, IncidentReport.STATUS_SUBMITTED)
        self.assertEqual(report.user, self.student)

    def test_feedback_and_usability_metrics(self):
        """Test user feedback submission and usability metric logging."""
        feedback = Feedback.objects.create(
            user=self.student,
            rating=5,
            comments="Rapid response, security arrived in 2 minutes!"
        )
        self.assertEqual(feedback.rating, 5)

        metric = UsabilityMetric.objects.create(
            user=self.student,
            task_name="Trigger Emergency Alert",
            completion_time_seconds=1.75,
            is_successful=True,
            error_count=0,
            sus_score=92.0
        )
        self.assertEqual(metric.completion_time_seconds, 1.75)
        self.assertTrue(metric.is_successful)
