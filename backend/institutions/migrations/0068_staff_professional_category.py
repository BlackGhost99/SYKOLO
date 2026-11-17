from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institutions", "0067_platform_subscriptions")]
    operations = [
        migrations.AddField(
            model_name="staffprofessionaldossier",
            name="category",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
