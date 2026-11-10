"""Minimal class-roster visibility after a parent admission.

The list must be useful to studies/life-school staff without granting broad
pupil, guardian, contact, finance or other-school file permissions.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES, SECONDARY_ROLE_TEMPLATES
from .staff_models import StaffRecord, StaffAssignment
from .student_models import Student, Enrollment


class ClassRosterRoleTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.school = School.objects.create(
            organization=Organization.objects.create(name="Groupe YEM test rosters"),
            name="Lycée Privé 2 (test isolé)", school_type="lycee_general",
            education_cycles=["lycee_general"],
        )
        self.other = School.objects.create(
            organization=Organization.objects.create(name="Autre groupe YEM"),
            name="École voisine",
        )
        for code, label, perms in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school, code=code, label=label, permissions=perms)
        for code, label, perms in SECONDARY_ROLE_TEMPLATES["lycee_general"]:
            SchoolRole.objects.update_or_create(school=self.school, code=code,
                defaults={"label": label, "permissions": list(perms)})
        self.users = {}
        for code in ("direction", "secretariat", "etudes", "vie_scolaire", "enseignant"):
            user = user_model.objects.create_user(username=f"roster-{code}", password="Test-mot-de-passe-2026!")
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=code),
            )
            self.users[code] = user
        self.outsider = user_model.objects.create_user("roster-outsider", password="Test outsider 2026!")
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026", name="2026-2027",
            start_date="2026-09-01", end_date="2027-07-31",
        )
        self.cycle = AcademicCycle.objects.create(school=self.school, code="lycee_general", name="Lycée général")
        level = AcademicLevel.objects.create(school=self.school, cycle=self.cycle, code="seconde", name="Seconde")
        self.classroom = AcademicClass.objects.create(school=self.school, year=self.year, level=level,
            code="seconde-s", name="Seconde S", capacity=30)
        self.other_classroom = AcademicClass.objects.create(school=self.school, year=self.year,
            level=level, code="seconde-a", name="Seconde A", capacity=30)
        pupil = Student.objects.create(school=self.school, first_name="Élève", last_name="TEST")
        Enrollment.objects.create(school=self.school, student=pupil, year=self.year,
            classroom=self.classroom, enrolled_on="2026-11-10")
        self.path = f"/api/v1/schools/{self.school.pk}/classes/{self.classroom.pk}/students"
        self.other_path = f"/api/v1/schools/{self.school.pk}/classes/{self.other_classroom.pk}/students"

    def as_role(self, role):
        self.client.force_login(self.users[role])

    def test_studies_and_life_school_see_only_name_and_matricule(self):
        for code in ("etudes", "vie_scolaire"):
            with self.subTest(role=code):
                self.as_role(code)
                response = self.client.get(self.path)
                self.assertEqual(response.status_code, 200, response.content)
                pupils = response.json()["students"]
                self.assertEqual(len(pupils), 1)
                self.assertEqual(pupils[0]["first_name"], "Élève")
                self.assertEqual(pupils[0]["last_name"], "TEST")
                self.assertEqual(set(pupils[0]), {"id", "first_name", "last_name", "student_code"})
                self.assertEqual(self.client.get(
                    f"/api/v1/schools/{self.school.pk}/students"
                ).status_code, 403)

    def test_assigned_teacher_only_his_class_and_outsider_isolation(self):
        self.as_role("enseignant")
        self.assertEqual(self.client.get(self.path).status_code, 403)
        record = StaffRecord.objects.create(
            school=self.school, account=self.users["enseignant"],
            staff_code="teach-seconde-s", first_name="Prof", last_name="Test", position="enseignant",
        )
        StaffAssignment.objects.create(school=self.school, staff=record,
            year=self.year, classroom=self.classroom, duty="enseignant")
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.assertEqual(self.client.get(self.other_path).status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/students").status_code, 403)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.as_role("direction")
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.other.pk}/classes/{self.classroom.pk}/students"
        ).status_code, 404)

    def test_restricted_cycle_account_cannot_bypass_dedicated_view(self):
        member = SchoolMember.objects.get(school=self.school, user=self.users["etudes"])
        member.access_cycle_ids = [str(self.cycle.pk)]
        member.save(update_fields=["access_cycle_ids"])
        self.as_role("etudes")
        self.assertEqual(self.client.get(self.path).status_code, 403)

    def test_secretariat_keeps_existing_roster_and_student_file_rights(self):
        self.as_role("secretariat")
        self.assertEqual(self.client.get(self.path).status_code, 200)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/students"
        ).status_code, 200)
