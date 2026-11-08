"""PostgreSQL guards for closed school-year data.

These triggers intentionally operate at the database boundary: API writes,
imports, payment callbacks and QuerySet.update() cannot bypass an archive.
They lock the year row while checking status, serializing in-flight writes
against the final close transaction. SQLite is used only for development;
the production close endpoint explicitly requires PostgreSQL.
"""
from django.db import migrations

# Traverse FK chains, never the shared school or permanent pupil record.
YEAR_PATHS = {
    "AcademicClass": [("year",)],
    "AcademicPeriod": [("year",)],
    "Enrollment": [("year",)],
    "EnrollmentEvent": [("enrollment", "year")],
    "StaffAssignment": [("year",)],
    "CourseOffering": [("year",)],
    "CourseUnit": [("course", "year")],
    "CourseInstructor": [("course", "year")],
    "Assessment": [("course", "year")],
    "AssessmentGrade": [("assessment", "course", "year")],
    "SchoolReport": [("year",)],
    "SchoolCouncil": [("year",)],
    "CouncilDecision": [("council", "year")],
    "ReportAmendment": [("report", "year")],
    "AttendanceSession": [("classroom", "year")],
    "AttendanceMark": [("session", "classroom", "year")],
    "AttendanceChange": [("mark", "session", "classroom", "year")],
    "FeeSchedule": [("year",)],
    "FeeCharge": [("enrollment", "year")],
    "FeePaymentBatch": [("enrollment", "year")],
    "FeePayment": [("charge", "enrollment", "year")],
    "FeePaymentVoid": [("payment", "charge", "enrollment", "year")],
    "AdmissionApplication": [("year",)],
    "AdmissionEvent": [("application", "year")],
    "AdmissionDocument": [("application", "year")],
    "AdmissionPolicy": [("year",)],
    "TimetableSlot": [("year",)],
    "TimetableEntry": [("year",)],
    "SchoolAdmissionFee": [("year",)],
    "ParentAdmissionRequest": [("application", "year")],
    "ParentPaymentAttempt": [("request", "application", "year")],
    "SingPayIntent": [
        ("charge", "enrollment", "year"),
        ("admission", "application", "year"),
    ],
    "SingPayEvent": [
        ("intent", "charge", "enrollment", "year"),
        ("intent", "admission", "application", "year"),
    ],
    "SingPaySettlement": [
        ("intent", "charge", "enrollment", "year"),
        ("intent", "admission", "application", "year"),
    ],
}


def _closed_year_query(apps, model, path, row):
    """Construct a statically mapped, safely quoted FK join to AcademicYear."""
    q = lambda value: '"' + value.replace('"', '""') + '"'
    current = model
    fragments = []
    initial_field = current._meta.get_field(path[0])
    for i, field_name in enumerate(path):
        field = current._meta.get_field(field_name)
        target = field.related_model
        alias = "y" if i == len(path) - 1 else "t" + str(i + 1)
        table = q(target._meta.db_table)
        previous = row if i == 0 else "t" + str(i)
        reference = q(field.column)
        condition = alias + "." + q(target._meta.pk.column) + " = " + previous + "." + reference
        fragments.append(("FROM " if i == 0 else "JOIN ") + table + " " + alias +
                         (" WHERE " if i == 0 else " ON ") + condition)
        current = target
    if current._meta.model_name != "academicyear":
        raise ValueError("Invalid year guard FK path: " + repr(path))
    # SQL join order is: FROM t1 WHERE ... JOIN t2 ON ..., which is invalid.
    # Build all JOINs first, and the initial WHERE last.
    segments = []
    current = model
    for i, field_name in enumerate(path):
        field = current._meta.get_field(field_name)
        target = field.related_model
        alias = "y" if i == len(path) - 1 else "t" + str(i + 1)
        parent = row if i == 0 else "t" + str(i)
        condition = alias + "." + q(target._meta.pk.column) + " = " + parent + "." + q(field.column)
        segments.append((q(target._meta.db_table), alias, condition))
        current = target
    base = "FROM " + segments[0][0] + " " + segments[0][1]
    joins = "".join(" JOIN " + name + " " + alias + " ON " + link for name, alias, link in segments[1:])
    return ("SELECT 1 " + base + joins + " WHERE " + segments[0][2] +
            " AND y.status = 'closed' FOR SHARE OF y")


def _guard_function(apps, model, paths):
    snippets = []
    for event, row in (("TG_OP <> 'INSERT'", "OLD"),
                       ("TG_OP <> 'DELETE'", "NEW")):
        checks = "\n".join(
            "        IF EXISTS (" + _closed_year_query(apps, model, path, row) +
            ") THEN RAISE EXCEPTION 'Année scolaire clôturée : écriture refusée' USING ERRCODE = '23514'; END IF;"
            for path in paths
        )
        snippets.append("    IF " + event + " THEN\n" + checks + "\n    END IF;")
    return ("CREATE FUNCTION yem_closed_" + model._meta.db_table + "() RETURNS trigger "
            "LANGUAGE plpgsql AS $year_guard$\nBEGIN\n" + "\n".join(snippets) +
            "\n    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;\n"
            "    RETURN NEW;\nEND;\n$year_guard$")


def _cash_function(apps, model, *, via_closing=False):
    q = lambda v: '"' + v.replace('"', '""') + '"'
    years = q(apps.get_model("institutions", "AcademicYear")._meta.db_table)
    closings = q(apps.get_model("institutions", "CashClosing")._meta.db_table)
    checks = []
    for event, row in (("TG_OP <> 'INSERT'", "OLD"),
                       ("TG_OP <> 'DELETE'", "NEW")):
        if via_closing:
            where = ("FROM " + closings + " c JOIN " + years +
                     " y ON y.school_id = c.school_id AND c.day BETWEEN y.start_date AND y.end_date "
                     "WHERE c.id = " + row + ".closing_id AND y.status = 'closed' FOR SHARE OF y")
        else:
            where = ("FROM " + years + " y WHERE y.school_id = " + row +
                     ".school_id AND " + row + ".day BETWEEN y.start_date AND y.end_date "
                     "AND y.status = 'closed' FOR SHARE OF y")
        checks.append("    IF " + event + " THEN\n        IF EXISTS (SELECT 1 " + where +
                      ") THEN RAISE EXCEPTION 'Année scolaire clôturée : caisse verrouillée' "
                      "USING ERRCODE = '23514'; END IF;\n    END IF;")
    return ("CREATE FUNCTION yem_closed_" + model._meta.db_table + "() RETURNS trigger "
            "LANGUAGE plpgsql AS $year_guard$\nBEGIN\n" + "\n".join(checks) +
            "\n    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;\n"
            "    RETURN NEW;\nEND;\n$year_guard$")


def install_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for model_name, paths in [*YEAR_PATHS.items(),
                                  ("CashClosing", None), ("CashTransfer", None)]:
            model = apps.get_model("institutions", model_name)
            table = model._meta.db_table
            fn = "yem_closed_" + table
            if len(fn) >= 63:
                raise ValueError("Trigger function name too long: " + fn)
            definition = (
                _guard_function(apps, model, paths) if paths is not None
                else _cash_function(apps, model, via_closing=model_name == "CashTransfer")
            )
            cursor.execute(definition)
            cursor.execute('CREATE TRIGGER yem_lock_closed_year BEFORE INSERT OR UPDATE OR DELETE ON "' +
                           table + '" FOR EACH ROW EXECUTE FUNCTION ' + fn + '()')


def remove_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for model_name in [*YEAR_PATHS, "CashClosing", "CashTransfer"]:
            table = apps.get_model("institutions", model_name)._meta.db_table
            cursor.execute('DROP TRIGGER IF EXISTS yem_lock_closed_year ON "' + table + '"')
            cursor.execute('DROP FUNCTION IF EXISTS yem_closed_' + table + '()')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0036_academic_year_lifecycle")]
    operations = [migrations.RunPython(install_guards, remove_guards)]
