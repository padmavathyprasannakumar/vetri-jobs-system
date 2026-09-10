# Adds the new "application_under_review" event choice on
# NotificationChannelSetting.event_key. Choices-metadata-only
# change (no new column).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobsystem', '0031_new_job_posted_admin_alert_event'),
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
                    ('application_under_review', 'Application Under Review'),
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