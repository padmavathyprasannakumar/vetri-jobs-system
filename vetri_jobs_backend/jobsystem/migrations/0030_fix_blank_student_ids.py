# Generated migration to fix a pre-existing data bug: StudentProfile.student_id
# is unique=True but wasn't being set explicitly on registration, so it
# defaulted to "" (empty string) instead of NULL. Since unique=True still
# applies to duplicate empty strings, any StudentProfile rows already saved
# with student_id="" are blocking every future registration that also
# leaves it blank. This converts existing "" values to NULL, which is
# exempt from the unique constraint.

from django.db import migrations


def fix_blank_student_ids(apps, schema_editor):

    StudentProfile = apps.get_model('jobsystem', 'StudentProfile')

    StudentProfile.objects.filter(student_id="").update(student_id=None)


def reverse_noop(apps, schema_editor):

    # Not reversible - there's no way to know which NULLs used to be ""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('jobsystem', '0029_passwordresetotp'),
    ]

    operations = [
        migrations.RunPython(fix_blank_student_ids, reverse_noop),
    ]