import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0014_platform_administration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="admissionapplication", name="route",
            field=models.CharField(choices=[("direct", "Inscription directe"), ("concours", "Concours ou test"), ("orientation", "Affectation ou orientation")],
                                   default="direct", max_length=16),
        ),
        migrations.AddField(
            model_name="admissionapplication", name="origin_school",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="admissionapplication", name="route_reference",
            field=models.CharField(blank=True, max_length=140),
        ),
        migrations.AddField(
            model_name="admissionapplication", name="orientation_authority",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="admissionapplication", name="external_result",
            field=models.CharField(choices=[("pending", "À vérifier"), ("eligible", "Éligible"), ("ineligible", "Non éligible")],
                                   default="pending", max_length=16),
        ),
        migrations.AddField(
            model_name="admissionapplication", name="required_documents",
            field=models.JSONField(default=list, blank=True),
        ),
        migrations.CreateModel(
            name="AdmissionPolicy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("scope_key", models.CharField(max_length=85)),
                ("enabled_routes", models.JSONField(default=list)),
                ("required_documents", models.JSONField(default=dict, blank=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("level", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                            related_name="admission_policies", to="institutions.academiclevel")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                             related_name="admission_policies", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                           related_name="admission_policies", to="institutions.academicyear")),
            ],
            options={"constraints":[models.UniqueConstraint(fields=("school", "scope_key"),
                                                             name="unique_school_admission_policy_scope")]},
        ),
        migrations.CreateModel(
            name="AdmissionDocument",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=48)),
                ("reference", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("pending", "À vérifier"), ("verified", "Vérifié"),
                                                    ("rejected", "Non conforme")], default="pending", max_length=16)),
                ("review_reason", models.CharField(blank=True, max_length=280)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                   related_name="documents", to="institutions.admissionapplication")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                  related_name="+", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="admission_documents", to="institutions.school")),
            ],
            options={"constraints":[models.UniqueConstraint(fields=("application", "code"),
                                                             name="unique_admission_document_code")]},
        ),
    ]
