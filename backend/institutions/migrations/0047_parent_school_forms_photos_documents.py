"""School-driven parent dossier snapshots, private child portraits and attachment evidence."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def protect_new_parent_tables(apps, schema_editor):
    """Supabase's Data API must not expose Django-owned records to anon/authenticated."""
    if schema_editor.connection.vendor != "postgresql":
        return
    tables = ("institutions_familychildphoto", "institutions_parentdocumentupload")
    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f'ALTER TABLE "public"."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')")
            roles = [row[0] for row in cursor.fetchall()]
            for role in roles:
                cursor.execute(f'REVOKE ALL PRIVILEGES ON TABLE "public"."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0046_partial_scholarships"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="familychild", name="profile",
            field=models.JSONField(default=dict, blank=True),
        ),
        migrations.AddField(
            model_name="parentadmissionrequest", name="form_revision",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="parentadmissionrequest", name="form_data",
            field=models.JSONField(default=dict, blank=True),
        ),
        migrations.AddField(
            model_name="parentadmissionrequest", name="document_requirements",
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.CreateModel(
            name="FamilyChildPhoto",
            fields=[
                ("child", models.OneToOneField(primary_key=True, serialize=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="portrait", to="institutions.familychild")),
                ("data", models.BinaryField()),
                ("content_type", models.CharField(max_length=30, default="image/jpeg")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ParentDocumentUpload",
            fields=[
                ("document", models.OneToOneField(primary_key=True, serialize=False,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="parent_upload", to="institutions.admissiondocument")),
                ("filename", models.CharField(max_length=120)),
                ("content_type", models.CharField(max_length=50)),
                ("content", models.BinaryField()),
                ("size", models.PositiveIntegerField()),
                ("uploaded_at", models.DateTimeField(auto_now=True)),
                ("uploaded_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="+",
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RunPython(protect_new_parent_tables, migrations.RunPython.noop),
    ]
