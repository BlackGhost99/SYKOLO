from django.db import migrations


SECONDARY_STUDIES_PERMISSIONS = (
    "school.view", "school.academic.read", "school.curriculum.read", "school.curriculum.manage",
    "school.staff.read", "school.timetable.read", "school.timetable.manage",
    "school.assessments.read", "school.reports.read", "school.deliberations.read",
)
SECONDARY_ATTENDANCE_PERMISSIONS = (
    "school.view", "school.academic.read", "school.attendance.read", "school.attendance.write",
)
SECONDARY_SURVEILLANCE = ("surveillance", "Surveillance", (
    "school.view", "school.academic.read", "school.attendance.assigned",
))
SECONDARY_LYCEE_ROLES = (
    ("censeur_principal", "Censeur principal", (*SECONDARY_STUDIES_PERMISSIONS, "school.attendance.read")),
    ("surveillance_generale", "Surveillance générale", SECONDARY_ATTENDANCE_PERMISSIONS),
    SECONDARY_SURVEILLANCE,
)
SECONDARY_ROLE_TEMPLATES = {
    "college": (
        ("etudes", "Direction des études", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Surveillant général / Conseiller d’éducation", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        SECONDARY_SURVEILLANCE,
    ),
    "lycee_general": (
        ("etudes", "Censeur pédagogique / Direction des études", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Censeur de la vie scolaire", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        *SECONDARY_LYCEE_ROLES,
    ),
    "lycee_technique": (
        ("etudes", "Direction des études du lycée technique", SECONDARY_STUDIES_PERMISSIONS),
        ("vie_scolaire", "Direction de la vie scolaire", (
            *SECONDARY_ATTENDANCE_PERMISSIONS, "school.attendance.finalize",
        )),
        *SECONDARY_LYCEE_ROLES,
        ("chef_travaux", "Chef de travaux", (
            "school.view", "school.academic.read", "school.curriculum.read",
        )),
    ),
}



def add_secondary_roles(apps, schema_editor):
    School = apps.get_model("institutions", "School")
    SchoolRole = apps.get_model("institutions", "SchoolRole")
    database = schema_editor.connection.alias
    schools = School.objects.using(database).filter(school_type__in=SECONDARY_ROLE_TEMPLATES)
    for school in schools.only("id", "school_type").iterator():
        SchoolRole.objects.using(database).bulk_create([
            SchoolRole(school_id=school.pk, code=code, label=label, permissions=list(permissions))
            for code, label, permissions in SECONDARY_ROLE_TEMPLATES[school.school_type]
        ], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("institutions", "0033_configurable_student_numbering")]
    operations = [migrations.RunPython(add_secondary_roles, migrations.RunPython.noop)]
