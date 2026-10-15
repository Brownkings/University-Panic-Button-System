"""
Custom Django Email Backend for Resend Transactional Email API.
Uses requests to dispatch emails via https://api.resend.com/emails.
"""
import logging
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """
    Standard Django Email Backend implementation that delivers emails via the
    Resend REST API (https://api.resend.com/emails).
    """

    RESEND_API_URL = "https://api.resend.com/emails"

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'RESEND_API_KEY', '') if api_key is None else api_key

    def send_messages(self, email_messages):
        """
        Sends one or more EmailMessage / EmailMultiAlternatives instances via Resend API.
        Returns the number of successfully delivered messages.
        """
        if not email_messages:
            return 0

        if not self.api_key:
            logger.warning("RESEND_API_KEY is not configured. Email will not be delivered to external recipients.")
            if not self.fail_silently and not getattr(settings, 'DEBUG', False):
                logger.info("Resend mock mode active: skipping delivery.")
            return 0

        sent_count = 0
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for message in email_messages:
            try:
                from_email = message.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'security@youthalliance.co.za')
                if not from_email or 'onboarding@resend.dev' in from_email:
                    from_email = 'UPBS Campus Safety <security@youthalliance.co.za>'
                recipients = list(message.to)
                if not recipients:
                    continue

                # Detect HTML body if present in alternatives
                html_content = None
                if hasattr(message, 'alternatives'):
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            html_content = content
                            break

                # If the main body itself is HTML
                if getattr(message, 'content_subtype', '') == 'html':
                    html_content = message.body
                    text_content = ""
                else:
                    text_content = message.body

                payload = {
                    "from": from_email,
                    "to": recipients,
                    "subject": message.subject,
                }
                if text_content:
                    payload["text"] = text_content
                if html_content:
                    payload["html"] = html_content
                if getattr(message, 'cc', None):
                    payload["cc"] = list(message.cc)
                if getattr(message, 'bcc', None):
                    payload["bcc"] = list(message.bcc)
                if getattr(message, 'reply_to', None):
                    payload["reply_to"] = message.reply_to[0] if isinstance(message.reply_to, list) else message.reply_to

                response = requests.post(
                    self.RESEND_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=10
                )

                if response.status_code in (200, 201):
                    sent_count += 1
                    logger.info("Email '%s' successfully dispatched via Resend (ID: %s)", message.subject, response.json().get('id'))
                else:
                    err_msg = f"Resend API error [{response.status_code}]: {response.text}"
                    logger.error(err_msg)
                    if not self.fail_silently:
                        raise RuntimeError(err_msg)

            except Exception as exc:
                logger.exception("Failed to dispatch email via Resend: %s", exc)
                if not self.fail_silently:
                    raise

        return sent_count
