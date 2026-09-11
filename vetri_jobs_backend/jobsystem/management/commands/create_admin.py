import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        User = get_user_model()

        email = os.environ.get("DJANGO_ADMIN_EMAIL")
        username = os.environ.get("DJANGO_ADMIN_USERNAME")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")

        if not email or not password:
            self.stdout.write("Admin environment variables missing")
            return

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username
            }
        )

        user.username = username
        user.email = email
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()

        self.stdout.write(
            "Admin account created/updated successfully"
        )
