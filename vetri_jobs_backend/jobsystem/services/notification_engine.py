"""
Centralized Notification Engine (Requirement 22).

Every place in the codebase that needs to notify a student
(or company) about something should call `dispatch()` here
instead of creating a Notification / sending an email /
calling the WhatsApp service directly. This is what makes the
channel toggles in Django Admin (NotificationChannelSetting)
actually mean something - flip "Email" off for "Shortlisted"
and no shortlist emails go out, without touching any code that
triggers the event.

Usage:

    from jobsystem.services.notification_engine import dispatch

    dispatch(
        event_key="shortlisted",
        user=application.student.user,
        context={
            "job_title": application.job.title,
            "company_name": application.job.company.company_name,
        },
    )
"""

from django.utils import timezone


# =====================================================
# BUILT-IN MESSAGE TEMPLATES
# {placeholders} are filled in from the `context` dict
# passed to dispatch(). Every event has a WhatsApp-style
# message (matches the format shown in the spec: sender
# name, message, then labelled details) and a shorter
# in-app title/body pair.
# =====================================================

TEMPLATES = {

    "registration_confirmation": {
        "title": "Welcome to Vetri Jobs!",
        "in_app": "Hi {name}, your account has been created successfully. Complete your profile to start applying for jobs.",
        "whatsapp": "Vetri Placements\nHi {name}, welcome to Vetri Jobs! Your account has been created. Complete your profile to unlock job recommendations and apply for opportunities.",
        "email_subject": "Welcome to Vetri Jobs",
    },

    "profile_verification": {
        "title": "Profile verified",
        "in_app": "Hi {name}, your profile has been verified by the placement team. You're all set to apply for jobs.",
        "whatsapp": "Vetri Placements\nHi {name}, your profile has been verified. You can now apply for jobs on Vetri Jobs.",
        "email_subject": "Your profile has been verified",
    },

    "new_job_alert": {
        "title": "New job posted",
        "in_app": "A new opportunity matching your profile is live: {job_title} at {company_name}.",
        "whatsapp": "Vetri Placements\nNew job alert! {job_title} at {company_name} is now open for applications.\nLocation: {location}",
        "email_subject": "New job opportunity: {job_title}",
    },

    "application_confirmation": {
        "title": "Application submitted",
        "in_app": "Your application for {job_title} at {company_name} has been submitted successfully.",
        "whatsapp": "Vetri Placements\nHi {name}, your application for {job_title} at {company_name} has been received. We'll notify you of any updates.",
        "email_subject": "Application received: {job_title}",
    },

    "application_under_review": {
    "title": "Application under review",
    "in_app": (
        "Your application for {job_title} at {company_name} "
        "is now under review."
    ),
    "whatsapp": (
        "Vetri Placements\n"
        "Hi {name}, your application for {job_title} at "
        "{company_name} is now under review."
    ),
    "email_subject": (
        "Your application for {job_title} is under review"
    ),
},

    "shortlisted": {
        "title": "You've been shortlisted!",
        "in_app": "Good news! You've been shortlisted for {job_title} at {company_name}.",
        "whatsapp": "Vetri Placements\nYou have been shortlisted for the {job_title} position at {company_name}.",
        "email_subject": "You've been shortlisted for {job_title}",
    },

    "interview_scheduled": {
        "title": "Interview scheduled",
        "in_app": "An interview has been scheduled for {job_title} at {company_name} on {interview_date} at {interview_time} ({mode}).",
        "whatsapp": "Vetri Placements\nYour interview for {job_title} at {company_name} has been scheduled.\nInterview Date: {interview_date}\nTime: {interview_time}\nMode: {mode}",
        "email_subject": "Interview scheduled: {job_title}",
    },

    "interview_reminder": {
        "title": "Interview reminder",
        "in_app": "Reminder: your interview for {job_title} at {company_name} is on {interview_date} at {interview_time}.",
        "whatsapp": "Vetri Placements\nReminder: you have an interview for {job_title} at {company_name} tomorrow.\nDate: {interview_date}\nTime: {interview_time}\nMode: {mode}\nAll the best!",
        "email_subject": "Reminder: interview tomorrow for {job_title}",
    },

    "selected": {
        "title": "Congratulations - you're selected!",
        "in_app": "Congratulations! You've been selected for {job_title} at {company_name}.",
        "whatsapp": "Vetri Placements\nCongratulations! You have been selected for the {job_title} position at {company_name}. Our placement team will reach out with the offer details.",
        "email_subject": "You've been selected for {job_title}!",
    },

    "rejected": {
        "title": "Application update",
        "in_app": "Your application for {job_title} at {company_name} was not successful this time. Keep going - more opportunities are available.",
        "whatsapp": "Vetri Placements\nThank you for applying for {job_title} at {company_name}. We won't be moving forward with your application this time. We encourage you to keep applying to other opportunities.",
        "email_subject": "Update on your application for {job_title}",
    },

    "drive_reminder": {
        "title": "Placement drive reminder",
        "in_app": "Reminder: {company_name} is conducting a placement drive on {drive_date}. Make sure you're registered.",
        "whatsapp": "Vetri Placements\nReminder: {company_name}'s placement drive is on {drive_date} at {venue}. Don't miss it!",
        "email_subject": "Reminder: upcoming placement drive - {company_name}",
    },

}


def _format(template_str, context):

    try:

        return template_str.format(**{
            **{k: "" for k in [
                "name", "job_title", "company_name", "location",
                "interview_date", "interview_time", "mode",
                "drive_date", "venue",
            ]},
            **context,
        })

    except Exception:

        return template_str


def _get_channel_setting(event_key):

    from jobsystem.models import NotificationChannelSetting

    setting = NotificationChannelSetting.objects.filter(
        event_key=event_key
    ).first()

    if setting:

        return {
            "in_app": setting.in_app_enabled,
            "email": setting.email_enabled,
            "whatsapp": setting.whatsapp_enabled,
        }

    # Not configured yet (e.g. migration hasn't run) - default
    # to sending on every channel rather than silently going
    # dark on a real event.

    return {"in_app": True, "email": True, "whatsapp": True}


def dispatch(event_key, user, context=None):
    """
    Central notification dispatcher.

    Sends:
    1. In-app notification
    2. Email
    3. WhatsApp template message

    according to NotificationChannelSetting.
    """

    if not user:
        return

    context = dict(context or {})

    context.setdefault(
        "name",
        getattr(user, "first_name", None)
        or getattr(user, "username", "there")
    )

    template = TEMPLATES.get(event_key)

    if not template:
        print(
            f"notification_engine: "
            f"unknown event_key '{event_key}'"
        )
        return

    channels = _get_channel_setting(event_key)


    # =====================================================
    # IN-APP NOTIFICATION
    # =====================================================

    if channels["in_app"]:

        try:

            from jobsystem.models import Notification

            Notification.objects.create(
                user=user,
                title=template["title"],
                message=_format(
                    template["in_app"],
                    context
                ),
                notification_type=(
                    "interview"
                    if "interview" in event_key

                    else "application"
                    if event_key in (
                        "application_confirmation",
                        "application_under_review",
                        "shortlisted",
                        "selected",
                        "rejected",
                    )

                    else "job"
                    if event_key == "new_job_alert"

                    else "placement"
                    if event_key == "drive_reminder"

                    else "system"
                ),
            )

        except Exception as e:

            print(
                "notification_engine in-app error:",
                e
            )


    # =====================================================
    # EMAIL
    # =====================================================

    if (
        channels["email"]
        and getattr(user, "email", None)
    ):

        try:

            from django.core.mail import send_mail
            from django.conf import settings

            send_mail(
                subject=_format(
                    template["email_subject"],
                    context
                ),

                message=_format(
                    template["in_app"],
                    context
                ),

                from_email=getattr(
                    settings,
                    "DEFAULT_FROM_EMAIL",
                    None
                ),

                recipient_list=[
                    user.email
                ],

                fail_silently=False,
            )

        except Exception as e:

            print(
                "notification_engine email error:",
                e
            )


    # =====================================================
    # WHATSAPP - CANDIDATE
    # =====================================================

    if channels["whatsapp"]:

        try:

            from jobsystem.services.whatsapp import (
                send_whatsapp_event
            )

            whatsapp_sent = send_whatsapp_event(
                user=user,
                event_key=event_key,
                context=context,
            )

            if not whatsapp_sent:

                print(
                    f"WhatsApp was not sent. "
                    f"event={event_key}, "
                    f"user={user.id}"
                )

        except Exception as e:

            print(
                "notification_engine whatsapp error:",
                e
            )


    # =====================================================
    # WHATSAPP COPY TO PLACEMENT ADMIN
    # =====================================================

    ADMIN_COPY_EVENTS = {
        "registration_confirmation",
        "profile_verification",
        "application_confirmation",
        "application_under_review",
        "shortlisted",
        "interview_scheduled",
        "interview_reminder",
        "selected",
        "rejected",
    }


    if (
        channels["whatsapp"]
        and event_key in ADMIN_COPY_EVENTS
    ):

        try:

            from jobsystem.models import User

            from jobsystem.services.whatsapp import (
                send_whatsapp_event
            )

            placement_admins = User.objects.filter(
                role="placement_admin"
            )

            for admin in placement_admins:

                # Don't send duplicate copy
                # if current user itself is placement admin.

                if admin.id == user.id:
                    continue

                send_whatsapp_event(
                    user=admin,
                    event_key=event_key,
                    context=context,
                )

        except Exception as e:

            print(
                "placement admin whatsapp error:",
                e
            )