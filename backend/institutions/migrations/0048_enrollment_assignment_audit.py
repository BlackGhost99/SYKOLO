"""History of class-division changes without altering existing enrollments."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("institutions", "0047_parent_school_forms_photos_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollmentevent",
            name="assignment_mode",
            field=models.CharField(max_length=16, blank=True),
        ),
        migrations.AddField(
            model_name="enrollmentevent",
            name="reason",
            field=models.CharField(max_length=300, blank=True),
        ),
    ]
