import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def grant(apps, schema_editor):
    Role = apps.get_model("institutions", "SchoolRole")
    mapping = {
        "direction": [
            "school.deliberations.read", "school.deliberations.manage",
            "school.deliberations.finalize", "school.reports.amend",
        ],
        "secretariat": ["school.deliberations.read"],
    }
    for role in Role.objects.filter(code__in=mapping, revision=1).iterator():
        new = [permission for permission in mapping[role.code] if permission not in role.permissions]
        if new:
            role.permissions = list(role.permissions) + new
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies = [("institutions", "0007_reports"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="SchoolCouncil",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("period_key", models.CharField(max_length=36, blank=True)),
                ("title", models.CharField(max_length=140)),
                ("meeting_date", models.DateField()),
                ("status", models.CharField(max_length=12, default="draft")),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="councils", to="institutions.school")),
                ("year", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="councils", to="institutions.academicyear")),
                ("classroom", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="councils", to="institutions.academicclass")),
                ("period", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="councils", to="institutions.academicperiod")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, to=settings.AUTH_USER_MODEL)),
                ("closed_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("closed_at", models.DateTimeField(null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="CouncilDecision",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("code", models.SlugField(max_length=48)),
                ("label", models.CharField(max_length=120)),
                ("rationale", models.TextField(max_length=1000)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="council_decisions", to="institutions.school")),
                ("council", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="decisions", to="institutions.schoolcouncil")),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="council_decisions", to="institutions.enrollment")),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="council_decisions", to="institutions.schoolreport")),
                ("decided_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ReportAmendment",
            fields=[
                ("id", models.UUIDField(primary_key=True, serialize=False, default=uuid.uuid4, editable=False)),
                ("sequence", models.PositiveIntegerField()),
                ("course_id", models.UUIDField()),
                ("previous_percent", models.CharField(max_length=32, blank=True)),
                ("corrected_percent", models.CharField(max_length=32)),
                ("reason", models.TextField(max_length=1000)),
                ("prior_snapshot", models.JSONField()),
                ("snapshot", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="report_amendments", to="institutions.school")),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="amendments", to="institutions.schoolreport")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, null=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["sequence"]},
        ),
        migrations.AddConstraint("schoolcouncil", models.UniqueConstraint(fields=("school", "classroom", "period_key"), name="unique_school_council_class_period")),
        migrations.AddConstraint("councildecision", models.UniqueConstraint(fields=("council", "enrollment"), name="unique_council_enrollment_decision")),
        migrations.AddConstraint("reportamendment", models.UniqueConstraint(fields=("report", "sequence"), name="unique_report_amendment_sequence")),
        migrations.RunPython(grant, migrations.RunPython.noop),
    ]
