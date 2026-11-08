"""Parent portal: explicit verification and per-child object authorization."""
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .attendance_models import AttendanceSession, AttendanceMark
from .council_models import ReportAmendment
from .finance_models import FeeCharge, FeeSchedule, FeePayment
from .models import Organization, School, SchoolLogin, SchoolMember, SchoolRole
from .parent_models import GuardianAccountLink
from .report_models import SchoolReport
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment


class ParentPortalTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.director = U.objects.create_user(username="p15-director", password="Strong parent portal test director 2026!")
        self.secretary = U.objects.create_user(username="p15-secretary", password="Strong parent portal test secretary 2026!")
        self.parent_a = U.objects.create_user(username="p15-parent-a", password="Strong parent portal test parent 2026!")
        self.parent_b = U.objects.create_user(username="p15-parent-b", password="Strong parent portal test parent 2026!")
        self.parent_other = U.objects.create_user(username="p15-parent-other", password="Strong parent portal test parent 2026!")
        self.outsider = U.objects.create_user(username="p15-outsider", password="Strong parent portal test outsider 2026!")
        org = Organization.objects.create(name="Groupe P15")
        self.school = School.objects.create(organization=org, name="École P15")
        self.foreign_school = School.objects.create(organization=org, name="École étrangère P15")
        for school in (self.school, self.foreign_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        for user, code in ((self.director, "direction"), (self.secretary, "secretariat"),
                           (self.parent_a, "parent"), (self.parent_b, "parent")):
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=code),
            )
        SchoolMember.objects.create(
            school=self.foreign_school, user=self.parent_other,
            role=SchoolRole.objects.get(school=self.foreign_school, code="parent"),
        )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026", name="2026–2027",
            start_date="2026-09-01", end_date="2027-07-31",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="cm1", name="CM1")
        self.classroom = AcademicClass.objects.create(school=self.school, year=self.year, level=level,
                                                       code="a", name="CM1 A")
        self.students = []
        self.guardians = []
        self.enrollments = []
        for i in (1, 2):
            student = Student.objects.create(
                school=self.school, student_code=f"P15-{i}",
                first_name=f"Élève {i}", last_name="Test",
            )
            guardian = StudentGuardian.objects.create(
                school=self.school, student=student, full_name=f"Responsable {i}",
                email="contact@example.test", phone="+241 00 00 00 00", active=True,
            )
            enrollment = Enrollment.objects.create(
                school=self.school, student=student, year=self.year,
                classroom=self.classroom, enrolled_on="2026-09-14",
            )
            self.students.append(student)
            self.guardians.append(guardian)
            self.enrollments.append(enrollment)
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.root = f"/api/v1/schools/{self.school.pk}/parent-links"
        self.portal = "/api/v1/parents/children"

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self, path, data, method="post"):
        return getattr(self.client, method)(
            path, json.dumps(data), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def link(self, index=0, user=None):
        u = user or self.parent_a
        r = self.write(self.root, {"guardian": str(self.guardians[index].pk), "username": u.username})
        self.assertEqual(r.status_code, 201, r.content.decode())
        return r.json()

    def path(self, index=0, suffix=""):
        return f"{self.portal}/{self.students[index].pk}{suffix}"

    def add_published_report(self, index=0, published=True):
        student = self.students[index]
        snapshot = {
            "school": {"name": self.school.name},
            "template": {"title": "Bulletin", "show_score": True, "show_label": True},
            "student": {"last_name": student.last_name, "first_name": student.first_name,
                        "code": student.student_code},
            "class": {"name": self.classroom.name},
            "year": {"name": self.year.name},
            "period": None,
            "subjects": [{"subject": "Français", "coefficient": "1",
                          "result": {"score": "12/20", "label": "Bien"}}],
            "overall": {"status": "calculated", "score": "12/20", "label": "Bien"},
        }
        return SchoolReport.objects.create(
            school=self.school, enrollment=self.enrollments[index], year=self.year,
            period_key="", status="published" if published else "draft",
            snapshot=snapshot,
            published_at=timezone.now() if published else None,
        )

    def add_finance(self, index=0):
        schedule = FeeSchedule.objects.create(
            school=self.school, year=self.year, code=f"frais-{index}",
            label="Scolarité", amount="120000", currency="XAF",
        )
        charge = FeeCharge.objects.create(
            school=self.school, enrollment=self.enrollments[index], schedule=schedule,
            label="Scolarité", amount=Decimal("120000.00"), currency="XAF",
        )
        FeePayment.objects.create(
            school=self.school, charge=charge, amount=Decimal("20000.00"),
            currency="XAF", method="especes", reference="PRIVATE-RECEIPT-123",
            paid_on="2026-11-02", idempotency_key=uuid.uuid4(),
            recorded_by=self.director,
        )

    def add_attendance(self, index=0, closed=True):
        session = AttendanceSession.objects.create(
            school=self.school, classroom=self.classroom, attendance_date="2026-10-13",
            slot=f"matin-{index}", label="Appel du matin",
            closed_at=timezone.now() if closed else None,
        )
        AttendanceMark.objects.create(
            school=self.school, session=session, enrollment=self.enrollments[index],
            status_code="a", status_label="Absent", status_group="absent",
            note="Note confidentielle de l'enseignant",
            justification="Justificatif interne sensible",
        )

    def test_manual_verification_required_role_and_audit(self):
        self.login(self.parent_a)
        empty = self.client.get(self.portal)
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json()["children"], [])
        self.assertIn("no-store", empty["Cache-Control"])
        self.login(self.secretary)
        self.assertEqual(self.write(self.root, {
            "guardian": str(self.guardians[0].pk), "username": self.parent_a.username,
        }).status_code, 403)
        self.login(self.director)
        self.assertEqual(self.write(self.root, {
            "guardian": str(self.guardians[0].pk), "username": self.outsider.username,
        }).status_code, 422)
        link = self.link()
        self.assertEqual(link["revision"], 1)
        self.assertEqual(self.write(self.root, {
            "guardian": str(self.guardians[0].pk), "username": self.parent_a.username,
        }).status_code, 409)
        self.login(self.parent_a)
        cards = self.client.get(self.portal).json()["children"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["student"], str(self.students[0].pk))
        self.assertNotIn("guardian_phone", str(cards))
        self.assertEqual(self.client.get(self.path(suffix="/enrollments")).status_code, 200)

    def test_school_session_separates_staff_and_parent_api_access(self):
        for user, password in (
            (self.director, "Strong parent portal test director 2026!"),
            (self.parent_a, "Strong parent portal test parent 2026!"),
        ):
            with self.subTest(user=user.username):
                SchoolLogin.objects.create(school=self.school, user=user, username=user.username)
                response = self.write("/api/v1/auth/login", {
                    "scope": "school", "school_code": str(self.school.pk),
                    "username": user.username, "password": password,
                })
                self.assertEqual(response.status_code, 200)
                self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
                session = self.client.get("/api/v1/auth/me").json()
                self.assertEqual(session["login_scope"], "school")
                self.assertEqual(session["school_id"], str(self.school.pk))
                self.assertEqual(self.client.get("/api/v1/parents/catalog").status_code, 200)
                family_allowed = user == self.parent_a
                self.assertEqual(self.client.get(self.portal).status_code, 200 if family_allowed else 403)
                self.assertEqual(self.client.get(self.root).status_code, 403 if family_allowed else 200)
                response = self.write("/api/v1/parents/family-children", {
                    "first_name": "Enfant", "last_name": "Test", "date_of_birth": "",
                })
                self.assertEqual(response.status_code, 201 if family_allowed else 403)
                if not family_allowed:
                    self.link()
        self.assertEqual(self.client.get(self.portal).json()["children"][0]["student"],
                         str(self.students[0].pk))
        response = self.write("/api/v1/auth/login", {
            "scope": "parent", "username": self.outsider.username,
            "password": "Strong parent portal test outsider 2026!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/me").json()["login_scope"], "parent")
        self.assertEqual(self.client.get("/api/v1/parents/family-children").json()["children"], [])

    def test_parent_attachment_preserves_existing_membership(self):
        url = f"/api/v1/schools/{self.school.pk}/members"
        for user, status in ((self.secretary, 409), (self.outsider, 201), (self.outsider, 200)):
            result = self.write(url, {"username": user.username, "role": "parent", "create_only": True})
            self.assertEqual(result.status_code, status, result.content)
        self.assertEqual(SchoolMember.objects.get(school=self.school, user=self.secretary).role.code,
                         "secretariat")
        self.assertEqual(SchoolMember.objects.get(school=self.school, user=self.outsider).role.code,
                         "parent")

    def test_cross_family_and_school_isolation_for_all_resources(self):
        self.login(self.director)
        self.link()
        self.link(index=1, user=self.parent_b)
        own_report = self.add_published_report()
        other_report = self.add_published_report(index=1)
        self.add_finance(0)
        self.add_finance(1)
        self.add_attendance(0)
        self.add_attendance(1)
        self.login(self.parent_a)
        for endpoint in ("/enrollments", "/reports", "/finance", "/attendance", "/timetable"):
            self.assertEqual(self.client.get(self.path(0, endpoint)).status_code, 200, endpoint)
            self.assertEqual(self.client.get(self.path(1, endpoint)).status_code, 404, endpoint)
        self.assertEqual(self.client.get(self.path(0, "/reports/" + str(other_report.pk))).status_code, 404)
        self.assertEqual(self.client.get(self.path(0, "/reports/" + str(other_report.pk) + "/pdf")).status_code, 404)
        self.assertEqual(self.client.get(self.path(1, "/reports/" + str(own_report.pk) + "/pdf")).status_code, 404)
        self.assertEqual(self.client.get(self.path(0, "/finance")).json()["totals"]["XAF"]["balance"], "100000.00")
        self.assertNotIn("PRIVATE-RECEIPT", str(self.client.get(self.path(0, "/finance")).json()))
        attendance = self.client.get(self.path(0, "/attendance")).json()["attendance"]
        self.assertEqual(len(attendance), 1)
        self.assertEqual(attendance[0]["status"], "Absent")
        self.assertNotIn("Note confidentielle", str(attendance))
        self.assertNotIn("Justificatif interne", str(attendance))
        # Existing generic staff APIs must still refuse parent-role access.
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/reports").status_code, 403)
        self.login(self.parent_b)
        self.assertEqual([x["student"] for x in self.client.get(self.portal).json()["children"]],
                         [str(self.students[1].pk)])

    def test_only_published_and_latest_corrected_report_with_pdf(self):
        self.login(self.director)
        self.link()
        published = self.add_published_report()
        amendment_snapshot = dict(published.snapshot)
        amendment_snapshot["overall"] = {"status": "calculated", "score": "15/20", "label": "Très bien"}
        ReportAmendment.objects.create(
            school=self.school, report=published, sequence=1,
            course_id=uuid.uuid4(), previous_percent="60", corrected_percent="75",
            reason="Rectification administrative", prior_snapshot=published.snapshot,
            snapshot=amendment_snapshot, created_by=self.director,
        )
        self.login(self.parent_a)
        listed = self.client.get(self.path(suffix="/reports"))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["reports"][0]["score"], "15/20")
        self.assertEqual(listed.json()["reports"][0]["amendment_sequence"], 1)
        detail = self.client.get(self.path(suffix="/reports/" + str(published.pk)))
        self.assertEqual(detail.json()["snapshot"]["overall"]["score"], "15/20")
        pdf = self.client.get(self.path(suffix="/reports/" + str(published.pk) + "/pdf"))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertIn("no-store", pdf["Cache-Control"])
        self.assertIn("rectificatif-1", pdf["Content-Disposition"])

    def test_revocation_parent_role_change_and_no_reactivation_by_parent(self):
        link = self.link()
        self.login(self.parent_a)
        self.assertEqual(len(self.client.get(self.portal).json()["children"]), 1)
        self.login(self.director)
        self.assertEqual(self.write(self.root + "/" + link["id"], {
            "revision": 0, "active": False,
        }, method="patch").status_code, 422)
        revoked = self.write(self.root + "/" + link["id"], {
            "revision": 1, "active": False,
        }, method="patch")
        self.assertEqual(revoked.status_code, 200, revoked.content.decode())
        self.login(self.parent_a)
        self.assertEqual(self.client.get(self.portal).json()["children"], [])
        self.assertEqual(self.client.get(self.path(suffix="/reports")).status_code, 404)
        self.assertEqual(self.write(self.root + "/" + link["id"], {
            "revision": 2, "active": True,
        }, method="patch").status_code, 403)
        self.login(self.director)
        revived = self.link()
        self.assertEqual(revived["id"], link["id"])
        self.assertEqual(revived["revision"], 3)
        SchoolMember.objects.filter(school=self.school, user=self.parent_a).update(
            role=SchoolRole.objects.get(school=self.school, code="enseignant"),
        )
        self.login(self.parent_a)
        self.assertEqual(self.client.get(self.portal).json()["children"], [])
        self.assertEqual(self.client.get(self.path(suffix="/finance")).status_code, 404)

    def test_unpublished_report_and_unclosed_attendance_not_visible(self):
        self.link()
        draft = self.add_published_report(published=False)
        self.add_attendance(closed=False)
        self.login(self.parent_a)
        self.assertEqual(self.client.get(self.path(suffix="/reports")).json()["reports"], [])
        self.assertEqual(self.client.get(self.path(suffix="/reports/" + str(draft.pk))).status_code, 404)
        self.assertEqual(self.client.get(self.path(suffix="/reports/" + str(draft.pk) + "/pdf")).status_code, 404)
        self.assertEqual(self.client.get(self.path(suffix="/attendance")).json()["attendance"], [])

    def test_csrf_404_anonymous_and_no_delete(self):
        self.assertEqual(self.client.post(
            self.root, json.dumps({"username": self.parent_a.username,
                                   "guardian": str(self.guardians[0].pk)}),
            content_type="application/json",
        ).status_code, 403)
        self.assertEqual(self.client.delete(
            self.root, HTTP_X_CSRFTOKEN=self.csrf,
        ).status_code, 405)
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.portal).json()["children"], [])
        self.assertEqual(self.client.get(self.path(suffix="/reports")).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.portal).status_code, 401)
