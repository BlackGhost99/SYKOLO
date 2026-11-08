"""Protect the signed annual closure evidence from UPDATE and DELETE on PostgreSQL."""
from django.db import migrations


def protect_evidence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = apps.get_model("institutions", "AcademicYearClosure")._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            CREATE FUNCTION yem_immutable_year_closure() RETURNS trigger
            LANGUAGE plpgsql AS $year_evidence$
            BEGIN
              RAISE EXCEPTION 'Procès-verbal de clôture immuable'
                USING ERRCODE = '23514';
            END;
            $year_evidence$
        """)
        cursor.execute('CREATE TRIGGER yem_no_modify_year_closure BEFORE UPDATE OR DELETE ON "' +
                       table + '" FOR EACH ROW EXECUTE FUNCTION yem_immutable_year_closure()')


def unprotect_evidence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = apps.get_model("institutions", "AcademicYearClosure")._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP TRIGGER IF EXISTS yem_no_modify_year_closure ON "' + table + '"')
        cursor.execute("DROP FUNCTION IF EXISTS yem_immutable_year_closure()")


class Migration(migrations.Migration):
    dependencies = [("institutions", "0038_academic_year_closure_evidence")]
    operations = [migrations.RunPython(protect_evidence, unprotect_evidence)]
