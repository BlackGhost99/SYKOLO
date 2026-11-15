from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institutions", "0057_multicycle_periods")]
    operations = [
        migrations.AddField(
            model_name="staffprofessionaldossier",
            name="category",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
