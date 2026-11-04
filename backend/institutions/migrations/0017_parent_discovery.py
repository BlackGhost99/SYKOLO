import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0016_school_profiles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolPublicListing",
            fields=[
                ("school", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, primary_key=True,
                    related_name="public_listing", serialize=False, to="institutions.school")),
                ("published", models.BooleanField(default=False)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("district", models.CharField(blank=True, max_length=100)),
                ("description", models.CharField(blank=True, max_length=600)),
                ("contact_phone", models.CharField(blank=True, max_length=45)),
                ("cash_at_school", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name="FamilyChild",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("first_name", models.CharField(max_length=120)),
                ("last_name", models.CharField(max_length=120)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="family_children", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="ParentAdmissionRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("payment_choice", models.CharField(
                    choices=[("cash", "Espèces sur place")], default="cash", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("application", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="parent_request", to="institutions.admissionapplication")),
                ("child", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="admission_requests", to="institutions.familychild")),
                ("owner", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="parent_admission_requests", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
