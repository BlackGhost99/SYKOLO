import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations,models
import django.db.models.deletion


def grant(apps,schema_editor):
    Role=apps.get_model("institutions","SchoolRole")
    for role in Role.objects.filter(code="direction",revision=1).iterator():
        missing=[p for p in ("school.assessments.read","school.assessments.manage") if p not in role.permissions]
        if missing:
            role.permissions=list(role.permissions)+missing
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies=[("institutions","0005_curriculum"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(
            name="Assessment",
            fields=[
                ("id",models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
                ("name",models.CharField(max_length=180)),
                ("kind",models.SlugField(max_length=50,default="evaluation")),
                ("assessment_date",models.DateField()),
                ("weight",models.DecimalField(max_digits=7,decimal_places=3,default=Decimal("1"))),
                ("policy_snapshot",models.JSONField()),
                ("policy_layers",models.JSONField(default=list)),
                ("active",models.BooleanField(default=True)),
                ("published",models.BooleanField(default=False)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="assessments",to="institutions.school")),
                ("course",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="assessments",to="institutions.courseoffering")),
                ("period",models.ForeignKey(null=True,blank=True,on_delete=django.db.models.deletion.PROTECT,related_name="assessments",to="institutions.academicperiod")),
            ],
        ),
        migrations.CreateModel(
            name="AssessmentGrade",
            fields=[
                ("id",models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
                ("score",models.JSONField(null=True,blank=True)),
                ("feedback",models.CharField(max_length=500,blank=True)),
                ("status",models.CharField(max_length=24,default="empty")),
                ("percent",models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)),
                ("label",models.CharField(max_length=120,blank=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("updated_at",models.DateTimeField(auto_now=True)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="grades",to="institutions.school")),
                ("assessment",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="grades",to="institutions.assessment")),
                ("enrollment",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="grades",to="institutions.enrollment")),
                ("author",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="grades_entered",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint("assessmentgrade",models.UniqueConstraint(fields=("assessment","enrollment"),name="unique_grade_by_assessment_enrollment")),
        migrations.RunPython(grant,migrations.RunPython.noop),
    ]
