"""Cycle access scope for staff accounts; preserve all existing memberships."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("institutions", "0029_harden_supabase_rls")]

    operations = [
        migrations.AddField(
            model_name="schoolmember",
            name="access_cycle_ids",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
