"""
Creates a Super Admin account.

Usage:

    python manage.py create_super_admin \\
        --email superadmin@vetrijobs.com \\
        --username super_admin \\
        --password "ChangeMe123!"

Or run it with no arguments for interactive prompts:

    python manage.py create_super_admin
"""

import getpass

from django.core.management.base import BaseCommand, CommandError

from jobsystem.models import User


class Command(BaseCommand):

    help = "Create a Super Admin login account"

    def add_arguments(self, parser):

        parser.add_argument(
            "--email", type=str, default=None
        )

        parser.add_argument(
            "--username", type=str, default=None
        )

        parser.add_argument(
            "--password", type=str, default=None
        )

    def handle(self, *args, **options):

        email = options.get("email") or input("Email: ").strip()

        if User.objects.filter(email__iexact=email).exists():

            raise CommandError(
                f"A user with email '{email}' already exists."
            )

        username = (
            options.get("username")
            or input("Username: ").strip()
            or email.split("@")[0]
        )

        if User.objects.filter(username__iexact=username).exists():

            raise CommandError(
                f"A user with username '{username}' already exists."
            )

        password = options.get("password")

        if not password:

            password = getpass.getpass("Password: ")

            confirm = getpass.getpass("Password (again): ")

            if password != confirm:

                raise CommandError("Passwords did not match.")

        if len(password) < 8:

            raise CommandError(
                "Password should be at least 8 characters."
            )

        user = User.objects.create_user(

            username=username,

            email=email,

            password=password,

            role="super_admin",

            is_active=True,

            is_staff=True,

            is_verified=True,

        )

        self.stdout.write(

            self.style.SUCCESS(

                f"Super admin created: {user.email} "
                f"(username: {user.username}, id: {user.id})"

            )

        )
