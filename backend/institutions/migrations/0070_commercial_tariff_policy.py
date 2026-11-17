from django.db import migrations, models

def protect_policy(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE public."institutions_platformsubscriptionpolicy" ENABLE ROW LEVEL SECURITY')
        cursor.execute('REVOKE ALL ON TABLE public."institutions_platformsubscriptionpolicy" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            if cursor.fetchone():
                cursor.execute(f'REVOKE ALL ON TABLE public."institutions_platformsubscriptionpolicy" FROM "{role}"')

class Migration(migrations.Migration):
    dependencies = [("institutions", "0068_staff_professional_category")]

    operations = [
        migrations.AddField(model_name="platformsubscription", name="commercial_terms",
                            field=models.JSONField(blank=True, default=dict)),
        migrations.CreateModel(
            name="PlatformSubscriptionPolicy",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("rates", models.JSONField(default=dict)),
                ("minimums", models.JSONField(default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"constraints":[models.CheckConstraint(condition=models.Q(id=1), name="singleton_yem_subscription_policy")]},
        ),
        migrations.RunPython(protect_policy, migrations.RunPython.noop),
    ]
