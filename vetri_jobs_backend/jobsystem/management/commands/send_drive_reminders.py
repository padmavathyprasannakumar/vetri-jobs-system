"""
Sends a reminder for every placement drive scheduled for
tomorrow, to every student registered for that drive.

Run this once a day from any scheduler:

    python manage.py send_drive_reminders
"""

from django.core.management.base import BaseCommand

from django.utils import timezone

from datetime import timedelta

from jobsystem.models import PlacementDrive

from jobsystem.services.notification_engine import dispatch


class Command(BaseCommand):

    help = "Send WhatsApp/email/in-app reminders for placement drives happening tomorrow"

    def handle(self, *args, **options):

        tomorrow = (timezone.now() + timedelta(days=1)).date()

        drives = PlacementDrive.objects.filter(
            drive_date=tomorrow,
        ).prefetch_related("students").select_related("company")

        count = 0

        for drive in drives:

            for student in drive.students.all():

                if not getattr(student, "user", None):

                    continue

                try:

                    dispatch(
                        "drive_reminder",
                        student.user,
                        {
                            "company_name": (
                                drive.company.company_name
                                if drive.company else "the company"
                            ),
                            "drive_date": drive.drive_date.strftime("%d %b %Y"),
                            "venue": drive.venue or "details on your dashboard",
                        },
                    )

                    count += 1

                except Exception as e:

                    self.stderr.write(
                        f"Failed to send reminder for drive {drive.id} "
                        f"to student {student.id}: {e}"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {count} placement drive reminder(s) for tomorrow."
            )
        )
