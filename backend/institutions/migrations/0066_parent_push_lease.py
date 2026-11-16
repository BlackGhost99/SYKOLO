from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("institutions", "0065_pedagogical_family_notices")]
    operations = [
        migrations.AlterField(model_name="parentpushdevice", name="session",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="yem_parent_push", to="sessions.session")),
        migrations.AddField(model_name="parentpushdevice", name="auth_binding",
            field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="parentpushdevice", name="valid_until",
            field=models.DateTimeField(blank=True, null=True, db_index=True)),
    ]
