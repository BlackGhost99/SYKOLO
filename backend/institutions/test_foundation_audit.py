"""Tests d'audit M0/M1 : détecter les incohérences sans modifier les données."""
import io
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from institutions.academic_models import AcademicCycle, AcademicYear
from institutions.models import Organization, School, SchoolMember, SchoolRole


class FoundationAuditTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Organisation fictive")
        self.school = School.objects.create(
            organization=org, name="Primaire fictif",
            school_type="primaire", education_cycles=["primaire"],
        )
        self.other = School.objects.create(
            organization=org, name="Autre primaire fictif",
            school_type="primaire", education_cycles=["primaire"],
        )
        self.local_role = SchoolRole.objects.create(
            school=self.school, code="direction", label="Direction",
            permissions=["school.view", "school.academic.read"],
        )
        self.foreign_role = SchoolRole.objects.create(
            school=self.other, code="direction", label="Direction",
            permissions=["school.view"],
        )
        self.cycle = AcademicCycle.objects.create(
            school=self.school, code="primaire", name="Primaire",
        )
        self.foreign_cycle = AcademicCycle.objects.create(
            school=self.other, code="primaire", name="Primaire",
        )
        self.user = get_user_model().objects.create_user(
            username="audit-fictif", password="Mot-de-passe-de-test-2026!",
        )
        self.member = SchoolMember.objects.create(
            school=self.school, user=self.user, role=self.local_role,
            access_cycle_ids=[str(self.cycle.pk)],
        )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
            status=AcademicYear.STATUS_CURRENT,
        )

    def run_audit(self):
        stdout = io.StringIO()
        call_command("audit_yem_foundations", as_json=True, stdout=stdout)
        return json.loads(stdout.getvalue())

    def run_audit_with_errors(self):
        stdout = io.StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_yem_foundations", as_json=True, stdout=stdout)
        return json.loads(stdout.getvalue())

    def test_valid_fixtures_and_no_writes(self):
        with CaptureQueriesContext(connection) as queries:
            data = self.run_audit()
        self.assertEqual(data["critical"], {})
        self.assertEqual(data["mode"], "read_only")
        self.assertEqual(data["counts"]["schools"], 2)
        writes = [
            q["sql"] for q in queries
            if q["sql"].lstrip().split(maxsplit=1)[0].upper()
            in {"INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "CREATE", "TRUNCATE"}
        ]
        self.assertEqual(writes, [])

    def test_cross_school_main_and_additional_roles_are_detected(self):
        self.member.role = self.foreign_role
        self.member.save(update_fields=["role"])
        self.member.additional_roles.add(self.foreign_role)
        data = self.run_audit_with_errors()
        self.assertEqual(data["critical"]["member_role_other_school"], 1)
        self.assertEqual(data["critical"]["additional_role_other_school"], 1)
        self.assertNotIn("audit-fictif", json.dumps(data))

    def test_scoped_member_with_foreign_cycle_is_detected(self):
        self.member.access_cycle_ids = [str(self.foreign_cycle.pk)]
        self.member.save(update_fields=["access_cycle_ids"])
        data = self.run_audit_with_errors()
        self.assertEqual(data["critical"]["invalid_active_member_cycle_scopes"], 1)

    def test_overlapping_years_are_detected_without_change(self):
        second = AcademicYear.objects.create(
            school=self.school, code="2027-2028", name="2027-2028",
            start_date=date(2027, 7, 1), end_date=date(2028, 7, 1),
            status=AcademicYear.STATUS_PREPARATION,
        )
        data = self.run_audit_with_errors()
        self.assertEqual(data["critical"]["overlapping_academic_years"], 1)
        second.refresh_from_db()
        self.assertEqual(second.status, AcademicYear.STATUS_PREPARATION)

    def test_unclassified_and_legacy_global_access_are_warnings(self):
        self.school.school_type = "non_classe"
        self.school.save(update_fields=["school_type"])
        self.member.access_cycle_ids = None
        self.member.save(update_fields=["access_cycle_ids"])
        data = self.run_audit()
        self.assertEqual(data["critical"], {})
        self.assertEqual(data["warnings"]["schools_unclassified"], 1)
        self.assertEqual(data["warnings"]["legacy_global_members_to_review"], 1)
