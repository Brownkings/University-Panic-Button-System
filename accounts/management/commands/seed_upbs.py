"""
Management command to initialize the UPBS database with essential institutional roles
and the master administrator account.
"""
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Role, User
from alerts.models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification
from incidents.models import IncidentReport
from feedback.models import Feedback, UsabilityMetric


class Command(BaseCommand):
    help = "Seeds database with essential UPBS institutional roles and ensures the master admin account exists."
    help = "Seeds database with essential UPBS institutional roles and ensures the master admin account exists. Use --demo to populate demo accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            '--demo',
            action='store_true',
            help='Populate student, security officer demo accounts, and evaluation usability metrics.'
        )

    def handle(self, *args, **options):
        self.stdout.write("Initializing UPBS institutional roles...")

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
        self.stdout.write(self.style.SUCCESS("✓ Institutional roles ready (STUDENT, STAFF, SECURITY, ADMIN)."))

        # 2. Ensure Master Admin Account Exists
        # NOTE: NEVER overwrites or resets an existing administrator password.
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                'full_name': "Brown Nkosi (Master Administrator)",
                'institutional_id': "ADMIN001",
                'email': "mnnhlnkosi@gmail.com",
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
            self.stdout.write(self.style.SUCCESS(f"✓ Created initial master admin account: {admin_user.username}"))
        else:
            updated = False
            if admin_user.email != "mnnhlnkosi@gmail.com":
                admin_user.email = "mnnhlnkosi@gmail.com"
                updated = True
            if admin_user.full_name != "Brown Nkosi (Master Administrator)":
                admin_user.full_name = "Brown Nkosi (Master Administrator)"
                updated = True
            if updated:
                admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Master admin account verified: {admin_user.username} ({admin_user.email}) - existing password preserved."))

        # 3. Optional Demo Seeding
        if options.get('demo'):
            self.stdout.write("Seeding demo accounts and evaluation metrics (--demo active)...")

            # Demo Security Officer
            sec_user, created = User.objects.get_or_create(
                username="officer1",
                defaults={
                    'full_name': "Rethabile Thuto Pheko",
                    'institutional_id': "SEC001",
                    'email': "202345683@student.spu.ac.za",
                    'contact_number': "+27821112222",
                    'role': roles[Role.SECURITY],
                    'is_staff': True,
                    'is_verified': True,
                }
            )
            if created:
                sec_user.set_password("password123")
                sec_user.save()

            officer, _ = SecurityOfficer.objects.get_or_create(
                badge_number="SEC-001",
                defaults={
                    'user': sec_user,
                    'officer_name': "Rethabile Thuto Pheko",
                    'on_duty': True,
                    'latitude': Decimal("-28.741800"),
                    'longitude': Decimal("24.764200"),
                }
            )

            # Demo Students
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

            # Panic Devices
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

            # Demo Emergency Alerts & Officer Field Resolution Reports
            if not EmergencyAlert.objects.exists():
                a1 = EmergencyAlert.objects.create(
                    user=student1,
                    panic_device=dev1,
                    status=EmergencyAlert.STATUS_RESOLVED,
                    alert_type=EmergencyAlert.TYPE_MEDICAL,
                    timestamp=timezone.now() - timedelta(minutes=42),
                    resolved_at=timezone.now() - timedelta(minutes=28),
                )
                Location.objects.create(
                    alert=a1,
                    latitude=Decimal("-28.742050"),
                    longitude=Decimal("24.765100"),
                    accuracy_meters=4.2,
                    description="Science Block Floor 2, Laboratory B",
                )
                AlertResponse.objects.create(
                    alert=a1,
                    officer=officer,
                    status=AlertResponse.STATUS_RESOLVED,
                    dispatched_at=timezone.now() - timedelta(minutes=41),
                    acknowledged_at=timezone.now() - timedelta(minutes=40),
                    resolved_at=timezone.now() - timedelta(minutes=28),
                    response_notes="Patrol unit on scene. First aid administered for chemical splash burn; student escorted to campus health clinic. Lab ventilated.",
                )

                a2 = EmergencyAlert.objects.create(
                    user=student2,
                    panic_device=dev2,
                    status=EmergencyAlert.STATUS_RESOLVED,
                    alert_type=EmergencyAlert.TYPE_CRIME,
                    timestamp=timezone.now() - timedelta(hours=2, minutes=15),
                    resolved_at=timezone.now() - timedelta(hours=1, minutes=50),
                )
                Location.objects.create(
                    alert=a2,
                    latitude=Decimal("-28.743100"),
                    longitude=Decimal("24.766200"),
                    accuracy_meters=3.8,
                    description="East Residence Turnstile Gate",
                )
                AlertResponse.objects.create(
                    alert=a2,
                    officer=officer,
                    status=AlertResponse.STATUS_RESOLVED,
                    dispatched_at=timezone.now() - timedelta(hours=2, minutes=14),
                    acknowledged_at=timezone.now() - timedelta(hours=2, minutes=13),
                    resolved_at=timezone.now() - timedelta(hours=1, minutes=50),
                    response_notes="Perimeter swept and secured by tactical patrol unit. Unauthorized trespasser escorted off campus grounds via North Gate.",
                )
                self.stdout.write(self.style.SUCCESS("✓ Demo emergency CAD alerts & officer responses populated."))

            # Demo Incident Reports with Officer Resolution Reports
            if not IncidentReport.objects.exists():
                IncidentReport.objects.create(
                    user=student1,
                    category=IncidentReport.CATEGORY_MEDICAL,
                    location_name="Science Block Floor 2, Laboratory B",
                    description="CAD Emergency Incident #1 [Medical Emergency / Injury]. Triggered by student Brown Nkosi (202474004). Attended and resolved by Officer Rethabile Thuto Pheko (SEC-001).",
                    status=IncidentReport.STATUS_CLOSED,
                    admin_notes="Officer Resolution Report by Officer Rethabile Thuto Pheko (SEC-001):\nPatrol unit on scene. First aid administered for chemical splash burn; student escorted to campus health clinic. Lab ventilated.",
                )
                IncidentReport.objects.create(
                    user=student2,
                    category=IncidentReport.CATEGORY_SUSPICIOUS,
                    location_name="East Residence Turnstile Gate",
                    description="CAD Emergency Incident #2 [Active Threat / Crime]. Triggered by student Palesa Hope Ntsane (202437528). Attended and resolved by Officer Rethabile Thuto Pheko (SEC-001).",
                    status=IncidentReport.STATUS_CLOSED,
                    admin_notes="Officer Resolution Report by Officer Rethabile Thuto Pheko (SEC-001):\nPerimeter swept and secured by tactical patrol unit. Unauthorized trespasser escorted off campus grounds via North Gate.",
                )
                IncidentReport.objects.create(
                    user=student1,
                    category=IncidentReport.CATEGORY_THEFT,
                    location_name="Central Library Quiet Study Area Floor 1",
                    description="Student laptop bag and textbooks taken from study desk while attending 10:00 lecture.",
                    status=IncidentReport.STATUS_ACTION,
                    admin_notes="Officer Rethabile Pheko reviewed security CCTV footage with IT Services. Identified item misplaced at library help desk and returned to student.",
                )
                self.stdout.write(self.style.SUCCESS("✓ Demo incident reports with officer resolution notes populated."))

            # Usability Testing Metrics (NPRT630 Phase 4 Rubric Compliance)
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

            self.stdout.write(self.style.SUCCESS(
                "✓ Demo accounts ready:\n"
                "   - Student 1: student1 (202474004) / password123\n"
                "   - Student 2: student2 (202437528) / password123\n"
                "   - Officer:   officer1 (SEC001) / password123\n"
                "   - Admin:     admin / password123"
            ))

        self.stdout.write(self.style.SUCCESS("✓ UPBS database initialization complete."))
