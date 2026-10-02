from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from accounts.models import Role, User
from alerts.models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification
from incidents.models import IncidentReport
from feedback.models import Feedback, UsabilityMetric


class Command(BaseCommand):
    help = "Seeds database with essential UPBS roles, demo users (Student, Security, Admin), past alerts, and usability metrics"

    def handle(self, *args, **options):
        self.stdout.write("Starting UPBS database seeding...")

        # 1. Create Roles
        roles_data = [
            (Role.STUDENT, "University Student with access to panic triggers and reports"),
            (Role.STAFF, "University Academic / Administrative Staff"),
            (Role.SECURITY, "Campus Security Personnel / Dispatch Operator"),
            (Role.ADMIN, "System Administrator with reporting and user management"),
        ]
        roles = {}
        for role_name, desc in roles_data:
            role, _ = Role.objects.get_or_create(role_name=role_name, defaults={'description': desc})
            roles[role_name] = role
        self.stdout.write(self.style.SUCCESS("✓ Roles created."))

        # 2. Create Admin
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                'full_name': "Administrator System",
                'institutional_id': "ADMIN001",
                'email': "admin@campus.ac.za",
                'contact_number': "+27820000001",
                'role': roles[Role.ADMIN],
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
            }
        )
        if created:
            admin_user.set_password("password123")
            admin_user.save()
        self.stdout.write(self.style.SUCCESS(f"✓ Admin account ready: {admin_user.username} (password123)"))

        # 3. Create Security Officer
        sec_user, created = User.objects.get_or_create(
            username="officer1",
            defaults={
                'full_name': "Sergeant Thabo Dlamini",
                'institutional_id': "SEC001",
                'email': "security1@campus.ac.za",
                'contact_number': "+27829991111",
                'role': roles[Role.SECURITY],
                'is_staff': True,
                'is_verified': True,
            }
        )
        if created:
            sec_user.set_password("password123")
            sec_user.save()

        officer, _ = SecurityOfficer.objects.get_or_create(
            user=sec_user,
            defaults={
                'officer_name': "Sergeant Thabo Dlamini",
                'badge_number': "SPU-SEC-402",
                'on_duty': True,
                'current_post': "Central Security Command Post"
            }
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Security Officer ready: {sec_user.username} (password123)"))

        # 4. Create Students (Group Members context: Brown Nkosi & Palesa Ntsane)
        student1, created = User.objects.get_or_create(
            username="student1",
            defaults={
                'full_name': "Brown Nkosi",
                'institutional_id': "202474004",
                'email': "202474004@student.spu.ac.za",
                'contact_number': "+27712345678",
                'role': roles[Role.STUDENT],
                'is_verified': True,
            }
        )
        if created:
            student1.set_password("password123")
            student1.save()

        student2, created = User.objects.get_or_create(
            username="student2",
            defaults={
                'full_name': "Palesa Hope Ntsane",
                'institutional_id': "202437528",
                'email': "202437528@student.spu.ac.za",
                'contact_number': "+27798765432",
                'role': roles[Role.STUDENT],
                'is_verified': True,
            }
        )
        if created:
            student2.set_password("password123")
            student2.save()
        self.stdout.write(self.style.SUCCESS(f"✓ Students ready: {student1.username}, {student2.username} (password123)"))

        # 5. Panic Devices
        dev1, _ = PanicDevice.objects.get_or_create(
            device_identifier="DEV-WEB-202474004",
            user=student1,
            defaults={'device_type': 'WEB_CLIENT', 'is_active': True}
        )
        dev2, _ = PanicDevice.objects.get_or_create(
            device_identifier="DEV-MOB-202437528",
            user=student2,
            defaults={'device_type': 'MOBILE_PWA', 'is_active': True}
        )

        # 6. Sample Alerts & Locations
        # Alert A: Resolved Alert from 2 days ago
        if not EmergencyAlert.objects.filter(user=student1).exists():
            time_past = timezone.now() - timedelta(days=2, hours=3)
            alert1 = EmergencyAlert.objects.create(
                user=student1,
                panic_device=dev1,
                timestamp=time_past,
                status=EmergencyAlert.STATUS_RESOLVED,
                alert_type=EmergencyAlert.TYPE_STANDARD,
                resolved_at=time_past + timedelta(minutes=14)
            )
            Location.objects.create(
                alert=alert1,
                latitude=Decimal("-28.742050"),
                longitude=Decimal("24.765100"),
                accuracy_meters=5.0,
                description="Central Campus Library, 2nd Floor Study Area"
            )
            AlertResponse.objects.create(
                alert=alert1,
                officer=officer,
                dispatched_at=time_past + timedelta(minutes=1),
                acknowledged_at=time_past + timedelta(minutes=2),
                resolved_at=time_past + timedelta(minutes=14),
                response_notes="Officer dispatched on foot. Student was escort safely to campus shuttle.",
                status=AlertResponse.STATUS_RESOLVED
            )
            Notification.objects.create(
                alert=alert1,
                recipient=sec_user.contact_number,
                channel=Notification.CHANNEL_SMS,
                message="EMERGENCY ALERT: Student Brown Nkosi triggered panic at Library 2nd Floor.",
                delivery_status=Notification.STATUS_DELIVERED
            )
            Feedback.objects.create(
                user=student1,
                alert=alert1,
                rating=5,
                comments="Security responded in less than 3 minutes. The live tracking timeline kept me calm!"
            )

            # Alert B: Dispatched Alert from 30 minutes ago
            time_recent = timezone.now() - timedelta(minutes=30)
            alert2 = EmergencyAlert.objects.create(
                user=student2,
                panic_device=dev2,
                timestamp=time_recent,
                status=EmergencyAlert.STATUS_DISPATCHED,
                alert_type=EmergencyAlert.TYPE_MEDICAL,
            )
            Location.objects.create(
                alert=alert2,
                latitude=Decimal("-28.743120"),
                longitude=Decimal("24.763850"),
                accuracy_meters=4.2,
                description="East Residence Block C, Ground Floor Foyer"
            )
            AlertResponse.objects.create(
                alert=alert2,
                officer=officer,
                dispatched_at=time_recent + timedelta(minutes=1),
                acknowledged_at=time_recent + timedelta(minutes=2),
                response_notes="First aid kit dispatched with medical response unit. En route.",
                status=AlertResponse.STATUS_EN_ROUTE
            )
            Notification.objects.create(
                alert=alert2,
                recipient=sec_user.contact_number,
                channel=Notification.CHANNEL_SMS,
                message="MEDICAL EMERGENCY: Palesa Ntsane at East Res Block C.",
                delivery_status=Notification.STATUS_DELIVERED
            )

        self.stdout.write(self.style.SUCCESS("✓ Sample Emergency Alerts and Locations populated."))

        # 7. Sample Incident Reports
        if not IncidentReport.objects.exists():
            IncidentReport.objects.create(
                user=student1,
                category=IncidentReport.CATEGORY_THEFT,
                location_name="Computer Science Lab 3",
                description="Laptop charger and notebook taken from table while attending consultation.",
                status=IncidentReport.STATUS_REVIEW,
                admin_notes="Reviewing CCTV footage between 14:00 and 15:00."
            )
            IncidentReport.objects.create(
                user=student2,
                category=IncidentReport.CATEGORY_HAZARD,
                location_name="Walkway between Science Building and Cafeteria",
                description="Streetlight pole has exposed wiring after recent rainstorm.",
                status=IncidentReport.STATUS_ACTION,
                admin_notes="Maintenance team dispatched to secure electrical junction box."
            )
        self.stdout.write(self.style.SUCCESS("✓ Sample Incident Reports populated."))

        # 8. Usability Testing Metrics (NPRT630 Phase 4 Rubric Compliance)
        if not UsabilityMetric.objects.exists():
            test_metrics = [
                ("Trigger Emergency Alert (Panic Button)", student1, 1.84, True, 0, 92.5),
                ("3-Second Abort / Cancel False Alarm", student1, 2.15, True, 0, 87.5),
                ("Security Officer Acknowledge & Dispatch", sec_user, 3.40, True, 0, 85.0),
                ("Submit Incident Report with Media", student2, 14.20, True, 0, 90.0),
                ("Resolve Alert & Post Field Notes", sec_user, 6.80, True, 0, 88.0),
            ]
            for task, u, comp_time, succ, errs, sus in test_metrics:
                UsabilityMetric.objects.create(
                    user=u,
                    task_name=task,
                    completion_time_seconds=comp_time,
                    is_successful=succ,
                    error_count=errs,
                    sus_score=sus
                )
        self.stdout.write(self.style.SUCCESS("✓ Usability testing metrics populated."))
        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] UPBS database successfully initialized!"))
        self.stdout.write(self.style.WARNING("Log in with: student1 / password123, officer1 / password123, or admin / password123"))
