"""M2.7: division assignment, seat locks, audit and school isolation."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicTrack, AcademicYear
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .student_models import Enrollment, EnrollmentEvent, Student


class ClassAssignmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="m27-direction", password="M27 secure test 2026!")
        self.teacher = User.objects.create_user(username="m27-teacher", password="M27 secure test 2026!")
        self.outsider = User.objects.create_user(username="m27-outsider", password="M27 secure test 2026!")
        org = Organization.objects.create(name="Groupe test M2.7")
        self.school = School.objects.create(organization=org, name="École divisions")
        self.other_school = School.objects.create(organization=org, name="École étrangère")
        for school in (self.school, self.other_school):
            for code, label, rights in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=rights)
        for user, role in ((self.director, "direction"), (self.teacher, "enseignant")):
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=role),
            )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date="2026-09-01", end_date="2027-07-31",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="college", name="Collège")
        self.level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="six", name="Sixième")
        higher = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="cinq", name="Cinquième")
        self.track = AcademicTrack.objects.create(school=self.school, level=self.level, code="serie-s", name="S")
        self.a = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level, code="6a", name="Sixième A", capacity=1,
        )
        self.b = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level, code="6b", name="Sixième B", capacity=2,
        )
        self.c = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level, code="6c", name="Sixième C", capacity=3,
        )
        self.wrong_level = AcademicClass.objects.create(
            school=self.school, year=self.year, level=higher, code="5a", name="Cinquième A",
        )
        self.wrong_track = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level, track=self.track,
            code="6s", name="Sixième S",
        )
        self.student = Student.objects.create(school=self.school, first_name="Ada", last_name="Fictive")
        self.enrollment = Enrollment.objects.create(
            school=self.school, student=self.student, year=self.year, classroom=self.a,
            enrolled_on="2026-09-20",
        )
        self.url = f"/api/v1/schools/{self.school.pk}/enrollments/{self.enrollment.pk}/assignment"
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.director)

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def move(self, target=None, *, revision=1, mode="manual", reason="Répartition pédagogique"):
        data = {"revision": revision, "mode": mode, "reason": reason}
        if target is not None:
            data["classroom"] = str(target.pk)
        return self.client.post(
            self.url, data=json.dumps(data), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_manual_change_keeps_student_enrollment_and_audit(self):
        before_student = self.student.matricule_yem
        options = self.client.get(self.url)
        self.assertEqual(options.status_code, 200)
        self.assertEqual({x["name"] for x in options.json()["divisions"]},
                         {"Sixième B", "Sixième C"})
        self.assertEqual(options.json()["divisions"][0]["occupied"], 0)
        changed = self.move(self.b)
        self.assertEqual(changed.status_code, 200, changed.content.decode())
        self.assertEqual(changed.json()["assignment"]["class_name"], "Sixième B")
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.pk, self.enrollment.pk)
        self.assertEqual(self.enrollment.revision, 2)
        self.assertEqual(self.enrollment.classroom_id, self.b.pk)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Student.objects.get(pk=self.student.pk).matricule_yem, before_student)
        event = EnrollmentEvent.objects.get(enrollment=self.enrollment)
        self.assertEqual(event.previous_class_id, self.a.pk)
        self.assertEqual(event.new_class_id, self.b.pk)
        self.assertEqual(event.actor_id, self.director.pk)
        self.assertEqual(event.reason, "Répartition pédagogique")
        self.assertEqual(event.assignment_mode, "manual")
        self.assertTrue(SchoolAudit.objects.filter(
            school=self.school, event="class_assignment_changed",
        ).exists())
        history = self.client.get(
            f"/api/v1/schools/{self.school.pk}/enrollments/{self.enrollment.pk}/history"
        ).json()["history"][0]
        self.assertEqual(history["reason"], "Répartition pédagogique")
        self.assertEqual(history["assignment_mode"], "manual")
        self.assertEqual(history["actor"], str(self.director.pk))
        self.assertEqual(self.move(self.c, revision=1).status_code, 409)
        self.assertEqual(EnrollmentEvent.objects.count(), 1)

    def test_automatic_balances_open_divisions_deterministically(self):
        student2 = Student.objects.create(school=self.school, first_name="Bob", last_name="Exemple")
        Enrollment.objects.create(
            school=self.school, student=student2, year=self.year, classroom=self.b,
            enrolled_on="2026-09-21",
        )
        result = self.move(mode="automatic", reason="Équilibrage des groupes")
        self.assertEqual(result.status_code, 200, result.content.decode())
        self.assertEqual(result.json()["assignment"]["to_class"], str(self.c.pk))
        self.assertEqual(result.json()["assignment"]["mode"], "automatic")
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.classroom_id, self.c.pk)

    def test_full_division_cannot_be_forced(self):
        for first in ("Bob", "Claire"):
            student = Student.objects.create(school=self.school, first_name=first, last_name="Exemple")
            Enrollment.objects.create(
                school=self.school, student=student, year=self.year, classroom=self.b,
                enrolled_on="2026-09-21",
            )
        self.assertEqual(self.move(self.b).status_code, 409)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.classroom_id, self.a.pk)
        self.assertFalse(EnrollmentEvent.objects.exists())
        self.assertEqual(self.move(self.c).status_code, 200)

    def test_archived_wrong_level_and_track_are_ineligible(self):
        self.assertEqual(self.move(self.wrong_level).status_code, 422)
        self.assertEqual(self.move(self.wrong_track).status_code, 422)
        self.b.active = False
        self.b.save(update_fields=["active"])
        options = self.client.get(self.url).json()["divisions"]
        self.assertNotIn(str(self.b.pk), [d["id"] for d in options])
        self.assertEqual(self.move(self.b).status_code, 422)
        self.assertEqual(self.move(self.a).status_code, 422)
        self.assertEqual(self.move(self.c).status_code, 200)

    def test_closed_year_and_inactive_enrollment_are_read_only(self):
        self.year.status = AcademicYear.STATUS_CLOSED
        self.year.save(update_fields=["status"])
        result = self.client.get(self.url)
        self.assertTrue(result.json()["read_only"])
        self.assertEqual(result.json()["divisions"], [])
        self.assertEqual(self.move(self.b).status_code, 409)
        self.year.status = AcademicYear.STATUS_PREPARATION
        self.year.save(update_fields=["status"])
        self.enrollment.active = False
        self.enrollment.save(update_fields=["active"])
        self.assertEqual(self.move(self.b).status_code, 409)

    def test_stale_revision_bad_reason_and_no_alternate_division(self):
        self.assertEqual(self.move(self.b, revision=3).status_code, 409)
        self.assertEqual(self.move(self.b, reason="").status_code, 422)
        self.assertEqual(self.move(self.b, reason="ok").status_code, 422)
        self.assertEqual(self.move(self.b, mode="automatic").status_code, 422)
        self.b.active = False
        self.c.active = False
        self.b.save(update_fields=["active"])
        self.c.save(update_fields=["active"])
        self.assertEqual(self.move(mode="automatic").status_code, 409)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_teacher_and_unrelated_user_cannot_assign_or_read_options(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.move(self.b).status_code, 403)
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.move(self.b).status_code, 404)
        self.login(self.director)
        unrelated = self.url.replace(str(self.school.pk), str(self.other_school.pk))
        self.assertEqual(self.client.get(unrelated).status_code, 404)
        self.assertEqual(EnrollmentEvent.objects.count(), 0)

    def test_legacy_patch_cannot_bypass_series_rules(self):
        path = self.url.removesuffix("/assignment")
        result = self.client.patch(
            path, data=json.dumps({"revision": 1, "classroom": str(self.wrong_track.pk)}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(result.status_code, 422, result.content.decode())
        result = self.client.patch(
            path, data=json.dumps({"revision": 1, "classroom": str(self.b.pk)}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(result.status_code, 200, result.content.decode())
        event = EnrollmentEvent.objects.get()
        self.assertEqual(event.assignment_mode, "legacy")
        self.assertTrue(event.reason)
