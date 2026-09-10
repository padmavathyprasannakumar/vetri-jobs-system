"""
Seeds common Departments and Courses so the Student Register
page's Course/Department dropdowns aren't empty on a fresh
install. Safe to run multiple times - uses get_or_create, so
it will never create duplicates.

    python manage.py seed_lookup_data
"""

from django.core.management.base import BaseCommand

from jobsystem.models import Department, Course


DEPARTMENTS = [
    ("Computer Science", "CSE"),
    ("Information Technology", "IT"),
    ("Electronics and Communication", "ECE"),
    ("Electrical and Electronics", "EEE"),
    ("Mechanical Engineering", "MECH"),
    ("Civil Engineering", "CIVIL"),
    ("Business Administration", "MBA"),
]

COURSES = [
    ("B.Tech Computer Science", "Computer Science", 4),
    ("B.Tech Information Technology", "Information Technology", 4),
    ("B.Tech Electronics and Communication", "Electronics and Communication", 4),
    ("B.Tech Electrical and Electronics", "Electrical and Electronics", 4),
    ("B.Tech Mechanical Engineering", "Mechanical Engineering", 4),
    ("B.Tech Civil Engineering", "Civil Engineering", 4),
    ("MBA", "Business Administration", 2),
    ("M.Tech Computer Science", "Computer Science", 2),
]


class Command(BaseCommand):

    help = "Seed common departments and courses for the registration dropdowns"

    def handle(self, *args, **options):

        dept_count = 0

        dept_lookup = {}

        for name, code in DEPARTMENTS:

            dept, created = Department.objects.get_or_create(
                name=name,
                defaults={"code": code, "is_active": True},
            )

            dept_lookup[name] = dept

            if created:
                dept_count += 1

        course_count = 0

        for name, dept_name, duration in COURSES:

            _, created = Course.objects.get_or_create(
                name=name,
                defaults={
                    "department": dept_lookup.get(dept_name),
                    "duration_years": duration,
                    "is_active": True,
                },
            )

            if created:
                course_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {dept_count} new department(s) and "
                f"{course_count} new course(s). "
                f"({Department.objects.count()} departments, "
                f"{Course.objects.count()} courses total)"
            )
        )
