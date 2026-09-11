import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        User = get_user_model()

        email = os.environ.get("DJANGO_ADMIN_EMAIL")
        username = os.environ.get("DJANGO_ADMIN_USERNAME")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD")


        # Remove duplicate email users except target user
        User.objects.filter(email=email).exclude(
            username=username
        ).delete()


        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email
            }
        )


        user.email = email
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save()


        if created:
            self.stdout.write(
                "Admin created successfully"
            )
        else:
            self.stdout.write(
                "Admin updated successfully"
            )
