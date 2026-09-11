import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        User = get_user_model()

        email = os.getenv("DJANGO_ADMIN_EMAIL")
        username = os.getenv("DJANGO_ADMIN_USERNAME")
        password = os.getenv("DJANGO_ADMIN_PASSWORD")

        user = User.objects.filter(username=username).first()

        if user:
            user.email = email
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()

            self.stdout.write(
                "Existing admin updated successfully"
            )

        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )

            self.stdout.write(
                "New admin created successfully"
            )
