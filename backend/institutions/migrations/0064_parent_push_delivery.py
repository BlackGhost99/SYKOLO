from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE public.institutions_parentpushdelivery ENABLE ROW LEVEL SECURITY")
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public.institutions_parentpushdelivery FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0063_parent_push_device")]
    operations = [
        migrations.CreateModel(
            name="ParentPushDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.CharField(default="pending", max_length=12)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_try", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("device", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="institutions.parentpushdevice")),
                ("notice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="institutions.schoolfamilynotification")),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("device", "notice"), name="unique_parent_push_delivery")],
                "indexes": [models.Index(fields=["state", "next_try"], name="yem_push_due")],
            },
        ),
        migrations.RunPython(protect, migrations.RunPython.noop),
    ]
