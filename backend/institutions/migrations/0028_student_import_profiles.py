"""Additive import metadata, no student data change."""
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0027_singpay_settlement_evidence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentImportProfile",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("name", models.CharField(max_length=80)),
                ("headers", models.JSONField(default=list)),
                ("mapping", models.JSONField(default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_import_profiles", to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="StudentImportBatch",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("fingerprint", models.CharField(max_length=64)),
                ("row_count", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_import_batches", to="institutions.school")),
                ("imported_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="studentimportprofile",
            constraint=models.UniqueConstraint(fields=("school", "name"), name="unique_school_import_profile"),
        ),
        migrations.AddConstraint(
            model_name="studentimportbatch",
            constraint=models.UniqueConstraint(fields=("school", "fingerprint"), name="unique_school_import_fingerprint"),
        ),
    ]
