"""One continuous lycée-family journey, using a disposable Django test database only.

This test must never create a live user, student or financial transaction in YEM.
It uses the existing PayCentral test sandbox protocol, not a real operator wallet.
"""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .academic_models import AcademicTrack
from .admission_models import AdmissionApplication, AdmissionPolicy
from .admission_policy import policy_key
from .attendance_models import AttendanceSession
from .staff_models import StaffRecord, StaffAssignment
from .finance_models import FeePayment
from .models import SchoolMember, SchoolRole
from .parent_admission_models import ParentAdmissionRequest
from .parent_models import GuardianAccountLink
from .parent_payment_models import ParentPaymentAttempt
from .services import SECONDARY_ROLE_TEMPLATES
from .student_models import Enrollment, Student, StudentGuardian
from .test_parent_payments import ParentPaymentTests, KEY, SECRET, MOCK_TXN, PHONE


@override_settings(
    PARENT_EMAIL_VERIFICATION_REQUIRED=False,
    PASSWORD_RESET_ENABLED=False,
    YEM_PAYMENT_ENCRYPTION_KEY="sandbox-test-only-YEM-encryption-key-abcdefghijklmnopqrstuvwxyz",
    YEM_PAYMENTS_LIVE_ENABLED=False,
    AUTH_PUBLIC_BASE_URL="https://yem.example.test",
)
class Lycee2ParentJourneyTests(TestCase):
    """Parent signup -> Seconde S -> simulated payment -> secretariat -> head -> student."""

    def setUp(self):
        # Reuse an established sandbox payment fixture without running its test methods.
        self.fixture = ParentPaymentTests
        self.fixture.setUp(self)
        self.school.name = "Lycée Privé 2 (base de test)"
        self.school.school_type = "lycee_general"
        self.school.education_cycles = ["college", "lycee_general"]
        self.school.save(update_fields=["name", "school_type", "education_cycles"])
        cycle = self.level.cycle
        cycle.code, cycle.name = "lycee_general", "Lycée général"
        cycle.save(update_fields=["code", "name"])
        self.level.code, self.level.name = "seconde", "Seconde"
        self.level.save(update_fields=["code", "name"])
        series = AcademicTrack.objects.create(
            school=self.school, level=self.level, code="s", name="S",
        )
        self.classroom.code, self.classroom.name, self.classroom.track = "seconde-s", "Seconde S", series
        self.classroom.save(update_fields=["code", "name", "track"])
        AdmissionPolicy.objects.create(
            school=self.school, year=self.year, level=self.level,
            scope_key=policy_key(self.year.pk, self.level.pk),
            enabled_routes=["direct"],
            required_documents={"direct": ["birth_certificate", "previous_reports"]},
        )
        self.proviseur = self.director
        proviseur_role = SchoolRole.objects.create(
            school=self.school, code="proviseur", label="Proviseur",
            permissions=SchoolRole.objects.get(school=self.school, code="direction").permissions,
        )
        member = SchoolMember.objects.get(school=self.school, user=self.proviseur)
        member.role = proviseur_role
        member.save(update_fields=["role"])
        self.secretary = get_user_model().objects.create_user("lycee2-secretary", password="Test secretariat 2026!")
        SchoolMember.objects.create(school=self.school, user=self.secretary,
            role=SchoolRole.objects.get(school=self.school, code="secretariat"))
        self.role_users = {}
        for code, label, permissions in SECONDARY_ROLE_TEMPLATES["lycee_general"]:
            if code not in ("etudes", "vie_scolaire"):
                continue
            role = SchoolRole.objects.create(
                school=self.school, code=code, label=label, permissions=list(permissions),
            )
            user = get_user_model().objects.create_user("lycee2-"+code, password="Test role 2026!")
            SchoolMember.objects.create(school=self.school, user=user, role=role)
            self.role_users[code] = user

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, route, data):
        return self.client.post("/api/v1/"+route, data=json.dumps(data),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def assert_success(self, response, code):
        self.assertEqual(response.status_code, code, response.content)
        return response.json()

    def test_complete_lycee2_seconde_s_direct_application(self):
        self.client.logout()
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
        status = self.client.get("/api/v1/auth/parents/registration-status")
        self.assertEqual(status.status_code, 200)
        self.assertFalse(status.json()["email_verification_required"])

        parent_username = "lycee2-famille-exemple"
        parent = self.assert_success(self.post("auth/parents/register", {
            "username": parent_username, "first_name": "Parent", "last_name": "Test",
            "email": "parent-lycee2@example.test", "password": "Inscription test YEM 2026!",
        }), 200)
        self.assertFalse(parent["email_verification_required"])
        created = get_user_model().objects.get(username=parent_username)
        self.assertTrue(created.is_active)
        self.assertFalse(SchoolMember.objects.filter(user=created).exists())
        self.assert_success(self.post("auth/login", {
            "username": parent_username, "password": "Inscription test YEM 2026!", "scope": "parent",
        }), 200)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

        schools = self.client.get("/api/v1/parents/catalog").json()["schools"]
        lycee = next(s for s in schools if s["id"] == str(self.school.pk))
        room = next(c for c in lycee["classes"] if c["name"] == "Seconde S")
        self.assertEqual(room["fee_amount_xaf"], 2500)
        self.assertTrue(room["online_payment_available"])

        child = self.assert_success(self.post("parents/family-children", {
            "first_name": "Élève", "last_name": "Essai", "date_of_birth": "2010-04-03",
        }), 201)
        application = self.assert_success(self.post("parents/applications", {
            "child": child["id"], "classroom": room["id"], "route": "direct",
            "payment_choice": "online", "guardian_relationship": "Mère",
            "guardian_phone": PHONE, "origin_school": "", "route_reference": "",
        }), 201)
        app_id = ParentAdmissionRequest.objects.get(pk=application["id"]).application_id
        self.assertEqual(application["status"], "submitted")
        self.assertFalse(Enrollment.objects.exists())
        self.assertFalse(Student.objects.exists())

        with patch("institutions.parent_payment_views.paycentral_request",
            return_value={"success": True, "data": {
                "transaction_id": MOCK_TXN, "status": "processing", "provider": "airtel",
                "amount": 2500, "currency": "XAF",
            }}):
            initiated = self.assert_success(self.post(
                "parents/applications/"+application["id"]+"/pay",
                {"channel": "airtel", "phone": PHONE},
            ), 201)
        self.assertEqual(initiated["provider_mode"], "sandbox")
        attempt = ParentPaymentAttempt.objects.get(pk=initiated["id"])
        callback = {"event": "payment.success", "timestamp": "2026-11-10T08:00:00Z",
                    "data": {"id": MOCK_TXN, "provider": "airtel",
                    "amount": "2500.00", "currency": "XAF", "status": "success",
                    "merchant_reference": attempt.merchant_reference,
                    "provider_reference": "provider-sandbox-lycee2"}}
        raw = json.dumps(callback, separators=(",", ":")).encode()
        signature = "sha256="+hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
        reply = self.client.post("/api/v1/parents/paycentral/webhook", data=raw,
            content_type="application/json", HTTP_X_PAYCENTRAL_SIGNATURE=signature)
        self.assertEqual(reply.status_code, 200, reply.content)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "success")
        self.assertFalse(self.client.get(
            "/api/v1/parents/applications/"+application["id"]+"/payments"
        ).json()["payments"][0]["paid_confirmed"])
        self.assertFalse(Enrollment.objects.exists())
        self.assertFalse(FeePayment.objects.exists())  # Aucune recette réelle depuis sandbox.

        self.login(self.secretary)
        admissions_base = f"schools/{self.school.pk}/admissions"
        self.assertEqual(self.client.get("/api/v1/"+admissions_base).status_code, 200)
        self.assertEqual(len(AdmissionApplication.objects.get(pk=app_id).required_documents), 2)
        for doc_code in AdmissionApplication.objects.get(pk=app_id).required_documents:
            row = AdmissionApplication.objects.get(pk=app_id)
            self.assert_success(self.post(
                admissions_base+f"/{app_id}/documents",
                {"revision": row.revision, "code": doc_code,
                 "reference": "Référence papier contrôlable (test)"},
            ), 201)
        self.login(self.proviseur)
        row = AdmissionApplication.objects.get(pk=app_id)
        blocked = self.post(admissions_base+f"/{app_id}/decide", {
            "revision": row.revision, "status": "accepted", "reason": "Sans vérifier les pièces",
        })
        self.assertEqual(blocked.status_code, 409)
        for doc in row.documents.all():
            self.assert_success(self.post(
                admissions_base+f"/{app_id}/documents/{doc.pk}/review",
                {"revision": row.revision, "status": "verified", "reason": "Contrôle test"},
            ), 200)
            row.refresh_from_db()
        self.assert_success(self.post(admissions_base+f"/{app_id}/decide", {
            "revision": row.revision, "status": "accepted", "reason": "Inscription directe acceptée",
        }), 200)
        self.assertFalse(Enrollment.objects.exists())

        self.login(self.secretary)
        row.refresh_from_db()
        # A PayCentral sandbox success is NOT a real payment. The new gate must
        # refuse conversion until verified aid or a real cashier receipt exists.
        self.assertEqual(self.post(admissions_base+f"/{app_id}/convert", {
            "revision": row.revision, "enrolled_on": "2026-11-10",
        }).status_code, 409)
        self.assertFalse(Enrollment.objects.exists())
        self.login(self.proviseur)
        scholarship = self.post(admissions_base+f"/{app_id}/scholarship", {
            "action": "approve", "coverage": "all", "revision": 0,
            "reference": "ETAT-RECETTE-TEST-2026",
        })
        self.assertEqual(scholarship.status_code, 201, scholarship.content)
        self.login(self.secretary)
        row.refresh_from_db()
        converted = self.assert_success(self.post(admissions_base+f"/{app_id}/convert", {
            "revision": row.revision, "enrolled_on": "2026-11-10",
        }), 201)
        self.assertEqual(converted["status"], "enrolled")
        enrollment = Enrollment.objects.get(school=self.school)
        self.assertEqual(enrollment.classroom.name, "Seconde S")
        self.assertEqual(enrollment.student.student_code[:4], "YEM-")
        self.assertEqual(StudentGuardian.objects.filter(student=enrollment.student).count(), 1)
        self.assertEqual(Enrollment.objects.filter(student=enrollment.student).count(), 1)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/students"
        ).status_code, 200)

        # Proviseur voit l'inscription ; vie scolaire voit l'élève dans un appel,
        # enseignant uniquement dans une classe à laquelle il est affecté.
        self.login(self.proviseur)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/students"
        ).status_code, 200)
        session = AttendanceSession.objects.create(
            school=self.school, classroom=self.classroom, attendance_date="2026-11-11",
            slot="matin", label="Appel Seconde S", created_by=self.proviseur,
        )
        teacher = get_user_model().objects.create_user("lycee2-teacher", password="Test prof 2026!")
        SchoolMember.objects.create(
            school=self.school, user=teacher,
            role=SchoolRole.objects.get(school=self.school, code="enseignant"),
        )
        record = StaffRecord.objects.create(
            school=self.school, account=teacher, staff_code="PROF-SECONDE-S",
            first_name="Prof", last_name="Test", position="enseignant",
        )
        StaffAssignment.objects.create(
            school=self.school, staff=record, year=self.year, classroom=self.classroom,
            duty="enseignant",
        )
        for role_user in (self.role_users["vie_scolaire"], teacher):
            self.login(role_user)
            roster = self.client.get(
                f"/api/v1/schools/{self.school.pk}/attendance/sessions/{session.pk}"
            )
            self.assertEqual(roster.status_code, 200, roster.content)
            self.assertEqual(len(roster.json()["roster"]), 1)
            self.assertEqual(roster.json()["roster"][0]["student_code"],
                             enrollment.student.student_code)
            self.assertEqual(self.client.get(
                f"/api/v1/schools/{self.school.pk}/students"
            ).status_code, 403)

        self.login(self.role_users["etudes"])
        classes_response = self.client.get(
            f"/api/v1/schools/{self.school.pk}/academic/classes"
        )
        self.assertEqual(classes_response.status_code, 200, classes_response.content)
        self.assertTrue(any(
            c["id"] == str(self.classroom.pk) for c in classes_response.json()["classes"]
        ))
        # Le censeur des études voit la classe et les cours, pas le dossier personnel.
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/students"
        ).status_code, 403)

        # Parent gains access ONLY after the school's explicit guardian verification.
        self.login(created)
        self.assertEqual(self.client.get("/api/v1/parents/children").json()["children"], [])
        SchoolMember.objects.create(
            school=self.school, user=created,
            role=SchoolRole.objects.get(school=self.school, code="parent"),
        )
        self.login(self.proviseur)
        guardian = StudentGuardian.objects.get(student=enrollment.student)
        self.assert_success(self.post(f"schools/{self.school.pk}/parent-links", {
            "guardian": str(guardian.pk), "username": parent_username,
        }), 201)
        self.login(created)
        visible = self.client.get("/api/v1/parents/children")
        self.assertEqual(visible.status_code, 200, visible.content)
        self.assertEqual(len(visible.json()["children"]), 1)
        self.assertFalse(self.client.get("/api/v1/parents/catalog").status_code >= 400)

        # Explicitly document the current limitation: these roles cannot read
        # the entire pupil file, which would leak more personal data than needed.
        for code in ("vie_scolaire", "etudes"):
            self.login(self.role_users[code])
            self.assertEqual(self.client.get(
                f"/api/v1/schools/{self.school.pk}/students"
            ).status_code, 403)
