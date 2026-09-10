# Generated migration for the new "new_job_posted_admin_alert"
# event choice on NotificationChannelSetting.event_key. This is
# a choices-metadata-only change (no new column), but Django
# still tracks it so makemigrations doesn't keep re-detecting it.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobsystem', '0030_fix_blank_student_ids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificationchannelsetting',
            name='event_key',
            field=models.CharField(
                choices=[
                    ('registration_confirmation', 'Registration Confirmation'),
                    ('profile_verification', 'Profile Verification'),
                    ('new_job_alert', 'New Job Alert'),
                    ('application_confirmation', 'Application Confirmation'),
                    ('shortlisted', 'Shortlist Notification'),
                    ('interview_scheduled', 'Interview Schedule'),
                    ('interview_reminder', 'Interview Reminder'),
                    ('selected', 'Selection Notification'),
                    ('rejected', 'Rejection Notification'),
                    ('drive_reminder', 'Placement Drive Reminder'),
                    ('new_job_posted_admin_alert', 'New Job Posted (Admin Alert)'),
                ],
                max_length=40,
                unique=True,
            ),
        ),
    ]