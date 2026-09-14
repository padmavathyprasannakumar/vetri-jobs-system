"""
Custom Django email backend that sends via SendGrid's REST API
(https://api.sendgrid.com) instead of raw SMTP.

Why this exists: Render (and many cloud hosts) block or silently
throttle outbound SMTP connections (port 587/465/25). That made
django.core.mail's default SMTP backend hang until gunicorn's
worker timeout killed the whole request - see the EMAIL_TIMEOUT
comment in settings.py for the other half of that fix. SendGrid's
API runs over plain HTTPS (port 443), which cloud hosts never
block, so this sidesteps the problem entirely instead of just
timing out faster.

This plugs into Django's standard email backend interface, so
every existing call to django.core.mail.send_mail() elsewhere in
the codebase keeps working unchanged - only settings.EMAIL_BACKEND
needs to point here (done conditionally in settings.py, based on
whether SENDGRID_API_KEY is set).

NOTE ON fail_silently: every caller in this codebase (see
notification_engine.py) sends with fail_silently=True, on purpose -
a broken notification should never break the action that triggered
it (applying, verifying a student, etc). But that means Django
swallows any exception raised here before it ever reaches the
caller's own try/except. Without the logger calls below, a real
SendGrid rejection (bad API key, unverified sender, rate limit)
and "nothing happened" would look identical from the outside -
nothing printed, nothing raised, nothing in Render's logs. The
logger.error() calls make sure the actual SendGrid response body
still shows up in Render's logs even when fail_silently swallows
the exception itself.
"""

import logging

import requests

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger("jobsystem")

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class SendGridBackend(BaseEmailBackend):

    def send_messages(self, email_messages):

        if not email_messages:
            return 0

        api_key = getattr(settings, "SENDGRID_API_KEY", None)

        if not api_key:

            logger.error(
                "SendGridBackend: SENDGRID_API_KEY is not set - "
                "cannot send email."
            )

            if not self.fail_silently:
                raise ValueError(
                    "SENDGRID_API_KEY is not set - cannot send email "
                    "via SendGridBackend."
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

        # SendGrid rejects sends from an address that isn't verified
        # (Single Sender Verification or a verified domain).
        sender_email = (
            getattr(settings, "SENDGRID_SENDER_EMAIL", "")
            or message.from_email
            or getattr(settings, "DEFAULT_FROM_EMAIL", "")
        )

        sender_name = getattr(settings, "SENDGRID_SENDER_NAME", "") or None

        from_field = {"email": sender_email}

        if sender_name:
            from_field["name"] = sender_name

        content = [{"type": "text/plain", "value": message.body}]

        # If this is a multipart email with an HTML alternative
        # (message.attach_alternative(html, "text/html")), include
        # that too.
        for alt_content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                content.append({"type": "text/html", "value": alt_content})
                break

        personalization = {"to": [{"email": addr} for addr in message.to]}

        if getattr(message, "cc", None):
            personalization["cc"] = [{"email": addr} for addr in message.cc]

        if getattr(message, "bcc", None):
            personalization["bcc"] = [{"email": addr} for addr in message.bcc]

        payload = {
            "personalizations": [personalization],
            "from": from_field,
            "subject": message.subject,
            "content": content,
        }

        try:

            response = requests.post(
                SENDGRID_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

            response.raise_for_status()

        except requests.exceptions.HTTPError:

            # SendGrid puts the actual reason (unverified sender,
            # bad API key scope, invalid payload field, etc) in the
            # response body - the status code alone isn't enough to
            # debug this from Render's logs.
            logger.error(
                "SendGrid API error (%s) sending to %s: %s",
                response.status_code,
                message.to,
                response.text,
            )

            raise

        except requests.exceptions.RequestException as e:

            logger.error(
                "SendGrid request failed sending to %s: %s",
                message.to,
                e,
            )

            raise

        else:

            logger.debug(
                "SendGrid: sent '%s' to %s",
                message.subject,
                message.to,
            )
