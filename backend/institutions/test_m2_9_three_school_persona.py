"""M2.9: isolated three-school persona rehearsal (never writes production data).

Exercises 12 fictitious pupils across two lycées and a mixed school using
real Django HTTP routes. Cash collection, admission conversion, grades and
publication are independently covered by dedicated journey tests.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicTrack, AcademicYear
from .finance_models import FeeCharge, FeeSchedule
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole
from .report_models import SchoolReport
from .services import ROLE_TEMPLATES
from .staff_models import StaffAssignment, StaffRecord
from .student_models import Enrollment, EnrollmentEvent, Student, StudentGuardian


@override_settings(PARENT_EMAIL_VERIFICATION_REQUIRED=False)
class ThreeSchoolPersonaM29Tests(TestCase):
    """A single parent account may have verified children in two schools."""

    def setUp(self):
        users = get_user_model()
        self.organization = Organization.objects.create(name="YEM M2.9 — groupe totalement fictif")
        self.parent_shared = users.objects.create_user(
            username="m29-parent-multi", password="M29 parent multi test 2026!",
        )
        self.parent_complex = users.objects.create_user(
            username="m29-parent-complexe", password="M29 parent complexe test 2026!",
        )
        self.unrelated = users.objects.create_user(
            username="m29-sans-ecole", password="M29 visiteur test 2026!",
        )
        self.schools = []
        definitions = (
            ("Lycée AWASSI (TEST M2.9)", "lycee_general", "lycee_general",
             "seconde", "Seconde", "s", "S", ("Seconde S1", "Seconde S2"), 70000),
            ("Lycée Privé 2 (TEST M2.9)", "lycee_general", "lycee_general",
             "terminale", "Terminale", "c", "C", ("Terminale C1", "Terminale C2"), 85000),
            ("Complexe scolaire Les 8 (TEST M2.9)", "groupe_scolaire", "primaire",
             "annee4", "Quatrième année", "", "", ("Quatrième année A", "Quatrième année B"), 45000),
        )
        for index, (name, school_type, cycle_code, level_code, level_name,
                    track_code, track_name, class_names, amount) in enumerate(definitions):
            school = School.objects.create(
                organization=self.organization, name=name,
                school_type=school_type, education_cycles=[cycle_code],
            )
            for role_code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=role_code,
                                          label=label, permissions=permissions)
            staff_users = {}
            for role in ("direction", "secretariat", "enseignant"):
                account = users.objects.create_user(
                    username=f"m29-{index}-{role}", password="M29 personnel test 2026!",
                )
                SchoolMember.objects.create(
                    school=school, user=account,
                    role=SchoolRole.objects.get(school=school, code=role),
                )
                staff_users[role] = account
            family_account = self.parent_shared if index < 2 else self.parent_complex
            SchoolMember.objects.create(
                school=school, user=family_account,
                role=SchoolRole.objects.get(school=school, code="parent"),
            )
            year = AcademicYear.objects.create(
                school=school, code="2026-2027", name="2026–2027",
                start_date="2026-09-01", end_date="2027-07-31",
                status=AcademicYear.STATUS_CURRENT,
            )
            cycle = AcademicCycle.objects.create(school=school, code=cycle_code,
                                                  name=cycle_code.replace("_", " ").title())
            level = AcademicLevel.objects.create(school=school, cycle=cycle,
                                                 code=level_code, name=level_name)
            track = None
            if track_code:
                track = AcademicTrack.objects.create(
                    school=school, level=level, code=track_code, name=track_name,
                )
            rooms = [
                AcademicClass.objects.create(
                    school=school, year=year, level=level, track=track,
                    code=f"m29-{index}-{j}", name=class_name, capacity=4,
                )
                for j, class_name in enumerate(class_names)
            ]
            teacher_record = StaffRecord.objects.create(
                school=school, account=staff_users["enseignant"],
                staff_code=f"m29-prof-{index}", first_name="Professeur",
                last_name="Fictif", position="enseignant",
            )
            StaffAssignment.objects.create(
                school=school, staff=teacher_record, year=year,
                classroom=rooms[0], duty="enseignant",
            )
            price = FeeSchedule.objects.create(
                school=school, year=year, code="scolarite-test-m29",
                label="Scolarité de simulation — aucune somme encaissée",
                amount=Decimal(amount), currency="XAF",
            )
            pupils, guardians, enrollments = [], [], []
            for pupil_index in range(4):
                student = Student.objects.create(
                    school=school, first_name=f"Élève-{index}-{pupil_index}",
                    last_name="FICTIF", date_of_birth="2011-03-12",
                )
                guardian = StudentGuardian.objects.create(
                    school=school, student=student,
                    full_name=f"Responsable FICTIF {index}/{pupil_index}",
                    relationship="Parent", is_primary=True,
                    phone="+24100000000",
                )
                enrolled = Enrollment.objects.create(
                    school=school, student=student, year=year,
                    classroom=rooms[pupil_index // 2], enrolled_on="2026-09-20",
                )
                FeeCharge.objects.create(
                    school=school, enrollment=enrolled, schedule=price,
                    label=price.label, amount=price.amount, currency="XAF",
                )
                pupils.append(student)
                guardians.append(guardian)
                enrollments.append(enrolled)
            self.schools.append({
                "school": school, "year": year, "rooms": rooms,
                "staff": staff_users, "family": family_account,
                "pupils": pupils, "guardians": guardians, "enrollments": enrollments,
                "amount": amount,
            })
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.schools[0]["staff"]["direction"])

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_three_schools_twelve_pupils_and_distinct_class_rosters(self):
        self.assertEqual(School.objects.count(), 3)
        self.assertEqual(Student.objects.count(), 12)
        self.assertEqual(StudentGuardian.objects.count(), 12)
        self.assertEqual(Enrollment.objects.count(), 12)
        self.assertEqual(FeeCharge.objects.count(), 12)
        identifiers = list(Student.objects.values_list("identity_id", flat=True))
        self.assertEqual(len(set(identifiers)), 12)
        yem_ids = [student.matricule_yem for batch in self.schools for student in batch["pupils"]]
        self.assertEqual(len(set(yem_ids)), 12)
        self.assertTrue(all(code.startswith("YEM-") for code in yem_ids))
        for batch in self.schools:
            self.login(batch["staff"]["direction"])
            school, year = batch["school"], batch["year"]
            overview = self.client.get(
                f"/api/v1/schools/{school.pk}/overview/classes",
                {"year": str(year.pk)},
            )
            self.assertEqual(overview.status_code, 200, overview.content)
            rows = overview.json()["classes"]
            self.assertEqual(len(rows), 2)
            self.assertEqual(sum(row["enrolled"] for row in rows), 4)
            self.assertEqual([row["remaining"] for row in rows], [2, 2])
            self.assertEqual(overview.json()["unassigned_students"], 0)
            self.assertEqual(str(year.pk), overview.json()["year"]["id"])
            self.assertEqual(len({student.student_code for student in batch["pupils"]}), 4)
            for room in batch["rooms"]:
                result = self.client.get(
                    f"/api/v1/schools/{school.pk}/classes/{room.pk}/students"
                )
                self.assertEqual(result.status_code, 200, result.content)
                self.assertEqual(len(result.json()["students"]), 2)
                self.assertTrue(all(set(row) == {
                    "id", "first_name", "last_name", "student_code",
                } for row in result.json()["students"]))

    def test_roles_and_other_school_protection(self):
        first, second = self.schools[:2]
        first_school, other_school = first["school"], second["school"]
        first_student, foreign_student = first["pupils"][0], second["pupils"][0]
        first_room, another_room = first["rooms"]
        self.login(first["staff"]["direction"])
        dossier = self.client.get(
            f"/api/v1/schools/{first_school.pk}/students/{first_student.pk}/dossier"
        )
        self.assertEqual(dossier.status_code, 200, dossier.content)
        self.assertTrue(dossier.json()["sensitive_visible"])
        self.assertTrue(dossier.json()["finance_visible"])
        self.assertEqual(len(dossier.json()["guardians"]), 1)
        self.assertEqual(dossier.json()["enrollments"][0]["finance"]["balance"], "70000.00")
        # A director's authority is per school, never per organization.
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{other_school.pk}/students/{foreign_student.pk}/dossier"
        ).status_code, 404)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{first_school.pk}/students/{foreign_student.pk}/dossier"
        ).status_code, 404)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{other_school.pk}/overview/classes"
        ).status_code, 404)
        self.login(first["staff"]["enseignant"])
        own_roster = self.client.get(
            f"/api/v1/schools/{first_school.pk}/classes/{first_room.pk}/students"
        )
        self.assertEqual(own_roster.status_code, 200, own_roster.content)
        self.assertEqual(len(own_roster.json()["students"]), 2)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{first_school.pk}/classes/{another_room.pk}/students"
        ).status_code, 403)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{first_school.pk}/students/{first_student.pk}/dossier"
        ).status_code, 403)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{other_school.pk}/classes/{second['rooms'][0].pk}/students"
        ).status_code, 404)
        self.login(self.unrelated)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{first_school.pk}/classes/{first_room.pk}/students"
        ).status_code, 404)

    def test_one_parent_account_two_schools_and_revocation(self):
        first, second, third = self.schools
        for batch in (first, second, third):
            school = batch["school"]
            self.login(batch["staff"]["direction"])
            url = f"/api/v1/schools/{school.pk}/parent-links"
            payload = {
                "guardian": str(batch["guardians"][0].pk),
                "username": batch["family"].username,
            }
            self.assertEqual(self.post(url, {**payload, "identity_verified": False}).status_code, 422)
            self.assertEqual(self.post(url, payload).status_code, 422)
            response = self.post(url, {**payload, "identity_verified": True})
            self.assertEqual(response.status_code, 201, response.content)
            self.assertTrue(SchoolAudit.objects.filter(
                school=school, event="parent_link_verified",
            ).exists())
            batch["link"] = response.json()
        self.login(self.parent_shared)
        result = self.client.get("/api/v1/parents/children")
        self.assertEqual(result.status_code, 200, result.content)
        visible = {row["student"] for row in result.json()["children"]}
        allowed = {str(first["pupils"][0].pk), str(second["pupils"][0].pk)}
        self.assertEqual(visible, allowed)
        self.assertTrue(result.json()["parent_role"])
        for batch in self.schools:
            for j, pupil in enumerate(batch["pupils"]):
                allowed_child = str(pupil.pk) in allowed
                for suffix in ("/enrollments", "/finance", "/reports", "/grades",
                               "/attendance", "/timetable"):
                    response = self.client.get(
                        f"/api/v1/parents/children/{pupil.pk}{suffix}"
                    )
                    self.assertEqual(
                        response.status_code, 200 if allowed_child else 404,
                        (batch["school"].name, j, suffix, response.content[:200]),
                    )
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{first['school'].pk}/students/{first['pupils'][0].pk}/dossier"
        ).status_code, 403)
        self.login(self.parent_complex)
        self.assertEqual(
            [row["student"] for row in self.client.get("/api/v1/parents/children").json()["children"]],
            [str(third["pupils"][0].pk)],
        )
        # Revocation takes effect immediately without deleting the school record.
        self.login(first["staff"]["direction"])
        link = first["link"]
        revoke = self.client.patch(
            f"/api/v1/schools/{first['school'].pk}/parent-links/{link['id']}",
            data=json.dumps({"revision": link["revision"], "active": False}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(revoke.status_code, 200, revoke.content)
        self.login(self.parent_shared)
        after = {row["student"] for row in self.client.get("/api/v1/parents/children").json()["children"]}
        self.assertEqual(after, {str(second["pupils"][0].pk)})
        self.assertEqual(self.client.get(
            f"/api/v1/parents/children/{first['pupils'][0].pk}/finance"
        ).status_code, 404)

    def test_m27_class_change_keeps_same_pupil_and_fee_snapshot(self):
        batch = self.schools[0]
        student, enrollment, first, second = (
            batch["pupils"][0], batch["enrollments"][0],
            batch["rooms"][0], batch["rooms"][1],
        )
        self.login(batch["staff"]["direction"])
        url = f"/api/v1/schools/{batch['school'].pk}/enrollments/{enrollment.pk}/assignment"
        target = self.post(url, {
            "revision": 1, "mode": "automatic",
            "reason": "Équilibrage des effectifs pour M2.9",
        })
        self.assertEqual(target.status_code, 200, target.content)
        # Two divisions begin with equal occupancy: stable name order chooses
        # the only other compatible division, then recounts in the same transaction.
        self.assertEqual(target.json()["assignment"]["to_class"], str(second.pk))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.classroom_id, second.pk)
        self.assertEqual(enrollment.student_id, student.pk)
        self.assertEqual(enrollment.revision, 2)
        self.assertEqual(Enrollment.objects.filter(student=student).count(), 1)
        self.assertEqual(FeeCharge.objects.filter(enrollment=enrollment).count(), 1)
        change = EnrollmentEvent.objects.get(enrollment=enrollment)
        self.assertEqual(change.assignment_mode, "automatic")
        self.assertEqual(change.actor_id, batch["staff"]["direction"].pk)
        counts = self.client.get(
            f"/api/v1/schools/{batch['school'].pk}/overview/classes",
            {"year": str(batch["year"].pk)},
        ).json()["classes"]
        self.assertEqual([row["enrolled"] for row in counts], [1, 3])
        self.assertEqual(self.post(url, {
            "revision": 1, "mode": "manual", "classroom": str(first.pk),
            "reason": "Demande doublon à refuser",
        }).status_code, 409)

    def test_published_reports_only_to_correct_verified_family(self):
        first, second = self.schools[:2]
        report_ids = []
        for batch in (first, second):
            student, enrollment = batch["pupils"][0], batch["enrollments"][0]
            report = SchoolReport.objects.create(
                school=batch["school"], enrollment=enrollment, year=batch["year"],
                status="published", published_at=timezone.now(), snapshot={
                    "school": {"name": batch["school"].name},
                    "template": {"title": "Bulletin", "show_score": True, "show_label": True},
                    "student": {"last_name": student.last_name, "first_name": student.first_name,
                                "code": student.student_code},
                    "class": {"name": enrollment.classroom.name},
                    "year": {"name": batch["year"].name},
                    "period": None,
                    "subjects": [{"subject": "Français", "coefficient": "1",
                                  "result": {"score": "12/20", "label": "Bien"}}],
                    "overall": {"status": "calculated", "score": "12/20", "label": "Bien"},
                },
            )
            report_ids.append(report.pk)
            self.login(batch["staff"]["direction"])
            result = self.post(
                f"/api/v1/schools/{batch['school'].pk}/parent-links",
                {"guardian": str(batch["guardians"][0].pk),
                 "username": self.parent_shared.username,
                 "identity_verified": True},
            )
            self.assertEqual(result.status_code, 201, result.content)
        self.login(self.parent_shared)
        for batch, report_id in zip((first, second), report_ids):
            url = f"/api/v1/parents/children/{batch['pupils'][0].pk}/reports"
            self.assertEqual(self.client.get(url).status_code, 200)
            response = self.client.get(url + f"/{report_id}")
            self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.client.get(
            f"/api/v1/parents/children/{first['pupils'][1].pk}/reports"
        ).status_code, 404)
        self.login(self.parent_complex)
        self.assertEqual(self.client.get(
            f"/api/v1/parents/children/{first['pupils'][0].pk}/reports/{report_ids[0]}"
        ).status_code, 404)
