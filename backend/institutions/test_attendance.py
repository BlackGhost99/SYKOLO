"""Attendance API integration tests: scoped teachers, configurable statuses and audit."""
import json
from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .attendance_models import AttendanceSession, AttendanceMark, AttendanceChange
from .models import Organization, School, SchoolMember, SchoolRole, SchoolSetting
from .services import ROLE_TEMPLATES, key_for_scope
from .staff_models import StaffRecord, StaffAssignment
from .student_models import Student, Enrollment


class AttendanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="director-att", password="Strong attendance director test 2026")
        self.secretary = User.objects.create_user(username="secretary-att", password="Strong attendance secretary test 2026")
        self.teacher = User.objects.create_user(username="teacher-att", password="Strong attendance teacher test 2026")
        self.unassigned = User.objects.create_user(username="other-teacher-att", password="Strong attendance test 2026")
        self.stranger = User.objects.create_user(username="stranger-att", password="Strong attendance stranger test 2026")
        org = Organization.objects.create(name="Groupe scolaire test")
        self.school = School.objects.create(organization=org, name="École principale")
        self.other_school = School.objects.create(organization=org, name="École voisine")
        for school in (self.school, self.other_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        for user, code in [
            (self.director, "direction"), (self.secretary, "secretariat"),
            (self.teacher, "enseignant"), (self.unassigned, "enseignant"),
        ]:
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=code),
            )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-27", name="Année", start_date="2026-09-01", end_date="2027-07-31",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="cm2", name="CM2")
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="cm2a", name="CM2 A",
        )
        self.other_class = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="cm2b", name="CM2 B",
        )
        self.staff = StaffRecord.objects.create(
            school=self.school, staff_code="T1", first_name="Paul", last_name="Test",
            account=self.teacher, position="enseignant",
        )
        StaffAssignment.objects.create(
            school=self.school, staff=self.staff, year=self.year,
            classroom=self.classroom, duty="enseignant",
        )
        self.enrollments = []
        for i in range(2):
            student = Student.objects.create(
                school=self.school, student_code=f"ATT-{i}",
                first_name=f"Eleve{i}", last_name="Test",
            )
            enrollment = Enrollment.objects.create(
                school=self.school, student=student, year=self.year,
                classroom=self.classroom, enrolled_on="2026-09-10",
            )
            self.enrollments.append(enrollment)
        student = Student.objects.create(
            school=self.school, student_code="ATT-EXT", first_name="Autre", last_name="Classe",
        )
        self.foreign_enrollment = Enrollment.objects.create(
            school=self.school, student=student, year=self.year,
            classroom=self.other_class, enrolled_on="2026-09-10",
        )
        SchoolSetting.objects.create(
            school=self.school, scope_key=key_for_scope({}), scope={},
            values={"attendance": {"statuses": [
                {"code": "p", "label": "Présent", "group": "present"},
                {"code": "a", "label": "Absent", "group": "absent"},
                {"code": "r", "label": "Retard", "group": "late"},
                {"code": "sp", "label": "Sortie permise", "group": "other"},
            ]}},
        )
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base = f"/api/v1/schools/{self.school.pk}/attendance/"

    def login(self, user):
        self.client.force_login(user)
        self.token = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, path, data):
        return self.client.post(
            self.base + path, data=json.dumps(data), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )

    def create_session(self, classroom=None, attendance_date="2026-10-13", slot="matin"):
        result = self.post("sessions", {
            "classroom": str((classroom or self.classroom).pk),
            "date": attendance_date, "slot": slot, "label": "Appel de début de cours",
        })
        self.assertEqual(result.status_code, 201, result.content.decode())
        return result.json()

    def mark(self, enrollment, status, revision=0, reason="", note="", justification="", justified=False):
        return {
            "enrollment": str(enrollment.pk), "status": status,
            "note": note, "justification": justification, "justified": justified,
            "revision": revision, "reason": reason,
        }

    def test_bulk_attendance_justification_history_and_closure(self):
        session = self.create_session()
        path = f"sessions/{session['id']}"
        self.assertEqual(self.client.get(self.base + "options?classroom=" + str(self.classroom.pk)).status_code, 200)
        roster = self.client.get(self.base + path).json()["roster"]
        self.assertEqual(len(roster), 2)
        self.assertTrue(all(item["mark"] is None for item in roster))
        created = self.post(path + "/marks", {"marks": [
            self.mark(self.enrollments[0], "p"),
            self.mark(self.enrollments[1], "a", note="Non signalée"),
        ]})
        self.assertEqual(created.status_code, 200, created.content.decode())
        self.assertEqual([m["revision"] for m in created.json()["marks"]], [1, 1])
        self.assertEqual(self.post(path + "/close", {"revision": 1}).status_code, 409)
        self.assertEqual(self.post(path + "/close", {"revision": 2}).status_code, 200)
        self.assertEqual(self.post(path + "/marks", {
            "marks": [self.mark(self.enrollments[0], "a", revision=1, reason="Modification")],
        }).status_code, 409)
        self.assertEqual(AttendanceMark.objects.count(), 2)
        self.assertEqual(AttendanceChange.objects.count(), 2)

    def test_corrected_absence_and_justification_no_loss(self):
        session = self.create_session()
        path = f"sessions/{session['id']}"
        first = self.post(path + "/marks", {
            "marks": [self.mark(self.enrollments[0], "a")],
        })
        self.assertEqual(first.status_code, 200, first.content.decode())
        missing_reason = self.post(path + "/marks", {
            "marks": [self.mark(self.enrollments[0], "r", revision=1)],
        })
        self.assertEqual(missing_reason.status_code, 422)
        corrected = self.post(path + "/marks", {
            "marks": [self.mark(self.enrollments[0], "a", revision=1,
                                reason="Justificatif apporté et validé par la direction.",
                                justification="Déclaration parentale", justified=True)],
        })
        self.assertEqual(corrected.status_code, 200, corrected.content.decode())
        self.assertTrue(corrected.json()["marks"][0]["justified"])
        hist = self.client.get(self.base + path + "/marks/" + str(self.enrollments[0].pk) + "/history")
        self.assertEqual(hist.status_code, 200)
        self.assertEqual([h["revision"] for h in hist.json()["history"]], [1, 2])
        self.assertIsNone(hist.json()["history"][0]["before"])
        self.assertFalse(hist.json()["history"][1]["before"]["justified"])
        self.assertEqual(hist.json()["history"][1]["after"]["justification"], "Déclaration parentale")
        summary = self.client.get(self.base + "summary?classroom=" + str(self.classroom.pk)
                                  + "&from=2026-10-01&to=2026-10-31")
        self.assertEqual(summary.status_code, 200, summary.content.decode())
        self.assertEqual(summary.json()["groups"]["absent"], 1)
        self.assertEqual(summary.json()["recorded"], 1)
        self.assertEqual(summary.json()["sessions"], 1)

    def test_teacher_only_assigned_class_and_cannot_validate_excuse_or_close(self):
        self.login(self.teacher)
        session = self.create_session()
        path = f"sessions/{session['id']}"
        self.assertEqual(self.client.get(self.base + path).status_code, 200)
        self.assertEqual(self.post(path + "/marks", {"marks": [
            self.mark(self.enrollments[0], "a", justified=True, justification="Lettre parentale"),
        ]}).status_code, 422)
        self.assertEqual(self.post(path + "/marks", {"marks": [
            self.mark(self.enrollments[0], "a", justification="Déclaration parentale"),
        ]}).status_code, 200)
        self.assertEqual(self.post(path + "/close", {"revision": 2}).status_code, 403)
        self.assertEqual(self.post("sessions", {
            "classroom": str(self.other_class.pk), "date": "2026-10-13",
            "slot": "m", "label": "Autre classe",
        }).status_code, 403)
        self.assertEqual(self.client.get(self.base + "options?classroom=" + str(self.other_class.pk)).status_code, 403)
        self.login(self.unassigned)
        self.assertEqual(self.client.get(self.base + path).status_code, 403)
        self.assertEqual(self.client.get(self.base + "sessions?classroom=" + str(self.classroom.pk)).status_code, 403)

    def test_missing_catalog_date_scope_foreign_enrollment_duplicate_and_atomicity(self):
        session = self.create_session()
        self.assertEqual(self.post("sessions", {
            "classroom": str(self.classroom.pk), "date": "2026-10-13",
            "slot": "matin", "label": "Doublon",
        }).status_code, 422)
        self.assertEqual(self.post("sessions", {
            "classroom": str(self.classroom.pk), "date": "2029-01-01",
            "slot": "fin", "label": "Hors année",
        }).status_code, 422)
        path = f"sessions/{session['id']}"
        bad = self.post(path + "/marks", {"marks": [
            self.mark(self.enrollments[0], "p"),
            self.mark(self.foreign_enrollment, "a"),
        ]})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(AttendanceMark.objects.count(), 0)
        self.assertEqual(self.post(path + "/marks", {"marks": [
            self.mark(self.enrollments[0], "inconnu"),
        ]}).status_code, 422)
        self.assertEqual(self.post(path + "/close", {"revision": 1}).status_code, 422)
        SchoolSetting.objects.filter(school=self.school).update(values={})
        self.assertEqual(self.post("sessions", {
            "classroom": str(self.classroom.pk), "date": "2026-10-14",
            "slot": "matin", "label": "Catalogue absent",
        }).status_code, 422)

    def test_tenant_isolation_permissions_csrf_anonymous_and_no_delete(self):
        session = self.create_session()
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base + "sessions/" + session["id"]).status_code, 404)
        self.assertEqual(self.client.get(self.base + "summary?classroom=" + str(self.classroom.pk)
                                         + "&from=2026-10-01&to=2026-10-31").status_code, 404)
        self.login(self.director)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other_school.pk}/attendance/sessions/"
                                         + session["id"]).status_code, 404)
        self.assertEqual(self.client.post(self.base + "sessions", json.dumps({
            "classroom": str(self.classroom.pk), "date": "2026-10-14",
            "slot": "test", "label": "Sans CSRF",
        }), content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(self.base + "sessions/" + session["id"]).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "sessions/" + session["id"]).status_code, 401)
