"""M0 regression: year-closure triggers do not inherit the caller's search_path."""
from django.db import connection
from django.test import TestCase, skipUnlessDBFeature


class YearGuardSearchPathTests(TestCase):
    @skipUnlessDBFeature("supports_transactions")
    def test_all_year_guard_functions_have_pinned_search_path(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific trigger security")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT p.proname, p.prosecdef, p.proconfig
                  FROM pg_catalog.pg_proc p
                  JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'public'
                   AND p.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype
                   AND (p.proname LIKE 'yem_closed_%'
                        OR p.proname = 'yem_immutable_year_closure')
            """)
            rows = cursor.fetchall()
        self.assertGreaterEqual(len(rows), 39)
        for name, elevated, config in rows:
            with self.subTest(name=name):
                self.assertFalse(elevated, "Trigger must remain SECURITY INVOKER")
                settings = [item for item in config or [] if item.startswith("search_path=")]
                self.assertEqual(len(settings), 1)
                self.assertEqual(
                    [schema.strip() for schema in settings[0].split("=", 1)[1].split(",")],
                    ["pg_catalog", "public", "pg_temp"],
                )
