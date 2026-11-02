import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def grant(apps, schema_editor):
    Role=apps.get_model("institutions","SchoolRole")
    mapping={
        "direction":["school.staff.read","school.staff.manage"],
        "secretariat":["school.staff.read","school.staff.manage"],
    }
    for role in Role.objects.filter(code__in=mapping,revision=1).iterator():
        missing=[permission for permission in mapping[role.code] if permission not in role.permissions]
        if missing:
            role.permissions=list(role.permissions)+missing
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):
    dependencies=[("institutions","0003_students_enrollment"),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[
        migrations.CreateModel(
            name="StaffRecord",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,primary_key=True,serialize=False,editable=False)),
                ("staff_code",models.SlugField(max_length=50)),
                ("first_name",models.CharField(max_length=120)),
                ("last_name",models.CharField(max_length=120)),
                ("position",models.CharField(max_length=100)),
                ("hired_on",models.DateField(null=True,blank=True)),
                ("active",models.BooleanField(default=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_records",to="institutions.school")),
                ("account",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,null=True,blank=True,related_name="staff_records",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="StaffAssignment",
            fields=[
                ("id",models.UUIDField(default=uuid.uuid4,primary_key=True,serialize=False,editable=False)),
                ("duty",models.SlugField(default="enseignant",max_length=50)),
                ("active",models.BooleanField(default=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_assignments",to="institutions.school")),
                ("staff",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="assignments",to="institutions.staffrecord")),
                ("year",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_assignments",to="institutions.academicyear")),
                ("classroom",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_assignments",to="institutions.academicclass")),
            ],
        ),
        migrations.AddConstraint("staffrecord",models.UniqueConstraint(fields=("school","staff_code"),name="unique_school_staff_code")),
        migrations.AddConstraint("staffrecord",models.UniqueConstraint(fields=("school","account"),name="unique_school_staff_account")),
        migrations.AddConstraint("staffassignment",models.UniqueConstraint(fields=("school","staff","year","classroom","duty"),name="unique_staff_assignment")),
        migrations.RunPython(grant,migrations.RunPython.noop),
    ]
