from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jobsystem', '0034_studentprofile_placement_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='MockInterviewSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_title', models.CharField(blank=True, max_length=200)),
                ('turns', models.JSONField(blank=True, default=list, help_text="List of {'question': str, 'answer': str|None} in order.")),
                ('status', models.CharField(choices=[('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='in_progress', max_length=20)),
                ('score_report', models.JSONField(blank=True, help_text='Set once the session concludes: overall_score, technical_score, communication_score, strengths, improvements, question_feedback.', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mock_interview_sessions', to='jobsystem.studentprofile')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
