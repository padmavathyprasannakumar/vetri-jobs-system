"""
Custom Django email backend that sends via Brevo's REST API
(https://api.brevo.com) instead of raw SMTP.

Why this exists: Render (and many cloud hosts) block or silently
throttle outbound SMTP connections (port 587/465/25). That made
django.core.mail's default SMTP backend hang until gunicorn's
worker timeout killed the whole request - see the EMAIL_TIMEOUT
comment in settings.py for the other half of that fix. Brevo's API
runs over plain HTTPS (port 443), which cloud hosts never block,
so this sidesteps the problem entirely instead of just timing out
faster.

This plugs into Django's standard email backend interface, so
every existing call to django.core.mail.send_mail() elsewhere in
the codebase keeps working unchanged - only settings.EMAIL_BACKEND
needs to point here (done conditionally in settings.py, based on
whether BREVO_API_KEY is set).
"""

import requests

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoAPIBackend(BaseEmailBackend):

    def send_messages(self, email_messages):

        if not email_messages:
            return 0

        api_key = getattr(settings, "BREVO_API_KEY", None)

        if not api_key:
            if not self.fail_silently:
                raise ValueError(
                    "BREVO_API_KEY is not set - cannot send email "
                    "via BrevoAPIBackend."
                )
            return 0

        sent_count = 0

        for message in email_messages:

            try:

                self._send_one(message, api_key)

                sent_count += 1

            except Exception:

                if not self.fail_silently:
                    raise

        return sent_count

    def _send_one(self, message, api_key):

        # Prefer the Brevo-verified sender (BREVO_SENDER_EMAIL/NAME)
        # since Brevo rejects sends from an address it hasn't
        # verified - falls back to the message's own from_email or
        # DEFAULT_FROM_EMAIL if those aren't set, for local dev.
        sender_email = (
            getattr(settings, "BREVO_SENDER_EMAIL", "")
            or message.from_email
            or getattr(settings, "DEFAULT_FROM_EMAIL", "")
        )

        sender_name = getattr(settings, "BREVO_SENDER_NAME", "") or None

        sender = {"email": sender_email}

        if sender_name:
            sender["name"] = sender_name

        payload = {
            "sender": sender,
            "to": [{"email": addr} for addr in message.to],
            "subject": message.subject,
            "textContent": message.body,
        }

        # Carbon copy / blind carbon copy, if the caller set them.
        if getattr(message, "cc", None):
            payload["cc"] = [{"email": addr} for addr in message.cc]

        if getattr(message, "bcc", None):
            payload["bcc"] = [{"email": addr} for addr in message.bcc]

        # If this is a multipart email with an HTML alternative
        # (message.attach_alternative(html, "text/html")), send
        # that as the HTML body instead of plain text only.
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["htmlContent"] = content
                break

        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=10,
        )

        response.raise_for_status()
