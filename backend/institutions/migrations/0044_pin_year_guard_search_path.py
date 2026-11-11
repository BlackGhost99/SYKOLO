"""M0: pin PostgreSQL search_path for YEM's immutable-year trigger guards.

The 39 legacy trigger functions use unqualified Django tables in the public
schema, so an empty search path would break their existing bodies. Pinning
pg_catalog, public, pg_temp preserves those queries while eliminating reliance
on the caller's (mutable) search_path.

This intentionally does NOT change security-invoker mode or grant privileges.
"""
from django.db import migrations


def pin_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT p.proname
              FROM pg_catalog.pg_proc p
              JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public'
               AND p.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype
               AND p.pronargs = 0
               AND (p.proname LIKE 'yem_closed_%'
                    OR p.proname = 'yem_immutable_year_closure')
             ORDER BY p.proname
        """)
        names = [name for (name,) in cursor.fetchall()]
        if not names:
            raise RuntimeError(
                "M0: missing year-closure trigger functions; do not silently skip security hardening."
            )
        for name in names:
            quoted = schema_editor.quote_name(name)
            cursor.execute(
                f'ALTER FUNCTION "public".{quoted}() '
                "SET search_path TO pg_catalog, public, pg_temp"
            )


class Migration(migrations.Migration):
    dependencies = [("institutions", "0043_school_governance_mode")]
    operations = [
        # Intentionally no reverse step: rolling back a separate model change
        # must not reintroduce a mutable function search_path.
        migrations.RunPython(pin_guards, migrations.RunPython.noop),
    ]
