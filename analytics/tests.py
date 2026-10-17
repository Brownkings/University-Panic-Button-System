import csv
import io
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import Role, User
from alerts.models import EmergencyAlert, Location
from feedback.models import Feedback


class AnalyticsAndReportsTests(TestCase):
    """
    Validates the Analytics and Safety Reports system (analytics app):
    - RBAC authorization for analytics console
    - Mobile client redirection to student portal
    - Filter criteria (category, status, date range)
    - KPI calculations (resolution rate, average rating)
    - CSV export generator
    """

    def setUp(self):
        self.client = Client()

        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student")
        self.role_security = Role.objects.create(role_name=Role.SECURITY, description="Security")
        self.role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin")

        self.student = User.objects.create_user(
            username="student_analytics",
            full_name="Brown Nkosi",
            institutional_id="202474004",
            email="student@campus.ac.za",
            contact_number="+27712345678",
            role=self.role_student,
            password="Password123!",
            is_verified=True
        )

        self.admin = User.objects.create_user(
            username="admin_analytics",
            full_name="Campus Safety Admin",
            institutional_id="ADM001",
            email="admin@campus.ac.za",
            contact_number="+27820000000",
            role=self.role_admin,
            password="Password123!",
            is_staff=True,
            is_superuser=True,
            is_verified=True
        )

        # Seed alerts
        self.alert_med = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_RESOLVED,
            alert_type=EmergencyAlert.TYPE_MEDICAL
        )
        Location.objects.create(
            alert=self.alert_med,
            latitude=Decimal("-28.742050"),
            longitude=Decimal("24.765100"),
            description="Library Study Hall"
        )

        self.alert_fire = EmergencyAlert.objects.create(
            user=self.student,
            status=EmergencyAlert.STATUS_SENT,
            alert_type=EmergencyAlert.TYPE_FIRE
        )
        Location.objects.create(
            alert=self.alert_fire,
            latitude=Decimal("-28.741500"),
            longitude=Decimal("24.766000"),
            description="Cafeteria Kitchen"
        )

        # Seed feedback
        Feedback.objects.create(
            user=self.student,
            alert=self.alert_med,
            rating=5,
            comments="Paramedic dispatched within 2 minutes."
        )

    def test_reports_access_control(self):
        """Student denied (403), Admin allowed (200), Mobile UA redirected (302)."""
        # Student access denied
        self.client.login(username="student_analytics", password="Password123!")
        resp_student = self.client.get(reverse('reports_analytics'))
        self.assertEqual(resp_student.status_code, 403)

        # Admin access granted
        self.client.login(username="admin_analytics", password="Password123!")
        resp_admin = self.client.get(reverse('reports_analytics'))
        self.assertEqual(resp_admin.status_code, 200)

        # Mobile client redirected
        resp_mobile = self.client.get(reverse('reports_analytics'), HTTP_USER_AGENT='Mozilla/5.0 UPBSStudentPortal/2.0')
        self.assertEqual(resp_mobile.status_code, 302)
        self.assertRedirects(resp_mobile, reverse('home'))

    def test_reports_filter_by_category_and_status(self):
        """Tests filtering safety reports by emergency category and status."""
        self.client.login(username="admin_analytics", password="Password123!")

        # Filter by MEDICAL
        resp_med = self.client.get(reverse('reports_analytics') + '?category=MEDICAL')
        self.assertEqual(resp_med.status_code, 200)
        alerts_list = list(resp_med.context['alerts'])
        self.assertIn(self.alert_med, alerts_list)
        self.assertNotIn(self.alert_fire, alerts_list)

        # Filter by status RESOLVED
        resp_res = self.client.get(reverse('reports_analytics') + '?status=RESOLVED')
        self.assertEqual(resp_res.status_code, 200)
        alerts_res = list(resp_res.context['alerts'])
        self.assertIn(self.alert_med, alerts_res)
        self.assertNotIn(self.alert_fire, alerts_res)

    def test_kpi_aggregate_metrics(self):
        """Tests calculation of resolution rate and feedback metrics."""
        self.client.login(username="admin_analytics", password="Password123!")
        response = self.client.get(reverse('reports_analytics'))
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['total_alerts'], 2)
        self.assertEqual(response.context['resolved_count'], 1)
        self.assertEqual(response.context['resolution_rate'], 50.0) # 1 of 2 resolved
        self.assertEqual(response.context['total_feedbacks'], 1)
        self.assertEqual(response.context['avg_rating'], 5.0)

    def test_export_reports_csv_access_control_and_content(self):
        """Tests CSV export endpoint access control, CSV MIME type, and tabular content."""
        # Student forbidden
        self.client.login(username="student_analytics", password="Password123!")
        resp_forbidden = self.client.get(reverse('export_reports_csv'))
        self.assertEqual(resp_forbidden.status_code, 403)

        # Admin authorized
        self.client.login(username="admin_analytics", password="Password123!")
        response = self.client.get(reverse('export_reports_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="upbs_safety_report_', response['Content-Disposition'])

        csv_content = response.content.decode('utf-8')
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        # Header row
        header = rows[0]
        self.assertIn('Alert ID', header)
        self.assertIn('Emergency Type', header)
        self.assertIn('Status', header)

        # Data rows (2 alerts seeded)
        self.assertEqual(len(rows), 3) # 1 header + 2 data rows
