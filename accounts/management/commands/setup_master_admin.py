"""
Management command to configure the Master Administrator account (mnnhlnkosi@gmail.com)
and dispatch their initial account setup & password configuration email via Resend.
"""
from django.core.management.base import BaseCommand
from accounts.models import User, Role
from accounts.email_service import send_account_setup_email


class Command(BaseCommand):
    help = "Configures master administrator account and dispatches initial password setup email via Resend."

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='mnnhlnkosi@gmail.com',
            help='Master admin email address (default: mnnhlnkosi@gmail.com)'
        )
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for master admin (default: admin)'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Brown Nkosi (Master Administrator)',
            help='Full name for master admin'
        )
        parser.add_argument(
            '--id',
            type=str,
            default='ADMIN001',
            help='Institutional ID for master admin (default: ADMIN001)'
        )
        parser.add_argument(
            '--base-url',
            type=str,
            default='https://youthalliance.co.za',
            help='Base URL for password setup link (default: https://youthalliance.co.za)'
        )

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        username = options['username'].strip()
        full_name = options['name'].strip()
        institutional_id = options['id'].strip()
        base_url = options['base_url'].strip()

        admin_role, _ = Role.objects.get_or_create(
            role_name=Role.ADMIN,
            defaults={'description': 'System Administrator with reporting and user management'}
        )

        # Check if master admin exists by email or username
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.filter(username=username).first()

        if user:
            user.email = email
            user.full_name = full_name
            user.institutional_id = institutional_id
            user.role = admin_role
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Updated existing admin account: {user.username} ({user.email})"))
        else:
            user = User.objects.create(
                username=username,
                email=email,
                full_name=full_name,
                institutional_id=institutional_id,
                role=admin_role,
                is_staff=True,
                is_superuser=True,
                is_active=True,
                is_verified=False
            )
            user.set_password(User.objects.make_random_password(length=24))
            user.save()
            self.stdout.write(self.style.SUCCESS(f"✓ Created new master admin account: {user.username} ({user.email})"))

        # Dispatch account setup email via Resend
        sent = send_account_setup_email(user, base_url=base_url)
        if sent:
            self.stdout.write(self.style.SUCCESS(
                f"✓ Initial account setup and password configuration email successfully dispatched via Resend to {user.email}!"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"⚠ Resend dispatch returned False. Check RESEND_API_KEY."
            ))
