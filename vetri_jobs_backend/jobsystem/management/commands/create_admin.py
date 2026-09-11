import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        User = get_user_model()

        email = os.environ.get("DJANGO_ADMIN_EMAIL")
        username = os.environ.get("DJANGO_ADMIN_USERNAME")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")

        # Check username OR email existing
        user = User.objects.filter(username=username).first()

        if not user:
            user = User.objects.filter(email=email).first()

        if user:
            user.username = username
            user.email = email
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    "Admin user updated successfully"
                )
            )

        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "New admin user created successfully"
                )
            )
