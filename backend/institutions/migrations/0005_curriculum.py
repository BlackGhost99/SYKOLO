import uuid
from decimal import Decimal
from django.db import migrations,models
import django.db.models.deletion


def grant(apps,schema_editor):
    Role=apps.get_model("institutions","SchoolRole")
    grants={
        "direction":["school.curriculum.read","school.curriculum.manage"],
        "secretariat":["school.curriculum.read"],
        "enseignant":["school.curriculum.read"],
    }
    for role in Role.objects.filter(code__in=grants,revision=1).iterator():
        additions=[p for p in grants[role.code] if p not in role.permissions]
        if additions:
            role.permissions=list(role.permissions)+additions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies=[("institutions","0004_staff_assignments")]
    operations=[
        migrations.CreateModel(
            name="Subject",
            fields=[
                ("id",models.UUIDField(primary_key=True,serialize=False,editable=False,default=uuid.uuid4)),
                ("code",models.SlugField(max_length=50)),
                ("name",models.CharField(max_length=120)),
                ("description",models.CharField(max_length=500,blank=True)),
                ("active",models.BooleanField(default=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="subjects",to="institutions.school")),
            ],
        ),
        migrations.CreateModel(
            name="CourseOffering",
            fields=[
                ("id",models.UUIDField(primary_key=True,serialize=False,editable=False,default=uuid.uuid4)),
                ("coefficient",models.DecimalField(max_digits=7,decimal_places=3,default=Decimal("1.000"))),
                ("active",models.BooleanField(default=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="courses",to="institutions.school")),
                ("year",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="courses",to="institutions.academicyear")),
                ("classroom",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="courses",to="institutions.academicclass")),
                ("subject",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="courses",to="institutions.subject")),
            ],
        ),
        migrations.CreateModel(
            name="CourseUnit",
            fields=[
                ("id",models.UUIDField(primary_key=True,serialize=False,editable=False,default=uuid.uuid4)),
                ("code",models.SlugField(max_length=50)),
                ("title",models.CharField(max_length=180)),
                ("objectives",models.TextField(max_length=2000,blank=True)),
                ("order",models.PositiveSmallIntegerField(default=0)),
                ("active",models.BooleanField(default=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="course_units",to="institutions.school")),
                ("course",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="units",to="institutions.courseoffering")),
            ],
        ),
        migrations.CreateModel(
            name="CourseInstructor",
            fields=[
                ("id",models.UUIDField(primary_key=True,serialize=False,editable=False,default=uuid.uuid4)),
                ("active",models.BooleanField(default=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="course_instructors",to="institutions.school")),
                ("course",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="instructors",to="institutions.courseoffering")),
                ("staff_assignment",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="courses",to="institutions.staffassignment")),
            ],
        ),
        migrations.AddConstraint("subject",models.UniqueConstraint(fields=("school","code"),name="unique_school_subject")),
        migrations.AddConstraint("courseoffering",models.UniqueConstraint(fields=("school","year","classroom","subject"),name="unique_school_class_subject")),
        migrations.AddConstraint("courseunit",models.UniqueConstraint(fields=("course","code"),name="unique_course_unit_code")),
        migrations.AddConstraint("courseinstructor",models.UniqueConstraint(fields=("course","staff_assignment"),name="unique_course_staff_link")),
        migrations.RunPython(grant,migrations.RunPython.noop),
    ]
