import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def protect_commercial_records(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in ("institutions_platformsubscription", "institutions_platformsubscriptionpayment"):
            cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
                if cursor.fetchone():
                    cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0066_parent_push_lease"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="PlatformSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lines", models.JSONField()),
                ("total_xaf", models.PositiveBigIntegerField()),
                ("issued_at", models.DateTimeField(auto_now_add=True)),
                ("issued_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("year", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="platform_subscription", to="institutions.academicyear")),
            ],
        ),
        migrations.CreateModel(
            name="PlatformSubscriptionPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=100)),
                ("amount_xaf", models.PositiveBigIntegerField()),
                ("method", models.CharField(max_length=24)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("recorded_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("void_reason", models.CharField(blank=True, max_length=240)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to="institutions.platformsubscription")),
            ],
        ),
        migrations.AddConstraint(model_name="platformsubscriptionpayment", constraint=models.UniqueConstraint(fields=("subscription", "reference"), name="unique_yem_subscription_payment_ref")),
        migrations.AddConstraint(model_name="platformsubscriptionpayment", constraint=models.CheckConstraint(condition=models.Q(amount_xaf__gt=0), name="positive_yem_subscription_payment")),
        migrations.RunPython(protect_commercial_records, migrations.RunPython.noop),
    ]
