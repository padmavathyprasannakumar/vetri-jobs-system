"""
Sends a reminder (in-app + email + WhatsApp, per the admin's
channel settings) for every interview scheduled for tomorrow.

Run this once a day from any scheduler (cron, Windows Task
Scheduler, a hosting platform's scheduled jobs, etc):

    python manage.py send_interview_reminders
"""

from django.core.management.base import BaseCommand

from django.utils import timezone

from datetime import timedelta

from jobsystem.models import Interview

from jobsystem.services.notification_engine import dispatch


class Command(BaseCommand):

    help = "Send WhatsApp/email/in-app reminders for interviews happening tomorrow"

    def handle(self, *args, **options):

        tomorrow_start = timezone.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        tomorrow_end = tomorrow_start + timedelta(days=1)

        interviews = Interview.objects.filter(
            interview_date__gte=tomorrow_start,
            interview_date__lt=tomorrow_end,
            status__in=["scheduled", "rescheduled"],
        ).select_related(
            "application__student__user",
            "application__job",
            "application__job__company",
        )

        count = 0

        for interview in interviews:

            application = interview.application

            try:

                dispatch(
                    "interview_reminder",
                    application.student.user,
                    {
                        "job_title": application.job.title,
                        "company_name": (
                            application.job.company.company_name
                            if application.job.company else "the company"
                        ),
                        "interview_date": interview.interview_date.strftime("%d %b %Y"),
                        "interview_time": interview.interview_date.strftime("%I:%M %p"),
                        "mode": interview.get_interview_mode_display(),
                    },
                )

                count += 1

            except Exception as e:

                self.stderr.write(
                    f"Failed to send reminder for interview {interview.id}: {e}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {count} interview reminder(s) for tomorrow."
            )
        )
