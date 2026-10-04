import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jobsystem", "0036_jobmatchalert"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyQuery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("subject", models.CharField(max_length=200)),
                ("question_text", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_review", "In Review"),
                            ("answered", "Answered"),
                            ("closed", "Closed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("admin_answer", models.TextField(blank=True)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source",
                    models.CharField(
                        default="chatbot",
                        help_text="Where this query came from (chatbot, form, etc.)",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "answered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="answered_company_queries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="raised_queries",
                        to="jobsystem.companyprofile",
                    ),
                ),
                (
                    "related_drive",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="related_queries",
                        to="jobsystem.placementdrive",
                    ),
                ),
                (
                    "related_job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="related_queries",
                        to="jobsystem.job",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Company queries",
                "ordering": ["-created_at"],
            },
        ),
    ]
