from django.db import migrations


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in (
            "institutions_historicalfinancialmigration",
            "institutions_historicalfinancialmigrationentry",
            "institutions_historicalfeeadjustment",
        ):
            cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
            for role in ("anon", "authenticated"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
                if cursor.fetchone():
                    cursor.execute(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0078_historical_financial_migration")]
    operations = [migrations.RunPython(protect, migrations.RunPython.noop)]
