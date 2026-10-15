from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from accounts.models import User, Role
from accounts.email_backend import ResendEmailBackend
from accounts.email_service import send_account_verification_email, send_password_reset_email, send_account_setup_email


class ResendEmailBackendTests(TestCase):
    """Unit tests for custom Resend transactional email backend."""

    @patch('accounts.email_backend.requests.post')
    def test_send_messages_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_test_msg_123"}
        mock_post.return_value = mock_resp

        backend = ResendEmailBackend(api_key="re_test_key_abc")
        email = EmailMultiAlternatives(
            subject="Test Safety Alert",
            body="Emergency Test Alert Plaintext",
            from_email="UPBS Campus Safety <onboarding@resend.dev>",
            to=["student@campus.ac.za"]
        )
        email.attach_alternative("<strong>Emergency Test HTML</strong>", "text/html")

        sent = backend.send_messages([email])
        self.assertEqual(sent, 1)
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.resend.com/emails")
        self.assertEqual(kwargs['headers']['Authorization'], "Bearer re_test_key_abc")
        self.assertEqual(kwargs['json']['to'], ["student@campus.ac.za"])
        self.assertEqual(kwargs['json']['subject'], "Test Safety Alert")
        self.assertEqual(kwargs['json']['html'], "<strong>Emergency Test HTML</strong>")

    def test_missing_api_key_graceful_handling(self):
        backend = ResendEmailBackend(api_key="")
        email = EmailMultiAlternatives(
            subject="Test Subject",
            body="Test Body",
            from_email="onboarding@resend.dev",
            to=["user@example.com"]
        )
        # Should return 0 without raising exception
        sent = backend.send_messages([email])
        self.assertEqual(sent, 0)


class AccountsEmailFlowTests(TestCase):
    """End-to-end tests for account verification and password reset flows."""

    def setUp(self):
        self.client = Client()
        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student Role")
        self.user = User.objects.create_user(
            username="student1",
            full_name="Brown Nkosi",
            institutional_id="202474004",
            email="student@campus.ac.za",
            contact_number="+27710001111",
            role=self.role_student,
            password="oldpassword123",
            is_verified=False,
            otp_code="654321"
        )

    @patch('accounts.views.send_account_verification_email')
    def test_registration_triggers_verification_email(self, mock_send_email):
        mock_send_email.return_value = True
        response = self.client.post(reverse('register'), {
            'full_name': 'Thabo Mbeki',
            'institutional_id': '202499999',
            'email': 'thabo@campus.ac.za',
            'contact_number': '+27821234567',
            'role': 'STUDENT',
            'password': 'StrongPassword123',
            'password_confirm': 'StrongPassword123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('verify_otp'))

        # Verify user was created with OTP and email dispatch called
        created_user = User.objects.get(institutional_id='202499999')
        self.assertFalse(created_user.is_verified)
        self.assertTrue(len(created_user.otp_code) == 6)
        mock_send_email.assert_called_once()

    @patch('accounts.views.send_account_verification_email')
    def test_resend_otp_triggers_email(self, mock_send_email):
        mock_send_email.return_value = True
        self.client.login(username='student1', password='oldpassword123')
        old_otp = self.user.otp_code
        response = self.client.get(reverse('resend_otp'))
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertNotEqual(self.user.otp_code, old_otp)
        mock_send_email.assert_called_once()

    def test_verify_email_link_view_valid_token(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.get(reverse('verify_email_link', kwargs={'uidb64': uidb64, 'token': token}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('role_redirect'), target_status_code=302)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.assertIsNone(self.user.otp_code)

    def test_verify_email_link_view_invalid_token(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse('verify_email_link', kwargs={'uidb64': uidb64, 'token': 'invalid-token-xyz'}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    @patch('accounts.views.send_password_reset_email')
    def test_password_reset_by_institutional_id(self, mock_send_email):
        mock_send_email.return_value = True
        response = self.client.post(reverse('password_reset'), {
            'identifier': '202474004'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('password_reset_done'))
        mock_send_email.assert_called_once_with(self.user, request=mock_send_email.call_args[1]['request'])

    @patch('accounts.views.send_password_reset_email')
    def test_password_reset_by_email(self, mock_send_email):
        mock_send_email.return_value = True
        response = self.client.post(reverse('password_reset'), {
            'identifier': 'student@campus.ac.za'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('password_reset_done'))
        mock_send_email.assert_called_once()

    def test_password_reset_confirm_and_complete(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # GET confirm page
        confirm_url = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['validlink'])

        # POST new password
        post_response = self.client.post(confirm_url, {
            'new_password': 'BrandNewPassword123!',
            'confirm_password': 'BrandNewPassword123!',
        })
        self.assertEqual(post_response.status_code, 302)
        self.assertRedirects(post_response, reverse('password_reset_complete'))

        # Verify authentication with new password succeeds and old password fails
        login_fail = self.client.login(username='student1', password='oldpassword123')
        self.assertFalse(login_fail)
        login_success = self.client.login(username='student1', password='BrandNewPassword123!')
        self.assertTrue(login_success)

    @patch('accounts.views.send_account_setup_email')
    def test_admin_create_user_with_setup_email(self, mock_send_email):
        mock_send_email.return_value = True
        role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin Role")
        admin = User.objects.create_user(
            username="admin_test",
            full_name="Campus Administrator",
            institutional_id="ADM999",
            email="admin@campus.ac.za",
            contact_number="+27820000999",
            role=role_admin,
            password="adminpassword123",
            is_staff=True,
            is_verified=True
        )
        self.client.login(username="admin_test", password="adminpassword123")

        response = self.client.post(reverse('admin_create_user'), {
            'full_name': 'Kagiso Rabada',
            'institutional_id': '202477889',
            'email': 'kagiso@campus.ac.za',
            'contact_number': '+27720001122',
            'role': 'STUDENT',
            'password': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user_management'))

        created = User.objects.get(institutional_id='202477889')
        self.assertFalse(created.is_verified)
        self.assertTrue(created.is_active)
        self.assertEqual(created.role.role_name, Role.STUDENT)
        mock_send_email.assert_called_once_with(created, request=mock_send_email.call_args[1]['request'])

    @patch('accounts.views.send_account_setup_email')
    def test_admin_send_reset_email_view(self, mock_send_email):
        mock_send_email.return_value = True
        role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin Role 2")
        admin = User.objects.create_user(
            username="admin_test2",
            full_name="Campus Administrator 2",
            institutional_id="ADM998",
            email="admin2@campus.ac.za",
            contact_number="+27820000998",
            role=role_admin,
            password="adminpassword123",
            is_staff=True,
            is_verified=True
        )
        self.client.login(username="admin_test2", password="adminpassword123")

        response = self.client.get(reverse('admin_send_reset_email', kwargs={'user_id': self.user.id}))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user_management'))
        mock_send_email.assert_called_once_with(self.user, request=mock_send_email.call_args[1]['request'])

    @patch('accounts.management.commands.setup_master_admin.send_account_setup_email')
    def test_setup_master_admin_command(self, mock_send_email):
        from django.core.management import call_command
        mock_send_email.return_value = True
        call_command('setup_master_admin', email='mnnhlnkosi@gmail.com')
        admin = User.objects.get(email='mnnhlnkosi@gmail.com')
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)
        self.assertEqual(admin.role.role_name, Role.ADMIN)
        mock_send_email.assert_called_once()



class HealthCheckAndKeepaliveTests(TestCase):
    """Unit tests for Render & Supabase keepalive health check endpoint and pulse."""

    def test_healthz_endpoint_status(self):
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['database'], 'connected')

    def test_api_ping_endpoint_status(self):
        response = self.client.get(reverse('api_ping'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')

    @patch('accounts.management.commands.keepalive.requests.get')
    def test_perform_keepalive_pulse(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        from accounts.management.commands.keepalive import perform_keepalive_pulse
        result = perform_keepalive_pulse("http://testserver/healthz/")
        self.assertTrue(result['db_ok'])
        self.assertTrue(result['http_ok'])
        self.assertEqual(result['http_status'], 200)


class AdminPortalTests(TestCase):
    """Unit and integration tests for the dedicated Admin Command Center (/admin-portal/)."""

    def setUp(self):
        self.client = Client()
        self.role_admin, _ = Role.objects.get_or_create(role_name=Role.ADMIN, defaults={'description': 'Admin'})
        self.role_security, _ = Role.objects.get_or_create(role_name=Role.SECURITY, defaults={'description': 'Officer'})
        self.role_student, _ = Role.objects.get_or_create(role_name=Role.STUDENT, defaults={'description': 'Student'})
        self.role_staff, _ = Role.objects.get_or_create(role_name=Role.STAFF, defaults={'description': 'Staff'})

        self.admin = User.objects.create_user(
            username="portal_admin",
            full_name="Command Admin",
            institutional_id="ADM001",
            email="portal_admin@campus.ac.za",
            contact_number="+27820000001",
            role=self.role_admin,
            password="adminpassword123",
            is_staff=True,
            is_verified=True
        )

        self.student = User.objects.create_user(
            username="portal_student",
            full_name="Portal Student",
            institutional_id="STU001",
            email="portal_student@campus.ac.za",
            contact_number="+27820000002",
            role=self.role_student,
            password="studentpassword123",
            is_verified=True
        )

        self.officer = User.objects.create_user(
            username="portal_officer",
            full_name="Portal Officer",
            institutional_id="SEC001",
            email="portal_officer@campus.ac.za",
            contact_number="+27820000003",
            role=self.role_security,
            password="officerpassword123",
            is_verified=True
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('admin_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        self.assertIn('next=/admin-portal/', response.url)

    def test_student_forbidden(self):
        self.client.login(username="portal_student", password="studentpassword123")
        response = self.client.get(reverse('admin_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    def test_security_officer_forbidden(self):
        self.client.login(username="portal_officer", password="officerpassword123")
        response = self.client.get(reverse('admin_portal'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    def test_admin_access_granted(self):
        self.client.login(username="portal_admin", password="adminpassword123")
        response = self.client.get(reverse('admin_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/admin_portal.html')
        self.assertContains(response, "Admin Command Center")
        self.assertContains(response, "/admin-portal/")
        self.assertContains(response, "Institutional Principals")
        self.assertEqual(response.context['db_status'], 'connected')
        self.assertGreaterEqual(response.context['total_users'], 3)

    def test_mobile_client_blocked(self):
        self.client.login(username="portal_admin", password="adminpassword123")
        response = self.client.get(reverse('admin_portal'), HTTP_USER_AGENT='UPBSStudentPortal/1.0')
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    def test_role_redirect_for_admin(self):
        self.client.login(username="portal_admin", password="adminpassword123")
        response = self.client.get(reverse('role_redirect'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_portal'))

    def test_admin_portal_search_filter(self):
        self.client.login(username="portal_admin", password="adminpassword123")
        response = self.client.get(reverse('admin_portal') + '?q=STU001')
        self.assertEqual(response.status_code, 200)
        users = list(response.context['users'])
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].institutional_id, "STU001")

    def test_actions_return_url_support(self):
        self.client.login(username="portal_admin", password="adminpassword123")
        # Toggle status with return_url=admin_portal
        response = self.client.post(
            reverse('toggle_user_status', kwargs={'user_id': self.student.id}),
            {'return_url': 'admin_portal'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_portal'))

        # Update role with return_url=admin_portal
        response = self.client.post(
            reverse('update_user_role', kwargs={'user_id': self.student.id}),
            {'role_name': Role.STAFF, 'return_url': 'admin_portal'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_portal'))


class DedicatedAdminLoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.role_admin = Role.objects.create(role_name=Role.ADMIN, description="Admin")
        self.role_student = Role.objects.create(role_name=Role.STUDENT, description="Student")
        self.admin = User.objects.create_user(
            username="masteradmin",
            full_name="Brown Master Admin",
            institutional_id="ADM999",
            email="mnnhlnkosi@gmail.com",
            contact_number="+27820000001",
            role=self.role_admin,
            password="MySecretAdminPassword123!",
            is_staff=True,
            is_superuser=True,
            is_verified=True,
        )
        self.student = User.objects.create_user(
            username="student_regular",
            full_name="Regular Student",
            institutional_id="STU888",
            email="student@campus.ac.za",
            contact_number="+27710002222",
            role=self.role_student,
            password="StudentPassword123!",
            is_verified=True,
        )

    def test_admin_login_get(self):
        response = self.client.get(reverse('admin_login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/admin_login.html')
        self.assertContains(response, "Safety Command Sign-In")

    def test_admin_login_success_with_email(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'mnnhlnkosi@gmail.com',
            'password': 'MySecretAdminPassword123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_portal'))

    def test_admin_login_success_with_username(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'masteradmin',
            'password': 'MySecretAdminPassword123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_portal'))

    def test_non_admin_denied_on_admin_login(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'student@campus.ac.za',
            'password': 'StudentPassword123!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/admin_login.html')
        self.assertContains(response, "strictly restricted to System Administrators")

    def test_standard_login_supports_email(self):
        response = self.client.post(reverse('login'), {
            'username': 'student@campus.ac.za',
            'password': 'StudentPassword123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('role_redirect'), target_status_code=302)


class PurgeTestAccountsTests(TestCase):
    def setUp(self):
        self.role_admin = Role.objects.create(role_name=Role.ADMIN)
        self.role_student = Role.objects.create(role_name=Role.STUDENT)
        self.admin = User.objects.create_user(
            username="admin",
            institutional_id="ADM_PURGE_01",
            email="mnnhlnkosi@gmail.com",
            role=self.role_admin,
            password="KeepMyPasswordSafe!",
            is_superuser=True,
        )
        self.dummy1 = User.objects.create_user(
            username="student_dummy",
            institutional_id="STU_PURGE_01",
            email="dummy@student.ac.za",
            role=self.role_student,
            password="testpassword",
        )

    def test_purge_command(self):
        from django.core.management import call_command
        call_command('purge_test_accounts')
        self.assertFalse(User.objects.filter(username="student_dummy").exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
        admin = User.objects.get(username="admin")
        self.assertTrue(admin.check_password("KeepMyPasswordSafe!"))



