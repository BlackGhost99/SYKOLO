"""Defense in depth: secure YEM tables left without RLS by additive migrations.

YEM's Django server remains responsible for authorization and school isolation.
Supabase anon/authenticated have no table grants and must never receive them.
PostgreSQL table-owner connections (the Django runtime) keep existing behavior.
"""
from django.db import migrations

TABLES = (
    "institutions_cashclosing",
    "institutions_cashtransfer",
    "institutions_enrollmentformconfig",
    "institutions_feepaymentbatch",
    "institutions_permissiondelegation",
    "institutions_schoollogin",
    "institutions_schoolmember_additional_roles",
    "institutions_singpayevent",
    "institutions_singpayintent",
    "institutions_singpaymerchant",
    "institutions_singpaysettlement",
    "institutions_studentimportbatch",
    "institutions_studentimportprofile",
)


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for name in TABLES:
            # Names are a fixed, reviewed whitelist; no user input in SQL.
            cursor.execute(f'ALTER TABLE "public"."{name}" ENABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0028_student_import_profiles")]
    operations = [migrations.RunPython(enable_rls, reverse_code=migrations.RunPython.noop)]
