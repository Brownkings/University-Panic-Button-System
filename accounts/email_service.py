"""
Email service utilities for UPBS account verification and password reset.
Handles token generation, template rendering, and delivery via configured email backend.
"""
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse

logger = logging.getLogger(__name__)


def build_absolute_url(request, path, base_url=None):
    """Safely builds an absolute URL using base_url, request, or settings fallback."""
    if base_url:
        return f"{base_url.rstrip('/')}{path}"
    if request:
        return request.build_absolute_uri(path)
    base_domain = getattr(settings, 'RENDER_EXTERNAL_HOSTNAME', None) or 'youthalliance.co.za'
    protocol = 'https' if ('youthalliance.co.za' in base_domain or not getattr(settings, 'DEBUG', False)) else 'http'
    return f"{protocol}://{base_domain}{path}"



def send_account_verification_email(user, otp_code=None, request=None):
    """
    Sends an account verification email containing the 6-digit OTP and a 1-click verification link.
    """
    if not user.email:
        logger.warning("User %s has no email address. Skipping verification email.", user.institutional_id)
        return False

    code = otp_code or user.otp_code
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_path = reverse('verify_email_link', kwargs={'uidb64': uidb64, 'token': token})
    verify_url = build_absolute_url(request, verify_path)

    subject = f"UPBS Account Verification Code: {code}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'UPBS Campus Safety <onboarding@resend.dev>')

    context = {
        'user': user,
        'otp_code': code,
        'verify_url': verify_url,
        'support_email': 'security@campus.ac.za',
    }

    try:
        text_content = render_to_string('emails/verification_email.txt', context)
        html_content = render_to_string('emails/verification_email.html', context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info("Verification email dispatched to %s for user %s", user.email, user.institutional_id)
        return True
    except Exception as exc:
        logger.exception("Failed to send verification email to %s: %s", user.email, exc)
        return False


def send_password_reset_email(user, request=None):
    """
    Generates a secure password reset token and sends the password reset email.
    """
    if not user.email:
        logger.warning("User %s has no email address. Skipping password reset email.", user.institutional_id)
        return False

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_path = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
    reset_url = build_absolute_url(request, reset_path)

    subject = "UPBS Campus Safety — Password Reset Request"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'UPBS Campus Safety <onboarding@resend.dev>')

    context = {
        'user': user,
        'reset_url': reset_url,
        'timeout_hours': 24,
        'support_email': 'security@campus.ac.za',
    }

    try:
        text_content = render_to_string('emails/password_reset_email.txt', context)
        html_content = render_to_string('emails/password_reset_email.html', context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info("Password reset email dispatched to %s for user %s", user.email, user.institutional_id)
        return True
    except Exception as exc:
        logger.exception("Failed to send password reset email to %s: %s", user.email, exc)
        return False


def get_user_activation_url(user, request=None, base_url=None):
    """
    Generates the cryptographically secure 24-hour activation and password setup URL for a user.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    setup_path = reverse('password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
    return build_absolute_url(request, setup_path, base_url=base_url)


def send_account_setup_email(user, request=None, base_url=None):
    """
    Sends an account activation and initial password setup email to a newly provisioned student,
    staff member, officer, or administrator via Resend.
    """
    if not user.email:
        logger.warning("User %s has no email address. Skipping account setup email.", user.institutional_id)
        return False

    setup_url = get_user_activation_url(user, request=request, base_url=base_url)

    subject = "UPBS Campus Safety — Set Up Your Account & Password"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'UPBS Campus Safety <onboarding@resend.dev>')

    context = {
        'user': user,
        'setup_url': setup_url,
        'timeout_hours': 24,
        'support_email': 'security@campus.ac.za',
    }

    try:
        text_content = render_to_string('emails/account_setup_email.txt', context)
        html_content = render_to_string('emails/account_setup_email.html', context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        sent_count = msg.send(fail_silently=False)
        delivered = bool(sent_count is None or (isinstance(sent_count, int) and sent_count > 0))
        logger.info("Account setup email dispatched to %s for user %s (delivered: %s)", user.email, user.institutional_id, delivered)
        return delivered
    except Exception as exc:
        logger.exception("Failed to send account setup email to %s: %s", user.email, exc)
        return False

