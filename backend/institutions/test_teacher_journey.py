"""Recette transversale : professeur -> notes/moyennes/appel -> profil -> proviseur.

Synthetic records only. No requests to real accounts, schools, or production data.
"""
import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from pedagogy.views import PRESETS
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass, AcademicPeriod
from .assessment_models import AssessmentGrade
from .attendance_models import AttendanceMark, AttendanceChange
from .curriculum_models import Subject, CourseOffering, CourseInstructor
from .models import Organization, School, SchoolMember, SchoolRole, SchoolSetting
from .services import ROLE_TEMPLATES, key_for_scope
from .staff_models import StaffRecord, StaffAssignment
from .student_models import Student, Enrollment


class TeacherCrossRoleJourneyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create_user(username="journey-teacher", password="test-private-2026-Teacher!")
        self.director = User.objects.create_user(username="journey-director", password="test-private-2026-Director!")
        self.stranger = User.objects.create_user(username="journey-unassigned", password="test-private-2026-Unassigned!")
        org = Organization.objects.create(name="Groupe scolaire recette")
        self.school = School.objects.create(organization=org, name="Lycée AWASSI (fictif)")
        self.foreign_school = School.objects.create(organization=org, name="Autre lycée (fictif)")
        for school in (self.school, self.foreign_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        for user, role in ((self.teacher, "enseignant"), (self.director, "direction")):
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=role),
            )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date="2026-09-01", end_date="2027-07-31",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="college", name="Collège")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="troisieme", name="Troisième")
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="troisieme-a", name="Troisième A",
        )
        other_class = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="troisieme-b", name="Troisième B",
        )
        period = AcademicPeriod.objects.create(
            school=self.school, year=self.year, code="t1", name="Trimestre 1",
            start_date="2026-09-01", end_date="2026-12-31",
        )
        self.period = period
        subject = Subject.objects.create(school=self.school, code="math", name="Mathématiques")
        self.course = CourseOffering.objects.create(
            school=self.school, year=self.year, classroom=self.classroom, subject=subject,
        )
        self.other_course = CourseOffering.objects.create(
            school=self.school, year=self.year, classroom=other_class, subject=subject,
        )
        self.staff = StaffRecord.objects.create(
            school=self.school, account=self.teacher, staff_code="AW-P-001",
            first_name="Paul", last_name="Nze", position="Professeur de mathématiques",
        )
        assignment = StaffAssignment.objects.create(
            school=self.school, year=self.year, classroom=self.classroom,
            staff=self.staff, duty="enseignant",
        )
        CourseInstructor.objects.create(school=self.school, course=self.course, staff_assignment=assignment)
        self.enrollments = []
        for idx, (first, last) in enumerate((("Eva", "Mba"), ("Jean", "Ondo")), 1):
            student = Student.objects.create(
                school=self.school, student_code=f"AW-26-{idx:03d}", first_name=first, last_name=last,
            )
            self.enrollments.append(Enrollment.objects.create(
                school=self.school, student=student, classroom=self.classroom,
                year=self.year, enrolled_on="2026-09-15",
            ))
        grading = deepcopy(next(p["policy"] for p in PRESETS if p["id"] == "numeric-20"))
        SchoolSetting.objects.create(
            school=self.school, scope_key=key_for_scope({}), scope={},
            values={
                "grading": grading,
                "attendance": {"statuses": [
                    {"code": "p", "label": "Présent", "group": "present"},
                    {"code": "a", "label": "Absent", "group": "absent"},
                    {"code": "r", "label": "Retard", "group": "late"},
                ]},
            },
        )
        self.client = Client(enforce_csrf_checks=True)
        self.base = f"/api/v1/schools/{self.school.pk}/"
        self.login(self.teacher)

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self, path, payload, method="post"):
        return getattr(self.client, method)(
            self.base + path, data=json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def create_assessment(self, name, weight):
        result = self.write("courses/" + str(self.course.pk) + "/assessments", {
            "name": name, "assessment_date": "2026-11-13", "kind": "devoir",
            "weight": weight, "period": str(self.period.pk),
        })
        self.assertEqual(result.status_code, 201, result.content.decode())
        return result.json()["id"]

    def mark(self, e, status, revision=0, reason=""):
        return {
            "enrollment": str(e.pk), "status": status, "note": "",
            "justification": "", "justified": False,
            "revision": revision, "reason": reason,
        }

    def test_complete_teacher_to_director_journey(self):
        courses = self.client.get(self.base + "curriculum/my-courses")
        self.assertEqual(courses.status_code, 200)
        self.assertEqual([c["id"] for c in courses.json()["courses"]], [str(self.course.pk)])
        assessment = self.create_assessment("Devoir 1", "2")
        students = self.client.get(self.base + "assessments/" + assessment + "/roster")
        self.assertEqual(students.status_code, 200)
        self.assertEqual(len(students.json()["students"]), 2)

        grade_path = "assessments/" + assessment + "/grades/batch"
        first = {"enrollment": str(self.enrollments[0].pk), "score": 18, "revision": 0}
        second = {"enrollment": str(self.enrollments[1].pk), "score": 12, "revision": 0}
        bad = self.write(grade_path, {"grades": [first, {**second, "score": 23}]})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(AssessmentGrade.objects.count(), 0)
        saved = self.write(grade_path, {"grades": [first, second]})
        self.assertEqual(saved.status_code, 200, saved.content.decode())
        self.assertEqual(saved.json()["saved"], 2)
        self.assertEqual(self.write(grade_path, {"grades": [first]}).status_code, 409)
        assessment_two = self.create_assessment("Interrogation 1", "1")
        self.assertEqual(self.write("assessments/" + assessment_two + "/grades/batch", {
            "grades": [{"enrollment": str(self.enrollments[0].pk), "score": 15, "revision": 0}],
        }).status_code, 200)

        averages = self.client.get(self.base + "courses/" + str(self.course.pk) +
                                   "/averages?period=" + str(self.period.pk))
        self.assertEqual(averages.status_code, 200)
        view = averages.json()
        self.assertTrue(view["provisional"])
        self.assertEqual(view["assessment_count"], 2)
        self.assertEqual(view["class_average_on_20"], "14.50")
        by_code = {s["student_code"]: s for s in view["students"]}
        self.assertEqual(by_code["AW-26-001"]["average_on_20"], "17.00")
        self.assertTrue(by_code["AW-26-001"]["complete"])
        self.assertEqual(by_code["AW-26-002"]["average_on_20"], "12.00")
        self.assertFalse(by_code["AW-26-002"]["complete"])
        self.assertEqual(self.client.get(self.base + "courses/" +
                                         str(self.other_course.pk) + "/averages").status_code, 404)

        attendance = self.write("attendance/sessions", {
            "classroom": str(self.classroom.pk), "date": "2026-11-13",
            "slot": "08-00", "label": "Mathématiques",
        })
        self.assertEqual(attendance.status_code, 201, attendance.content.decode())
        session = attendance.json()["id"]
        mark_path = "attendance/sessions/" + session + "/marks"
        posted = self.write(mark_path, {"marks": [
            self.mark(self.enrollments[0], "p"), self.mark(self.enrollments[1], "r"),
        ]})
        self.assertEqual(posted.status_code, 200, posted.content.decode())
        self.assertEqual(AttendanceMark.objects.count(), 2)
        self.assertEqual(self.write(mark_path, {"marks": [
            self.mark(self.enrollments[1], "a", revision=1),
        ]}).status_code, 422)
        self.assertEqual(self.write(mark_path, {"marks": [
            self.mark(self.enrollments[1], "a", revision=1, reason="Retard corrigé en absence"),
        ]}).status_code, 200)
        self.assertEqual(AttendanceChange.objects.count(), 3)
        self.assertEqual(self.write("attendance/sessions/" + session + "/close",
                                    {"revision": 3}).status_code, 403)

        self.assertEqual(self.write("staff/me/profile", {
            "revision": 1, "presentation": "Enseigne les mathématiques en Troisième A.",
        }, method="patch").status_code, 200)
        photo_path = "staff/" + str(self.staff.pk) + "/photo"
        uploaded = self.client.post(self.base + photo_path, {
            "photo": SimpleUploadedFile("prof.jpg", b"\xff\xd8\xff" + b"illustration-fictive", content_type="image/jpeg"),
        }, HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(uploaded.status_code, 200, uploaded.content.decode())
        self.assertEqual(self.client.get(self.base + photo_path).status_code, 200)

        self.login(self.director)
        directory = self.client.get(self.base + "staff")
        self.assertEqual(directory.status_code, 200)
        person = next(s for s in directory.json()["staff"] if s["staff_code"] == "AW-P-001")
        self.assertEqual(person["photo_url"], self.base + photo_path)
        self.assertIn("mathématiques", person["presentation"])
        portrait = self.client.get(self.base + photo_path)
        self.assertEqual(portrait.status_code, 200)
        self.assertIn("no-store", portrait["Cache-Control"])
        self.assertEqual(self.client.post(self.base + photo_path, {}, HTTP_X_CSRFTOKEN=self.csrf).status_code, 403)

        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base + photo_path).status_code, 404)
        self.assertEqual(self.client.get(self.base + "courses/" +
                                         str(self.course.pk) + "/averages").status_code, 404)
        self.login(self.teacher)
        foreign = f"/api/v1/schools/{self.foreign_school.pk}/staff/{self.staff.pk}/photo"
        self.assertEqual(self.client.get(foreign).status_code, 404)
