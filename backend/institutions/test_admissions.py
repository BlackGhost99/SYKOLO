"""Module 14: admissions are private, auditable and convert atomically."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .admission_models import AdmissionApplication, AdmissionEvent
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent


class AdmissionWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="adm-director", password="Strong test admission director 2026!")
        self.secretary = User.objects.create_user(username="adm-secretary", password="Strong test admission secretary 2026!")
        self.teacher = User.objects.create_user(username="adm-teacher", password="Strong test admission teacher 2026!")
        self.stranger = User.objects.create_user(username="adm-stranger", password="Strong test admission stranger 2026!")
        org = Organization.objects.create(name="Organisation fictive YEM Admissions")
        self.school = School.objects.create(organization=org, name="École admission")
        self.other = School.objects.create(organization=org, name="Autre école")
        for school in (self.school, self.other):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        for user, role in [(self.director, "direction"), (self.secretary, "secretariat"), (self.teacher, "enseignant")]:
            SchoolMember.objects.create(
                school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code=role),
            )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-27", name="2026-2027",
            start_date="2026-09-01", end_date="2027-07-31",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="ce1", name="CE1")
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="ce1a", name="CE1 A", capacity=1,
        )
        self.other_classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="ce1b", name="CE1 B", capacity=10,
        )
        self.client = Client(enforce_csrf_checks=True)
        self.base = f"/api/v1/schools/{self.school.pk}/admissions"
        self.login(self.director)

    def login(self, user):
        self.client.force_login(user)
        self.token = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, path, payload, method="post"):
        return getattr(self.client, method)(
            self.base + path, data=json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )

    def data(self, classroom=None, existing=None):
        result = {
            "year": str(self.year.pk), "classroom": str((classroom or self.classroom).pk),
            "first_name": "Léa", "last_name": "Nzamba", "date_of_birth": "2018-10-17",
            "guardian_name": "Mme Nzamba", "guardian_relationship": "Mère",
            "guardian_phone": "+241 000 00 00", "guardian_email": "parent@example.test",
            "source": "guichet",
        }
        if existing:
            result["existing_student"] = str(existing.pk)
        return result

    def create(self, data=None):
        response = self.post("", data or self.data())
        self.assertEqual(response.status_code, 201, response.content.decode())
        return response.json()

    def decide(self, row, status="accepted", revision=1, reason="Décision après étude du dossier"):
        return self.post(f"/{row['id']}/decide", {
            "revision": revision, "status": status, "reason": reason,
        })

    def convert(self, row, code="YEM001", revision=2):
        return self.post(f"/{row['id']}/convert", {
            "revision": revision, "enrolled_on": "2026-10-03", "student_code": code,
        })

    def test_admission_to_enrollment_and_guardian_with_audit(self):
        row = self.create()
        self.assertEqual(row["status"], "submitted")
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(Enrollment.objects.count(), 0)
        self.assertEqual(self.convert(row, revision=1).status_code, 409)
        reviewing = self.decide(row, "review")
        self.assertEqual(reviewing.status_code, 200, reviewing.content.decode())
        accepted = self.decide(row, revision=2)
        self.assertEqual(accepted.status_code, 200, accepted.content.decode())
        self.assertEqual(accepted.json()["status"], "accepted")
        self.login(self.secretary)
        self.assertEqual(self.decide(row, revision=3).status_code, 403)
        final = self.convert(row, revision=3)
        self.assertEqual(final.status_code, 201, final.content.decode())
        self.assertEqual(final.json()["status"], "enrolled")
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(StudentGuardian.objects.count(), 1)
        self.assertEqual(EnrollmentEvent.objects.count(), 1)
        self.assertRegex(Enrollment.objects.get().student.student_code, r"^YEM-[0-9A-F]{32}$")
        self.assertEqual(StudentGuardian.objects.get().full_name, "Mme Nzamba")
        duplicate = self.convert(row, revision=3)
        self.assertEqual(duplicate.status_code, 200, duplicate.content.decode())
        self.assertEqual(duplicate.json()["enrollment"], final.json()["enrollment"])
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(AdmissionEvent.objects.filter(application_id=row["id"]).count(), 4)
        history = self.client.get(self.base + f"/{row['id']}/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual([x["status"] for x in history.json()["history"]],
                         ["submitted", "review", "accepted", "enrolled"])

    def test_capacity_checked_at_conversion_not_assumed_reservation(self):
        first = self.create()
        second = self.create()
        self.assertEqual(self.decide(first).status_code, 200)
        self.assertEqual(self.decide(second).status_code, 200)
        before = self.client.get(self.base + "/capacity/" + str(self.classroom.pk)).json()
        self.assertEqual(before["accepted_pending"], 2)
        self.assertEqual(before["occupied"], 0)
        self.assertEqual(before["remaining"], 1)
        self.assertEqual(self.convert(first, "YEM101").status_code, 201)
        capacity = self.client.get(self.base + "/capacity/" + str(self.classroom.pk)).json()
        self.assertEqual(capacity["remaining"], 0)
        rejected = self.convert(second, "YEM102")
        self.assertEqual(rejected.status_code, 422, rejected.content.decode())
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(AdmissionApplication.objects.get(pk=second["id"]).status, "accepted")

    def test_rejected_stale_and_bad_transition(self):
        row = self.create()
        self.assertEqual(self.decide(row, revision=9).status_code, 409)
        self.assertEqual(self.decide(row, reason="").status_code, 422)
        rejected = self.decide(row, "rejected")
        self.assertEqual(rejected.status_code, 200, rejected.content.decode())
        self.assertEqual(self.convert(row).status_code, 409)
        self.assertEqual(self.decide(row, "accepted", revision=2).status_code, 409)
        self.assertEqual(AdmissionEvent.objects.filter(application_id=row["id"]).count(), 2)

    def test_existing_student_reenrollment_and_prevent_double(self):
        student = Student.objects.create(
            school=self.school, student_code="PREV-01", first_name="Léa", last_name="Nzamba",
        )
        row = self.create(self.data(classroom=self.other_classroom, existing=student))
        self.assertEqual(self.decide(row).status_code, 200)
        enrolled = self.convert(row, code="PREV-01")
        self.assertEqual(enrolled.status_code, 201, enrolled.content.decode())
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(StudentGuardian.objects.count(), 0)
        another = self.create(self.data(existing=student))
        self.assertEqual(self.decide(another).status_code, 200)
        self.assertEqual(self.convert(another, code="PREV-01").status_code, 409)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_reject_invalid_dates_email_and_foreign_links(self):
        invalid = self.data()
        invalid["guardian_email"] = "not-an-email"
        self.assertEqual(self.post("", invalid).status_code, 422)
        invalid = self.data()
        invalid["date_of_birth"] = "2026-99-99"
        self.assertEqual(self.post("", invalid).status_code, 422)
        invalid = self.data()
        invalid["classroom"] = str(self.other.pk)
        self.assertEqual(self.post("", invalid).status_code, 422)
        foreign_student = Student.objects.create(
            school=self.other, student_code="FOREIGN", first_name="Autre", last_name="Élève",
        )
        invalid = self.data(existing=foreign_student)
        self.assertEqual(self.post("", invalid).status_code, 422)
        row = self.create()
        self.assertEqual(self.decide(row).status_code, 200)
        self.assertEqual(self.post(f"/{row['id']}/convert", {
            "revision": 2, "enrolled_on": "2028-04-01", "student_code": "A",
        }).status_code, 422)
        self.assertEqual(Enrollment.objects.count(), 0)

    def test_private_access_and_csrf(self):
        row = self.create()
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base).status_code, 403)
        self.assertEqual(self.decide(row).status_code, 403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get(self.base + "/" + row["id"]).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other.pk}/admissions").status_code, 404)
        self.login(self.director)
        self.assertEqual(self.client.post(self.base, json.dumps(self.data()),
                                          content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(self.base + "/" + row["id"],
                                            HTTP_X_CSRFTOKEN=self.token).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.base).status_code, 401)

    def test_concours_requires_eligibility_and_verified_result_before_admission(self):
        payload = {**self.data(), "route": "concours", "origin_school": "École primaire",
                   "route_reference": ""}
        row = self.create(payload)
        self.assertEqual(row["route"], "concours")
        self.assertEqual(row["required_documents"], ["concours_result"])
        self.assertEqual(self.decide(row).status_code, 409)
        eligible = self.post(f"/{row['id']}/eligibility", {
            "revision": 1, "result": "eligible", "route_reference": "CONC-2026-001",
            "orientation_authority": "", "reason": "Résultat communiqué par le centre"
        })
        self.assertEqual(eligible.status_code, 200, eligible.content.decode())
        self.assertEqual(self.decide(row, revision=2).status_code, 409)
        doc = self.post(f"/{row['id']}/documents", {
            "revision": 2, "code": "concours_result", "reference": "Relevé concours 2026 n°001"
        })
        self.assertEqual(doc.status_code, 201, doc.content.decode())
        document_id = doc.json()["documents"][0]["id"]
        self.assertEqual(self.decide(row, revision=3).status_code, 409)
        reviewed = self.post(f"/{row['id']}/documents/{document_id}/review", {
            "revision": 3, "status": "verified", "reason": "Document vérifié par la direction"
        })
        self.assertEqual(reviewed.status_code, 200, reviewed.content.decode())
        self.assertEqual(reviewed.json()["documents"][0]["status"], "verified")
        accepted = self.decide(row, revision=4)
        self.assertEqual(accepted.status_code, 200, accepted.content.decode())
        self.assertEqual(Student.objects.count(), 0)
        enrolled = self.convert(row, code="CONC001", revision=5)
        self.assertEqual(enrolled.status_code, 201, enrolled.content.decode())
        self.assertEqual(Student.objects.count(), 1)

    def test_orientation_separates_eligibility_and_school_enrollment(self):
        row = self.create({**self.data(), "route": "orientation",
                           "origin_school": "École primaire de départ"})
        self.assertEqual(row["required_documents"], ["orientation_decision"])
        bad = self.post(f"/{row['id']}/eligibility", {
            "revision": 1, "result": "eligible", "route_reference": "AFF-2026-002",
            "orientation_authority": "", "reason": "Vérification"
        })
        self.assertEqual(bad.status_code, 422)
        updated = self.post(f"/{row['id']}/eligibility", {
            "revision": 1, "result": "eligible", "route_reference": "AFF-2026-002",
            "orientation_authority": "Commission d'orientation", "reason": "Attestation présentée"
        })
        self.assertEqual(updated.status_code, 200, updated.content.decode())
        self.assertEqual(self.decide(row, revision=2).status_code, 409)
        doc = self.post(f"/{row['id']}/documents", {
            "revision": 2, "code": "orientation_decision", "reference": "Attestation d'affectation n°002"
        })
        self.assertEqual(doc.status_code, 201, doc.content.decode())
        checked = self.post(f"/{row['id']}/documents/{doc.json()['documents'][0]['id']}/review", {
            "revision": 3, "status": "verified", "reason": "Pièce et destinataire contrôlés"
        })
        self.assertEqual(checked.status_code, 200, checked.content.decode())
        self.assertEqual(self.decide(row, revision=4).status_code, 200)
        self.assertFalse(Enrollment.objects.exists())
        self.assertEqual(self.convert(row, code="AFF002", revision=5).status_code, 201)

    def test_level_policy_and_mandatory_documents_snapshot(self):
        policy = self.post("/policy", {
            "year": str(self.year.pk), "level": str(self.classroom.level_id),
            "revision": 0, "enabled_routes": ["direct", "concours"],
            "required_documents": {"direct": ["birth_certificate", "school_report"],
                                   "concours": ["birth_certificate"]}
        })
        self.assertEqual(policy.status_code, 200, policy.content.decode())
        self.assertEqual(policy.json()["scope_revision"], 1)
        policy_read = self.client.get(self.base + f"/policy?year={self.year.pk}&level={self.classroom.level_id}")
        self.assertEqual(policy_read.json()["enabled_routes"], ["direct", "concours"])
        cannot = self.post("", {**self.data(), "route": "orientation"})
        self.assertEqual(cannot.status_code, 422)
        row = self.create()
        self.assertEqual(row["required_documents"], ["birth_certificate", "school_report"])
        self.assertEqual(self.decide(row).status_code, 409)
        for code, revision in (("birth_certificate", 1), ("school_report", 3)):
            added = self.post(f"/{row['id']}/documents", {
                "revision": revision, "code": code, "reference": f"Pièce papier {code}"
            })
            self.assertEqual(added.status_code, 201, added.content.decode())
            id = added.json()["documents"][-1]["id"]
            reviewed = self.post(f"/{row['id']}/documents/{id}/review", {
                "revision": revision + 1, "status": "verified", "reason": "Contrôle documentaire"
            })
            self.assertEqual(reviewed.status_code, 200, reviewed.content.decode())
        self.assertEqual(self.decide(row, revision=5).status_code, 200)
        revised_policy = self.post("/policy", {
            "year": str(self.year.pk), "level": str(self.classroom.level_id),
            "revision": 1, "enabled_routes": ["direct"],
            "required_documents": {"direct": ["new_document"]}
        })
        self.assertEqual(revised_policy.status_code, 200, revised_policy.content.decode())
        self.assertEqual(AdmissionApplication.objects.get(pk=row["id"]).required_documents,
                         ["birth_certificate", "school_report"])

    def test_secretary_cannot_verify_or_change_policy_but_can_record(self):
        row = self.create({**self.data(), "route": "concours"})
        self.login(self.secretary)
        self.assertEqual(self.post("/policy", {
            "year": str(self.year.pk), "level": None, "revision": 0,
            "enabled_routes": ["direct"], "required_documents": {}
        }).status_code, 403)
        document = self.post(f"/{row['id']}/documents", {
            "revision": 1, "code": "concours_result", "reference": "Document au secrétariat"
        })
        self.assertEqual(document.status_code, 201, document.content.decode())
        doc_id = document.json()["documents"][0]["id"]
        self.assertEqual(self.post(f"/{row['id']}/documents/{doc_id}/review", {
            "revision": 2, "status": "verified", "reason": "Essai"
        }).status_code, 403)
        self.login(self.director)
        self.assertEqual(self.client.get(self.base + f"/{row['id']}/documents").status_code, 200)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base + f"/{row['id']}/documents").status_code, 404)


    def test_readiness_explains_concours_blockers_until_evidence_is_verified(self):
        row = self.create({**self.data(), "route": "concours"})
        self.assertIn("concours", row["acceptance_blocker"])
        update = self.post(f"/{row['id']}/eligibility", {
            "revision": 1, "result": "eligible",
            "route_reference": "CONC-RECETTE-2026",
            "orientation_authority": "",
            "reason": "Résultat externe déclaré",
        })
        self.assertEqual(update.status_code, 200, update.content)
        self.assertIn("concours_result", update.json()["acceptance_blocker"])
        proof = self.post(f"/{row['id']}/documents", {
            "revision": 2, "code": "concours_result",
            "reference": "Procès-verbal de concours de test",
        })
        self.assertEqual(proof.status_code, 201, proof.content)
        self.assertIn("concours_result", self.client.get(
            self.base + f"/{row['id']}"
        ).json()["acceptance_blocker"])
        document_id = proof.json()["documents"][0]["id"]
        checked = self.post(f"/{row['id']}/documents/{document_id}/review", {
            "revision": 3, "status": "verified", "reason": "Référence vérifiée",
        })
        self.assertEqual(checked.status_code, 200, checked.content)
        response = self.client.get(self.base + f"/{row['id']}")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIsNone(response.json()["acceptance_blocker"])

    def test_direct_readiness_respects_required_documents_without_payment(self):
        configured = self.post("/policy", {
            "year": str(self.year.pk), "level": str(self.classroom.level_id),
            "revision": 0, "enabled_routes": ["direct", "concours"],
            "required_documents": {"direct": ["birth_certificate"]},
        })
        self.assertEqual(configured.status_code, 200, configured.content)
        row = self.create()
        self.assertIn("birth_certificate", row["acceptance_blocker"])
        self.assertEqual(self.decide(row).status_code, 409)
        proof = self.post(f"/{row['id']}/documents", {
            "revision": 1, "code": "birth_certificate",
            "reference": "Copie acte de naissance fictif",
        })
        self.assertEqual(proof.status_code, 201, proof.content)
        document_id = proof.json()["documents"][0]["id"]
        validated = self.post(f"/{row['id']}/documents/{document_id}/review", {
            "revision": 2, "status": "verified",
            "reason": "Identité vérifiée par la direction",
        })
        self.assertEqual(validated.status_code, 200, validated.content)
        self.assertIsNone(self.client.get(
            self.base + f"/{row['id']}"
        ).json()["acceptance_blocker"])
        accepted = self.decide(row, revision=3)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertFalse(Enrollment.objects.exists())

    def test_rejected_or_unverified_proof_never_grants_concours_admission(self):
        row = self.create({**self.data(), "route": "concours"})
        self.assertEqual(self.post(f"/{row['id']}/eligibility", {
            "revision": 1, "result": "ineligible", "route_reference": "C-FAIL",
            "orientation_authority": "", "reason": "Candidat non admis au concours"
        }).status_code, 200)
        added = self.post(f"/{row['id']}/documents", {
            "revision": 2, "code": "concours_result", "reference": "Avis de résultat"
        })
        self.assertEqual(added.status_code, 201)
        doc_id = added.json()["documents"][0]["id"]
        self.assertEqual(self.post(f"/{row['id']}/documents/{doc_id}/review", {
            "revision": 3, "status": "verified", "reason": "Document authentique"
        }).status_code, 200)
        self.assertEqual(self.decide(row, revision=4).status_code, 409)
