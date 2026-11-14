from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institutions", "0054_existing_student_parent_requests")]

    operations = [
        migrations.AddField(
            model_name="studentguardian",
            name="whatsapp_opt_in",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="existingstudentlinkrequest",
            name="whatsapp_opt_in",
            field=models.BooleanField(default=False),
        ),
    ]
