"""Integration check: YEM Django migration must not leave known tables exposed."""
from django.db import connection
from django.test import SimpleTestCase



class PublicTableRlsTests(SimpleTestCase):
    databases = {"default"}

    def test_postgres_public_yem_tables_have_rls(self):
        if connection.vendor != "postgresql":
            self.skipTest("RLS is a PostgreSQL feature.")
        with connection.cursor() as c:
            c.execute("""
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
                  AND c.relname ~ '^(institutions_|accounts_|django_|auth_)'
                  AND NOT c.relrowsecurity ORDER BY c.relname
            """)
            missing = [row[0] for row in c.fetchall()]
        self.assertEqual(missing, [], f"YEM tables missing RLS: {missing}")
