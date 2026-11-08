import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0037_closed_year_guards"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicYearClosure",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("snapshot", models.JSONField()),
                ("digest_sha256", models.CharField(max_length=64)),
                ("reason", models.TextField(max_length=600)),
                ("closed_at", models.DateTimeField(auto_now_add=True)),
                ("closed_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="year_closures", to="institutions.school",
                )),
                ("year", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="closure", to="institutions.academicyear",
                )),
            ],
        ),
    ]
