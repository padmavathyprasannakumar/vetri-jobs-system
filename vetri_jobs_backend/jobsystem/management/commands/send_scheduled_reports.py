"""
Sends the placement report summary by email to everyone with an
active ReportSchedule, respecting their chosen frequency.

Run this once a day from any scheduler (cron, Windows Task
Scheduler, etc). It only actually emails a given schedule when
that day matches its frequency:

  - weekly:  sent every Monday
  - monthly: sent on the 1st of the month

    python manage.py send_scheduled_reports
"""

from django.core.management.base import BaseCommand

from django.utils import timezone

from django.core.mail import send_mail

from django.conf import settings

from jobsystem.models import (
    ReportSchedule,
    StudentProfile,
    CompanyProfile,
    Application,
    Job,
)


class Command(BaseCommand):

    help = "Email the placement report summary to everyone with an active schedule"

    def add_arguments(self, parser):

        parser.add_argument(
            "--test",
            action="store_true",
            help=(
                "Ignore the weekly/monthly day check and send to "
                "every active schedule right now, regardless of "
                "today's date. Useful for verifying email "
                "delivery without waiting for Monday or the 1st."
            ),
        )

    def handle(self, *args, **options):

        test_mode = options.get("test", False)

        today = timezone.now()

        is_monday = today.weekday() == 0

        is_first_of_month = today.day == 1

        schedules = ReportSchedule.objects.filter(active=True)

        total_students = StudentProfile.objects.count()

        total_companies = CompanyProfile.objects.count()

        total_jobs = Job.objects.count()

        total_applications = Application.objects.count()

        selected_count = Application.objects.filter(status="selected").count()

        placement_rate = (
            round((selected_count / total_students) * 100, 1)
            if total_students else 0
        )

        summary = (
            "Vetri Jobs - Placement Report Summary\n\n"
            f"Total Students: {total_students}\n"
            f"Companies: {total_companies}\n"
            f"Total Jobs: {total_jobs}\n"
            f"Total Applications: {total_applications}\n"
            f"Placement Rate: {placement_rate}%\n\n"
            "Log in to the Placement Portal for the full report."
        )

        count = 0

        if not schedules.exists():

            self.stdout.write(
                self.style.WARNING(
                    "No active ReportSchedule records found. Set "
                    "one up from the Reports page's 'Schedule "
                    "Automated Reports' button first."
                )
            )

        for schedule in schedules:

            due = test_mode or (
                (schedule.frequency == "weekly" and is_monday) or
                (schedule.frequency == "monthly" and is_first_of_month)
            )

            if not due:

                self.stdout.write(
                    f"Skipping {schedule.email} - not due today "
                    f"(frequency={schedule.frequency}). Use --test "
                    f"to send anyway."
                )

                continue

            try:

                send_mail(
                    subject="Vetri Jobs - Your Scheduled Placement Report",
                    message=summary,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[schedule.email],
                    fail_silently=False,
                )

                schedule.last_sent_at = today

                schedule.save()

                count += 1

            except Exception as e:

                self.stderr.write(
                    f"Failed to send scheduled report to {schedule.email}: {e}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {count} scheduled report(s)."
            )
        )