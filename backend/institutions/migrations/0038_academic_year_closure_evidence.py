import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def enable_closure_rls(apps, schema_editor):
    """Protect newly created closure evidence in Supabase's public schema.

    Migration 0029 secures all existing Django tables, but this table is
    created later. Ensure it is protected in the same migration transaction.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    table = apps.get_model("institutions", "AcademicYearClosure")._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE " + schema_editor.quote_name(table) +
            " ENABLE ROW LEVEL SECURITY"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0037_closed_year_guards"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicYearClosure",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("snapshot", models.JSONField()),
                ("digest_sha256", models.CharField(max_length=64)),
                ("reason", models.TextField(max_length=600)),
                ("closed_at", models.DateTimeField(auto_now_add=True)),
                ("closed_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="year_closures", to="institutions.school",
                )),
                ("year", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="closure", to="institutions.academicyear",
                )),
            ],
        ),
        migrations.RunPython(enable_closure_rls, migrations.RunPython.noop),
    ]
