from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE public.institutions_parentpushdevice ENABLE ROW LEVEL SECURITY")
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public.institutions_parentpushdevice FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0062_preschool_competencies_liaison"),
        ("sessions", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ParentPushDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("encrypted_token", models.TextField()),
                ("registered_at", models.DateTimeField(auto_now_add=True)),
                ("refreshed_at", models.DateTimeField(auto_now=True)),
                ("parent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("session", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="yem_parent_push", to="sessions.session")),
            ],
        ),
        migrations.RunPython(protect, migrations.RunPython.noop),
    ]
