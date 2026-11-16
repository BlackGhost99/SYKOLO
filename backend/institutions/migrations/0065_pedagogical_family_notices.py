from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("institutions", "0064_parent_push_delivery")]
    operations = [
        migrations.AddField(model_name="schoolfamilynotification", name="student",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="institutions.student")),
        migrations.AddField(model_name="schoolfamilynotification", name="event_key",
            field=models.CharField(blank=True, default="", max_length=120)),
        migrations.AddConstraint(model_name="schoolfamilynotification",
            constraint=models.UniqueConstraint(fields=("school","parent","event_key"), condition=~models.Q(event_key=""), name="unique_family_notice_event")),
    ]
