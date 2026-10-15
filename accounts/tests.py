from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from accounts.models import User, Role
from accounts.email_backend import ResendEmailBackend
from accounts.email_service import send_account_verification_email, send_password_reset_email


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

    @patch('accounts.views.send_password_reset_email')
    def test_admin_create_user_with_reset_email(self, mock_send_email):
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
            'send_reset': '1',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user_management'))

        created = User.objects.get(institutional_id='202477889')
        self.assertTrue(created.is_verified)
        self.assertTrue(created.is_active)
        self.assertEqual(created.role.role_name, Role.STUDENT)
        mock_send_email.assert_called_once_with(created, request=mock_send_email.call_args[1]['request'])

    @patch('accounts.views.send_password_reset_email')
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


