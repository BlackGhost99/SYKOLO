"""Staff portrait + optional professional introduction, held privately in the database."""
import django.db.models.deletion
from django.db import migrations, models


def private_table(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE "public"."institutions_staffprofile" ENABLE ROW LEVEL SECURITY')
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
        for (role,) in cursor.fetchall():
            cursor.execute(f'REVOKE ALL PRIVILEGES ON TABLE "public"."institutions_staffprofile" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0048_enrollment_assignment_audit")]

    operations = [
        migrations.CreateModel(
            name="StaffProfile",
            fields=[
                ("staff", models.OneToOneField(
                    to="institutions.staffrecord", primary_key=True, serialize=False,
                    related_name="mobile_profile", on_delete=django.db.models.deletion.CASCADE)),
                ("presentation", models.CharField(max_length=280, blank=True, default="")),
                ("photo_data", models.BinaryField(null=True, blank=True)),
                ("photo_content_type", models.CharField(max_length=30, blank=True, default="")),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.RunPython(private_table, migrations.RunPython.noop),
    ]
