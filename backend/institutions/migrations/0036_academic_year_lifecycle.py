"""Introduce a single running year per school without discarding legacy cohorts.

Old active=False years were explicitly archived; they become 'closed'.
Among previously active years, choose one running year per school. Other
years stay in 'preparation' pending manual review, rather than silently
declaring historical data closed.
"""
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def migrate_years(apps, schema_editor):
    AcademicYear = apps.get_model("institutions", "AcademicYear")
    db = schema_editor.connection.alias
    today = timezone.localdate()
    school_ids = (AcademicYear.objects.using(db).order_by()
                  .values_list("school_id", flat=True).distinct())
    for school_id in school_ids.iterator():
        years = list(AcademicYear.objects.using(db).filter(school_id=school_id)
                     .order_by("-start_date", "-pk"))
        for year in years:
            if not year.active:
                AcademicYear.objects.using(db).filter(pk=year.pk).update(status="closed")
        candidates = [year for year in years if year.active]
        if not candidates:
            continue
        current = next((year for year in candidates
                        if year.start_date <= today <= year.end_date), candidates[0])
        AcademicYear.objects.using(db).filter(pk=current.pk).update(status="current")


class Migration(migrations.Migration):
    dependencies = [("institutions", "0035_platform_school_appointments")]

    operations = [
        migrations.AddField(
            model_name="academicyear",
            name="status",
            field=models.CharField(
                choices=[
                    ("preparation", "En préparation"),
                    ("current", "En cours"),
                    ("closed", "Clôturée"),
                ],
                default="preparation", max_length=16,
            ),
        ),
        migrations.RunPython(migrate_years, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="academicyear",
            constraint=models.UniqueConstraint(
                fields=["school"], condition=Q(status="current"),
                name="unique_current_academic_year_per_school",
            ),
        ),
    ]
