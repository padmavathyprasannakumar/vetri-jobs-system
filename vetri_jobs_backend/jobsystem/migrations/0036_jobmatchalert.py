from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jobsystem', '0035_mockinterviewsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobMatchAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_alerts', to='jobsystem.job')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_match_alerts', to='jobsystem.studentprofile')),
            ],
            options={
                'unique_together': {('student', 'job')},
            },
        ),
    ]
