"""
Vetri Jobs WhatsApp Notification Service

Handles:
1. Registration confirmation
2. Profile verification
3. New job alerts
4. Application confirmation
5. Application under review
6. Shortlisted
7. Interview scheduled
8. Interview reminder
9. Selected
10. Rejected
11. Placement drive reminder
12. Placement admin notifications

Uses Meta WhatsApp Cloud API.
"""

import requests

from django.utils import timezone

from jobsystem.models import (
    WhatsAppSetting,
    WhatsAppMessage,
)


WHATSAPP_API_VERSION = "v25.0"

# IMPORTANT:
# This exact template must exist in Meta WhatsApp Manager.
WHATSAPP_TEMPLATE_NAME = "vetri_notification"
WHATSAPP_LANGUAGE = "en_US"


# =====================================================
# GET ACTIVE WHATSAPP SETTING
# =====================================================

def _get_active_setting():

    return WhatsAppSetting.objects.filter(
        enabled=True
    ).first()


# =====================================================
# CLEAN PHONE NUMBER
# =====================================================

def _get_phone_number(user):

    if not user:
        return None

    phone_number = (
        getattr(user, "whatsapp_number", None)
        or getattr(user, "phone", None)
    )

    if not phone_number:
        return None

    phone_number = "".join(
        ch for ch in str(phone_number)
        if ch.isdigit()
    )

    return phone_number or None


# =====================================================
# SEND TEMPLATE MESSAGE
# =====================================================

def send_whatsapp_message(user, message):
    """
    Sends the given text inside the approved Meta template:

        vetri_notification

    Template should contain exactly one body variable {{1}}.
    """

    phone_number = _get_phone_number(user)

    if not phone_number:
        print(
            "WhatsApp: user has no WhatsApp/phone number:",
            user
        )
        return False


    message = str(message or "").strip()

    if not message:
        return False


    # -------------------------------------------------
    # Create log first
    # -------------------------------------------------

    log = WhatsAppMessage.objects.create(
        user=user,
        phone_number=phone_number,
        message=message,
        status="pending",
    )


    setting = _get_active_setting()


    if not setting:

        log.status = "failed"

        log.provider_response = (
            "No enabled WhatsAppSetting configured."
        )

        log.save()

        return False


    if not setting.phone_number_id:

        log.status = "failed"

        log.provider_response = (
            "WhatsApp Phone Number ID is missing."
        )

        log.save()

        return False


    if not setting.access_token:

        log.status = "failed"

        log.provider_response = (
            "WhatsApp access token is missing."
        )

        log.save()

        return False


    try:

        # -------------------------------------------------
        # META API URL
        # -------------------------------------------------

        url = (
            f"https://graph.facebook.com/"
            f"{WHATSAPP_API_VERSION}/"
            f"{setting.phone_number_id}/messages"
        )


        headers = {
            "Authorization":
                f"Bearer {setting.access_token}",

            "Content-Type":
                "application/json",
        }


        # -------------------------------------------------
        # TEMPLATE PAYLOAD
        # -------------------------------------------------

        payload = {
            "messaging_product": "whatsapp",

            "recipient_type": "individual",

            "to": phone_number,

            "type": "template",

            "template": {

                "name": WHATSAPP_TEMPLATE_NAME,

                "language": {
                    "code": WHATSAPP_LANGUAGE
                },

                "components": [
                    {
                        "type": "body",

                        "parameters": [
                            {
                                "type": "text",
                                "text": message,
                            }
                        ],
                    }
                ],
            },
        }


        # -------------------------------------------------
        # SEND REQUEST
        # -------------------------------------------------

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=15,
        )


        # Debug output
        print("========== WHATSAPP RESPONSE ==========")
        print("Phone:", phone_number)
        print("HTTP:", response.status_code)
        print("Response:", response.text)
        print("=======================================")


        log.provider_response = (
            f"HTTP {response.status_code}: "
            f"{response.text}"
        )[:2000]


        # Meta accepted request
        if response.status_code in (200, 201):

            log.status = "sent"

            log.sent_at = timezone.now()

            log.save()

            return True


        log.status = "failed"

        log.save()

        return False


    except requests.RequestException as e:

        log.status = "failed"

        log.provider_response = (
            f"HTTP request error: {str(e)}"
        )[:2000]

        log.save()

        return False


    except Exception as e:

        log.status = "failed"

        log.provider_response = (
            f"Unexpected WhatsApp error: {str(e)}"
        )[:2000]

        log.save()

        return False


# =====================================================
# EVENT MESSAGES
# =====================================================

EVENT_MESSAGES = {

    "registration_confirmation": (
        "Vetri Placements\n\n"
        "Hi {name}, welcome to Vetri Jobs! "
        "Your account has been created successfully. "
        "Complete your profile to start applying for jobs."
    ),

    "profile_verification": (
        "Vetri Placements\n\n"
        "Hi {name}, your profile has been verified successfully. "
        "You can now apply for opportunities on Vetri Jobs."
    ),

    "new_job_alert": (
        "Vetri Placements\n\n"
        "New job opportunity!\n\n"
        "Position: {job_title}\n"
        "Company: {company_name}\n"
        "Location: {location}\n\n"
        "Please check Vetri Jobs portal to apply."
    ),

    "application_confirmation": (
        "Vetri Placements\n\n"
        "Hi {name}, your application for {job_title} "
        "at {company_name} has been received successfully. "
        "We will notify you of further updates."
    ),

    "application_under_review": (
        "Vetri Placements\n\n"
        "Hi {name}, your application for {job_title} "
        "at {company_name} is currently under review. "
        "We will keep you updated."
    ),

    "shortlisted": (
        "Vetri Placements\n\n"
        "Congratulations {name}!\n\n"
        "You have been shortlisted for the "
        "{job_title} position at {company_name}.\n\n"
        "Please check your Vetri Jobs portal "
        "for the next steps."
    ),

    "interview_scheduled": (
        "Vetri Placements\n\n"
        "Hi {name}, your interview has been scheduled.\n\n"
        "Position: {job_title}\n"
        "Company: {company_name}\n"
        "Interview Date: {interview_date}\n"
        "Time: {interview_time}\n"
        "Mode: {mode}\n\n"
        "Please check your portal for details."
    ),

    "interview_reminder": (
        "Vetri Placements\n\n"
        "Interview Reminder\n\n"
        "Hi {name}, this is a reminder for your "
        "upcoming interview.\n\n"
        "Position: {job_title}\n"
        "Company: {company_name}\n"
        "Date: {interview_date}\n"
        "Time: {interview_time}\n"
        "Mode: {mode}\n\n"
        "All the best!"
    ),

    "selected": (
        "Vetri Placements\n\n"
        "Congratulations {name}!\n\n"
        "You have been selected for the "
        "{job_title} position at {company_name}.\n\n"
        "Our placement team will contact you "
        "with further details."
    ),

    "rejected": (
        "Vetri Placements\n\n"
        "Hi {name}, thank you for applying for "
        "{job_title} at {company_name}.\n\n"
        "Unfortunately, we will not proceed with "
        "your application this time.\n\n"
        "We encourage you to apply for other opportunities."
    ),

    "drive_reminder": (
        "Vetri Placements\n\n"
        "Placement Drive Reminder\n\n"
        "Company: {company_name}\n"
        "Date: {drive_date}\n"
        "Venue: {venue}\n\n"
        "Please make sure you are registered."
    ),

    "new_job_posted_admin_alert": (
        "Vetri Placements\n\n"
        "New job posting requires review.\n\n"
        "Company: {company_name}\n"
        "Position: {job_title}\n"
        "Location: {location}\n\n"
        "Please review it in the Placement Admin portal."
    ),
}


# =====================================================
# SEND AUTOMATIC WHATSAPP EVENT
# =====================================================

def send_whatsapp_event(
    user,
    event_key,
    context=None
):

    context = dict(context or {})


    if not user:
        return False


    # Default name
    context.setdefault(
        "name",
        getattr(user, "first_name", None)
        or getattr(user, "username", None)
        or "Student"
    )


    # Defaults so format() never crashes
    defaults = {
        "job_title": "",
        "company_name": "",
        "location": "",
        "interview_date": "",
        "interview_time": "",
        "mode": "",
        "drive_date": "",
        "venue": "",
    }


    for key, value in defaults.items():

        context.setdefault(
            key,
            value
        )


    template = EVENT_MESSAGES.get(
        event_key
    )


    if not template:

        print(
            "WhatsApp: unknown event key:",
            event_key
        )

        return False


    try:

        message = template.format(
            **context
        )

    except Exception as e:

        print(
            "WhatsApp message formatting error:",
            e
        )

        return False


    return send_whatsapp_message(
        user,
        message
    )


# =====================================================
# APPLICATION STATUS HELPER
# =====================================================

def notify_application_status_change(
    application
):

    if not application:
        return False


    student = getattr(
        application,
        "student",
        None
    )


    user = getattr(
        student,
        "user",
        None
    )


    if not user:
        return False


    status_event_map = {

        "reviewing":
            "application_under_review",

        "shortlisted":
            "shortlisted",

        "interview":
            "interview_scheduled",

        "selected":
            "selected",

        "rejected":
            "rejected",

    }


    event_key = status_event_map.get(
        application.status
    )


    if not event_key:
        return False


    job = getattr(
        application,
        "job",
        None
    )


    company = getattr(
        job,
        "company",
        None
    )


    context = {

        "name":
            getattr(
                student,
                "full_name",
                None
            )
            or getattr(
                user,
                "first_name",
                None
            )
            or getattr(
                user,
                "username",
                "Student"
            ),

        "job_title":
            getattr(
                job,
                "title",
                ""
            ),

        "company_name":
            getattr(
                company,
                "company_name",
                ""
            )
            if company
            else "",

    }


    return send_whatsapp_event(
        user=user,
        event_key=event_key,
        context=context,
    )