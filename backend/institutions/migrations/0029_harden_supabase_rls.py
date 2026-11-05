"""Secure every Django/YEM public table reproducibly on fresh and existing databases.

Supabase's anon/authenticated roles have no grants to Django tables.
The Django PostgreSQL table owner retains its existing behavior. Auth and
tenant isolation are still enforced by the Django application.
"""
from django.db import migrations

# Only app-owned tables in the standard Django public schema, never Supabase
# managed internal schemas, extensions, or unrelated services.
PREFIXES = ("institutions_", "accounts_", "django_", "auth_")


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.relname
              FROM pg_class AS c
              JOIN pg_namespace AS n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
               AND NOT c.relrowsecurity
               AND c.relname ~ '^(institutions_|accounts_|django_|auth_)'
             ORDER BY c.relname
        """)
        for (name,) in cursor.fetchall():
            if not name.startswith(PREFIXES):
                raise RuntimeError("Unrecognized Django table: " + name)
            cursor.execute(f'ALTER TABLE "public".{schema_editor.quote_name(name)} ENABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0028_student_import_profiles")]
    operations = [migrations.RunPython(enable_rls, reverse_code=migrations.RunPython.noop)]
