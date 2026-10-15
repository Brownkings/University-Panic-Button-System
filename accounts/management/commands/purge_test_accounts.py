"""
Management command to purge all test and demo accounts from the UPBS database,
leaving exclusively the master administrator account intact with their set password.
"""
from django.core.management.base import BaseCommand
from accounts.models import User, Role
from alerts.models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification
from incidents.models import IncidentReport
from feedback.models import Feedback, UsabilityMetric


class Command(BaseCommand):
    help = "Purges all demo/test accounts (student1, student2, officer1, etc.), leaving only the master administrator intact."

    def handle(self, *args, **options):
        self.stdout.write("Starting test account purge...")

        # Identify all non-admin test users
        # Exclude superusers, admin role users, and master admin email/username
        test_users = User.objects.exclude(
            username__iexact='admin'
        ).exclude(
            email__iexact='mnnhlnkosi@gmail.com'
        ).exclude(
            is_superuser=True
        ).filter(
            role__role_name__in=[Role.STUDENT, Role.SECURITY, Role.STAFF]
        )

        count = test_users.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("✓ No test accounts found. Database is already clean."))
        else:
            names = list(test_users.values_list('username', flat=True))
            self.stdout.write(f"Found {count} test account(s) to remove: {', '.join(names)}")
            
            # Cascade deletes handle alerts, feedback, panic devices, and security officers
            deleted_counts = test_users.delete()
            self.stdout.write(self.style.SUCCESS(f"✓ Successfully deleted {count} test account(s) and associated test data."))

        # Verify master admin remains intact
        admin = User.objects.filter(username='admin').first()
        if not admin:
            admin = User.objects.filter(email__iexact='mnnhlnkosi@gmail.com').first()

        if admin:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Master Administrator account preserved: {admin.username} ({admin.email}) [ID: {admin.institutional_id}]"
            ))
            self.stdout.write(self.style.SUCCESS("✓ Admin password was not modified."))
        else:
            self.stdout.write(self.style.WARNING("⚠ Warning: No master admin account was found."))
