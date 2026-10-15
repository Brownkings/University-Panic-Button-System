"""
Management command to initialize the UPBS database with essential institutional roles
and the master administrator account.
"""
from django.core.management.base import BaseCommand
from accounts.models import Role, User


class Command(BaseCommand):
    help = "Seeds database with essential UPBS institutional roles and ensures the master admin account exists."

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

        self.stdout.write(self.style.SUCCESS("✓ UPBS database initialization complete."))
