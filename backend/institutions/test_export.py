"""Bulk CSV export must respect school isolation, prevent formula execution and audit."""
import csv
import io
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Organization, School, SchoolRole, SchoolMember, SchoolAudit
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass


class StudentExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.secretary = User.objects.create_user(username="export-manager", password="Secure pass 2026")
        self.teacher = User.objects.create_user(username="export-teacher", password="Secure pass 2026")
        org = Organization.objects.create(name="Exports tests")
        self.school = School.objects.create(organization=org, name="Lycée Export")
        self.other = School.objects.create(organization=org, name="Lycée étranger")
        for school in (self.school, self.other):
            for code, label, perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=perms)
        SchoolMember.objects.create(school=self.school, user=self.secretary,
                                    role=SchoolRole.objects.get(school=self.school, code="secretariat"))
        SchoolMember.objects.create(school=self.school, user=self.teacher,
                                    role=SchoolRole.objects.get(school=self.school, code="enseignant"))
        self.student = Student.objects.create(school=self.school, student_code="EX1", last_name="=2+2",
                                              first_name="Paul", date_of_birth=date(2015, 2, 1))
        StudentGuardian.objects.create(school=self.school, student=self.student, full_name="@danger",
                                       phone="077432108", is_primary=True)
        Student.objects.create(school=self.other, student_code="FOREIGN", first_name="Secret", last_name="Autre")

    def post(self, school=None, data=None):
        return self.client.post(
            "/api/v1/schools/%s/imports/students/export" % (school or self.school.pk),
            json.dumps(data if data is not None else {}), content_type="application/json")

    def test_export_quoted_csv_and_formula_escape(self):
        self.client.force_login(self.secretary)
        response = self.post()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("attachment", response["Content-Disposition"])
        content = response.content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(content), delimiter=";"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "EX1")
        self.assertEqual(rows[1][1], "'=2+2")
        self.assertEqual(rows[1][7], "'@danger")
        self.assertNotIn("FOREIGN", content)
        self.assertTrue(SchoolAudit.objects.filter(school=self.school, event="students_exported").exists())

    def test_export_disallowed_without_permission_or_tenant_membership(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.post().status_code, 403)
        self.client.force_login(self.secretary)
        self.assertEqual(self.post(school=self.other.pk).status_code, 404)
        self.assertEqual(SchoolAudit.objects.count(), 0)

    def test_export_year_is_restricted_to_current_school(self):
        self.client.force_login(self.secretary)
        year = AcademicYear.objects.create(school=self.other, code="y", name="2026",
                                            start_date=timezone.localdate()-timedelta(days=1),
                                            end_date=timezone.localdate()+timedelta(days=200))
        self.assertEqual(self.post(data={"year":str(year.pk)}).status_code, 404)
        self.assertEqual(self.post(data={"year":"not-a-year"}).status_code, 422)
        self.assertEqual(self.post(data={"unknown":"value"}).status_code, 422)
