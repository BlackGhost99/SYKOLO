from importlib import import_module

from django.db import migrations, models


PREVIOUS = import_module("institutions.migrations.0034_secondary_role_presets")
OWNER = ("proprietaire", "Propriétaire de l’établissement", (
    "school.view", "school.members.read", "school.members.write", "school.roles.read", "school.roles.manage",
    "school.audit.read",
))
DIRECTION = (
    "school.view", "school.members.read", "school.members.write", "school.roles.read", "school.roles.manage",
    "school.settings.read", "school.settings.write", "school.audit.read", "school.academic.read",
    "school.academic.manage", "school.classes.manage", "school.admissions.read", "school.admissions.manage",
    "school.admissions.decide", "school.admissions.enroll", "school.parents.manage", "school.students.read",
    "school.students.manage", "school.staff.read", "school.staff.manage", "school.organization.read",
    "school.organization.manage", "school.curriculum.read", "school.curriculum.manage",
    "school.assessments.read", "school.assessments.manage", "school.reports.read", "school.reports.manage",
    "school.reports.publish", "school.deliberations.read", "school.deliberations.manage",
    "school.deliberations.finalize", "school.reports.amend", "school.timetable.read", "school.timetable.manage",
    "school.attendance.read", "school.attendance.write", "school.attendance.finalize",
    "school.attendance.assigned", "school.finance.read", "school.finance.approve",
)
HEADS = {
    "college": ("principal", "Principal / Principale du collège", DIRECTION),
    "lycee_general": ("proviseur", "Proviseur / Proviseure du lycée", DIRECTION),
    "lycee_technique": ("proviseur", "Proviseur / Proviseure du lycée technique", DIRECTION),
}
SECRETARIAT = ("secretariat_pedagogique", "Secrétaire pédagogique", (
    "school.view", "school.academic.read", "school.students.read", "school.curriculum.read",
    "school.timetable.read", "school.assessments.read", "school.reports.read",
))
COLLEGE_SURVEILLANCE = (
    "surveillance_generale", "Surveillant général / Conseiller d’éducation", PREVIOUS.SECONDARY_ATTENDANCE_PERMISSIONS,
)


def add_appointment_roles(apps, schema_editor):
    School = apps.get_model("institutions", "School")
    Role = apps.get_model("institutions", "SchoolRole")
    database = schema_editor.connection.alias
    for school in School.objects.using(database).only("id", "school_type", "education_cycles").iterator():
        cycles = school.education_cycles or [school.school_type]
        templates = {OWNER[0]: OWNER}
        for kind, head in HEADS.items():
            if kind in cycles:
                roles = (head, SECRETARIAT, *PREVIOUS.SECONDARY_ROLE_TEMPLATES[kind])
                if kind == "college":
                    roles = (*roles, COLLEGE_SURVEILLANCE)
                templates.update({row[0]: row for row in roles})
        Role.objects.using(database).bulk_create([
            Role(school_id=school.pk, code=code, label=label, permissions=list(permissions))
            for code, label, permissions in templates.values()
        ], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("institutions", "0034_secondary_role_presets")]
    operations = [
        migrations.AddField(
            model_name="schoolmember", name="is_school_owner",
            field=models.BooleanField(default=False, db_default=False, editable=False),
        ),
        migrations.RunPython(add_appointment_roles, migrations.RunPython.noop),
    ]
