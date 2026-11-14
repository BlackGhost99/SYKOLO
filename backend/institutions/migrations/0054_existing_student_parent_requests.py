"""Demandes de rattachement d'eleves existants, stockage prive (YEM)."""
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def private_requests(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE "public"."institutions_existingstudentlinkrequest" ENABLE ROW LEVEL SECURITY')
        cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
        for (role,) in cursor.fetchall():
            cursor.execute(
                f'REVOKE ALL PRIVILEGES ON TABLE "public"."institutions_existingstudentlinkrequest" FROM "{role}"'
            )


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0053_school_branding"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ExistingStudentLinkRequest",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("first_name", models.CharField(max_length=120)),
                ("last_name", models.CharField(max_length=120)),
                ("student_code", models.CharField(max_length=50, blank=True)),
                ("guardian_name", models.CharField(max_length=180)),
                ("contact_phone", models.CharField(max_length=45, blank=True)),
                ("status", models.CharField(max_length=12, default="pending", db_index=True, choices=[
                    ("pending", "En attente"), ("approved", "Validée"), ("rejected", "Refusée"),
                    ("cancelled", "Annulée"),
                ])),
                ("reviewed_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("linked_guardian", models.ForeignKey(
                    to="institutions.studentguardian", null=True, blank=True,
                    on_delete=django.db.models.deletion.PROTECT, related_name="+",
                )),
                ("owner", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT,
                    related_name="existing_student_requests",
                )),
                ("reviewed_by", models.ForeignKey(
                    to=settings.AUTH_USER_MODEL, null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL, related_name="+",
                )),
                ("school", models.ForeignKey(
                    to="institutions.school", on_delete=django.db.models.deletion.PROTECT,
                    related_name="existing_parent_requests",
                )),
            ],
            options={"indexes": [
                models.Index(fields=["school", "status", "created_at"], name="yem_link_req_school_idx"),
                models.Index(fields=["owner", "created_at"], name="yem_link_req_owner_idx"),
            ]},
        ),
        migrations.RunPython(private_requests, migrations.RunPython.noop),
    ]
