"""Integration check: YEM Django migration must not leave known tables exposed."""
from django.db import connection
from django.test import SimpleTestCase

from .migrations import __path__ as migration_path  # noqa: F401


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
                  AND (c.relname LIKE 'institutions_%'
                    OR c.relname LIKE 'accounts_%'
                    OR c.relname LIKE 'django_%'
                    OR c.relname LIKE 'auth_%')
                  AND NOT c.relrowsecurity ORDER BY c.relname
            """)
            missing = [row[0] for row in c.fetchall()]
        self.assertEqual(missing, [], f"YEM tables missing RLS: {missing}")
