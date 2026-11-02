import uuid
from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion


def grant(apps,schema_editor):
    Role=apps.get_model("institutions","SchoolRole")
    mapping={
        "direction":["school.reports.read","school.reports.manage","school.reports.publish"],
        "secretariat":["school.reports.read"],
    }
    for role in Role.objects.filter(code__in=mapping,revision=1).iterator():
        new=[p for p in mapping[role.code] if p not in role.permissions]
        if new:
            role.permissions=list(role.permissions)+new
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies=[("institutions","0006_assessments"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(
            name="SchoolReport",
            fields=[
                ("id",models.UUIDField(primary_key=True,serialize=False,default=uuid.uuid4,editable=False)),
                ("period_key",models.CharField(max_length=36,blank=True)),
                ("status",models.CharField(max_length=12,default="draft")),
                ("snapshot",models.JSONField()),
                ("revision",models.PositiveIntegerField(default=1)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("published_at",models.DateTimeField(null=True,blank=True)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="reports",to="institutions.school")),
                ("enrollment",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="reports",to="institutions.enrollment")),
                ("year",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="reports",to="institutions.academicyear")),
                ("period",models.ForeignKey(null=True,blank=True,on_delete=django.db.models.deletion.PROTECT,related_name="reports",to="institutions.academicperiod")),
                ("prepared_by",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="reports_prepared",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint("schoolreport",models.UniqueConstraint(fields=("school","enrollment","year","period_key"),name="unique_report_enrollment_period")),
        migrations.RunPython(grant,migrations.RunPython.noop),
    ]
