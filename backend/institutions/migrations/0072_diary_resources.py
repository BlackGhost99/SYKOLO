import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def protect_resources(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as c:
        c.execute("ALTER TABLE public.institutions_diaryresource ENABLE ROW LEVEL SECURITY")
        c.execute("REVOKE ALL ON TABLE public.institutions_diaryresource FROM PUBLIC")
        for role in ("anon", "authenticated"):
            c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [role])
            if c.fetchone():
                c.execute(f'REVOKE ALL ON TABLE public.institutions_diaryresource FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0071_teaching_diary"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="DiaryResource",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("filename", models.CharField(max_length=160)),
                ("content_type", models.CharField(max_length=40)),
                ("size", models.PositiveIntegerField()),
                ("digest", models.CharField(max_length=64)),
                ("data", models.BinaryField()),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="resources", to="institutions.teachingdiaryentry")),
                ("uploader", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints":[models.CheckConstraint(condition=models.Q(size__gte=1, size__lte=1048576), name="yem_resource_size_bound")]},
        ),
        migrations.RunPython(protect_resources, migrations.RunPython.noop),
    ]
