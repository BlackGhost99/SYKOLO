"""Parcours simplifiés : fiche de renseignement, inscriptions par classe, classes rapides, facturation."""
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment
from .models import Organization, School, SchoolRole, SchoolMember, SchoolAdminPolicy
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment


class RegistrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="dir-reg", password="Strong director password 2026!")
        self.secretary = User.objects.create_user(username="sec-reg", password="Strong secretary password 2026!")
        self.teacher = User.objects.create_user(username="tea-reg", password="Strong teacher password 2026!")
        self.biller = User.objects.create_user(username="billing-reg", password="Strong billing password 2026!")
        org = Organization.objects.create(name="Groupe inscriptions")
        self.school = School.objects.create(organization=org, name="École A")
        self.other = School.objects.create(organization=org, name="École B")
        for school in (self.school, self.other):
            for code, name, perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=name, permissions=perms)
        for user, role in ((self.director, "direction"), (self.secretary, "secretariat"), (self.teacher, "enseignant")):
            SchoolMember.objects.create(school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code=role))
        # Fee assessment is authorized for a tariff manager, not for direction by default.
        billing_member = SchoolMember.objects.create(
            school=self.school, user=self.biller,
            role=SchoolRole.objects.get(school=self.school, code="secretariat"),
        )
        billing_member.additional_roles.add(SchoolRole.objects.get(school=self.school, code="tarification"))
        today = timezone.localdate()
        self.year = AcademicYear.objects.create(school=self.school, code="y", name="2026-2027",
                                                start_date=today - timedelta(days=30), end_date=today + timedelta(days=300))
        cycle = AcademicCycle.objects.create(school=self.school, code="c", name="Collège")
        self.level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        self.c6a = AcademicClass.objects.create(school=self.school, year=self.year, level=self.level, code="6a", name="6e A", capacity=2)
        self.global_fee = FeeSchedule.objects.create(school=self.school, year=self.year, code="ins", label="Inscription",
                                                     amount=Decimal("50000"), currency="XAF")
        self.class_fee = FeeSchedule.objects.create(school=self.school, year=self.year, classroom=self.c6a, scope_key=str(self.c6a.pk),
                                                    code="scol", label="Scolarité 6e", amount=Decimal("150000"), currency="XAF")
        self.base = f"/api/v1/schools/{self.school.pk}/"

    def post(self, path, body):
        return self.client.post(self.base + path, json.dumps(body), content_type="application/json")

    def register_body(self, **extra):
        body = {
            "student": {"first_name": "Aaron", "last_name": "NZE", "date_of_birth": "2015-03-02", "gender": "M",
                        "place_of_birth": "Libreville", "nationality": "Gabonaise", "address": "Quartier Louis",
                        "previous_school": "École Montfort"},
            "guardians": [{"full_name": "NZE Sylvie", "relationship": "Mère", "phone": "+241 77 43 21 08",
                           "profession": "Infirmière", "address": "Quartier Louis"}],
            "enrollment": {"classroom": str(self.c6a.pk)},
        }
        body.update(extra)
        return body

    def test_manual_transfer_is_bound_to_destination_and_keeps_identity(self):
        from .models import SchoolMember, SchoolRole

        self.client.force_login(self.director)
        original = Student.objects.create(school=self.school, student_code="LOCAL-1",
            first_name="Aaron", last_name="NZE", date_of_birth="2015-03-02")
        SchoolMember.objects.create(school=self.other, user=self.director,
            role=SchoolRole.objects.get(school=self.other, code="direction"))
        source = f"/api/v1/schools/{self.school.pk}/students/{original.pk}/transfer"
        response = self.client.post(source, {"destination": str(self.other.pk)}, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        payload = self.register_body(enrollment=None, transfer_code=response.json()["transfer_code"])
        self.assertEqual(self.post("students/register", payload).status_code, 422)
        target = f"/api/v1/schools/{self.other.pk}/students/register"
        response = self.client.post(target, payload, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["student"]["matricule_yem"], original.matricule_yem)
        self.assertEqual(self.client.post(target, payload, content_type="application/json").status_code, 409)

    def test_full_registration_creates_student_guardian_enrollment_and_fees(self):
        self.client.force_login(self.biller)
        r = self.post("students/register", self.register_body())
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertRegex(d["student"]["matricule_yem"], r"^YEM-[0-9A-F]{32}$")
        self.assertEqual(d["student"]["place_of_birth"], "Libreville")
        self.assertTrue(d["guardians"][0]["is_primary"])
        self.assertEqual(d["guardians"][0]["profession"], "Infirmière")
        self.assertEqual(d["enrollment"]["classroom"], str(self.c6a.pk))
        self.assertEqual(d["charges_created"], 2)
        self.assertEqual(FeeCharge.objects.filter(enrollment_id=d["enrollment"]["id"]).count(), 2)
        # Matricules successifs uniques.
        r2 = self.post("students/register", self.register_body(student={"first_name": "Léa", "last_name": "NZE", "date_of_birth": "2016-01-01"}, enrollment=None))
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertNotEqual(r2.json()["student"]["student_code"], d["student"]["student_code"])

    def test_secretary_registers_without_fees_and_failure_rolls_back(self):
        self.client.force_login(self.secretary)
        r = self.post("students/register", self.register_body())
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["fees_skipped"])
        self.assertEqual(FeeCharge.objects.count(), 0)
        # Mauvais email du responsable : rien n'est créé.
        before = Student.objects.count()
        bad = self.register_body(guardians=[{"full_name": "X", "phone": "1", "email": "pas-un-email"}])
        self.assertEqual(self.post("students/register", bad).status_code, 422)
        self.assertEqual(Student.objects.count(), before)

    def test_capacity_and_permissions(self):
        self.client.force_login(self.director)
        for name in ("A", "B"):
            self.assertEqual(self.post("students/register", self.register_body(student={"first_name": name, "last_name": "X", "date_of_birth": "2015-01-01"})).status_code, 201)
        full = self.post("students/register", self.register_body(student={"first_name": "C", "last_name": "X", "date_of_birth": "2015-01-01"}))
        self.assertEqual(full.status_code, 422)
        self.assertIn("Capacité", full.json()["error"])
        self.client.force_login(self.teacher)
        self.assertEqual(self.post("students/register", self.register_body()).status_code, 403)
        other = f"/api/v1/schools/{self.other.pk}/students/register"
        self.client.force_login(self.director)
        self.assertEqual(self.client.post(other, json.dumps(self.register_body()), content_type="application/json").status_code, 404)

    def test_registration_respects_platform_student_limit(self):
        SchoolAdminPolicy.objects.create(school=self.school, max_students=0)
        self.client.force_login(self.secretary)
        response = self.post("students/register", self.register_body())
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 0)
        self.assertEqual(StudentGuardian.objects.filter(school=self.school).count(), 0)

    def test_quick_classes_creates_level_and_codes(self):
        self.client.force_login(self.director)
        r = self.post("academic/quick-classes", {"year": str(self.year.pk), "level_name": "CM1", "cycle_name": "Primaire",
                                                  "names": "CM1 A, CM1 B", "capacity": 35})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual([c["name"] for c in r.json()["classes"]], ["CM1 A", "CM1 B"])
        self.assertEqual(AcademicClass.objects.filter(school=self.school, level__name="CM1", capacity=35).count(), 2)
        dup = self.post("academic/quick-classes", {"year": str(self.year.pk), "level": str(self.level.pk), "names": ["6e a"]})
        self.assertEqual(dup.status_code, 409)
        self.client.force_login(self.secretary)
        self.assertEqual(self.post("academic/quick-classes", {"year": str(self.year.pk), "level": str(self.level.pk), "names": ["6e C"]}).status_code, 403)

    def test_class_enroll_and_apply_fees_and_overview(self):
        students = [Student.objects.create(school=self.school, student_code=f"S{i}", first_name="T", last_name=f"N{i}") for i in range(3)]
        self.client.force_login(self.secretary)
        r = self.post(f"classes/{self.c6a.pk}/enroll", {"students": [str(s.pk) for s in students]})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()["enrolled"]), 2)
        self.assertEqual(len(r.json()["failed"]), 1)
        self.assertEqual(self.post(f"classes/{self.c6a.pk}/apply-fees", {}).status_code, 403)
        self.client.force_login(self.biller)
        r = self.post(f"classes/{self.c6a.pk}/apply-fees", {})
        self.assertEqual(r.json()["charges_created"], 4)
        self.assertEqual(self.post(f"classes/{self.c6a.pk}/apply-fees", {}).json()["charges_created"], 0)
        charge = FeeCharge.objects.filter(enrollment__student=students[0]).first()
        FeePayment.objects.create(school=self.school, charge=charge, idempotency_key=uuid.uuid4(), amount=charge.amount,
                                  currency="XAF", method="moov_money", paid_on=timezone.localdate())
        o = self.client.get(self.base + "overview/classes").json()
        c = o["classes"][0]
        self.assertEqual((c["enrolled"], c["remaining"], c["fee_schedules"]), (2, 0, 2))
        self.assertEqual(c["finance"]["billed"], "400000.00")
        self.assertEqual(c["finance"]["partiel"], 1)
        self.assertEqual(o["unassigned_students"], 1)
        rows = {s["id"]: s for s in self.client.get(self.base + "overview/students").json()["students"]}
        self.assertEqual(rows[str(students[0].pk)]["finance"]["methods"], ["moov_money"])
        dossier = self.client.get(self.base + f"students/{students[0].pk}/dossier").json()
        self.assertEqual(dossier["enrollments"][0]["finance"]["payments"][0]["method"], "moov_money")
        self.assertEqual(dossier["enrollments"][0]["classroom_name"], "6e A")
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.base + f"students/{students[0].pk}/dossier").status_code, 403)

    def test_student_info_fields_editable(self):
        s = Student.objects.create(school=self.school, student_code="E1", first_name="A", last_name="B")
        self.client.force_login(self.secretary)
        r = self.client.patch(self.base + f"students/{s.pk}", json.dumps({"revision": 1, "nationality": "Gabonaise", "gender": "F"}),
                              content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["gender"], "F")
        bad = self.client.patch(self.base + f"students/{s.pk}", json.dumps({"revision": 2, "gender": "X"}), content_type="application/json")
        self.assertEqual(bad.status_code, 422)

    def test_school_form_is_configurable_by_secretariat(self):
        self.client.force_login(self.secretary)
        form = self.client.get(self.base + "enrollment-form").json()
        self.assertEqual(form["revision"], 0)
        config = form["config"]
        config["fields"]["place_of_birth"]["required"] = True
        config["fields"]["guardian_phone"] = {"visible": False, "required": False}
        config["custom_fields"] = [
            {"key": "religion", "label": "Confession", "type": "select", "options": ["Catholique", "Protestante", "Autre"], "required": True},
            {"key": "transport", "label": "Transport scolaire", "type": "yesno"},
        ]
        config["documents"].append({"key": "certificat_radiation", "label": "Certificat de radiation", "required": True})
        r = self.client.put(self.base + "enrollment-form", json.dumps({"config": config, "revision": 0}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        stale = self.client.put(self.base + "enrollment-form", json.dumps({"config": config, "revision": 0}), content_type="application/json")
        self.assertEqual(stale.status_code, 409)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.put(self.base + "enrollment-form", json.dumps({"config": config, "revision": 1}), content_type="application/json").status_code, 403)
        self.client.force_login(self.secretary)
        body = self.register_body(guardians=[{"full_name": "Parent"}])
        missing = self.post("students/register", body)
        self.assertEqual(missing.status_code, 422)
        self.assertIn("Confession", missing.json()["error"])
        body["student"].update(extra_fields={"religion": "Autre", "transport": True},
                               documents={"acte_naissance": True, "photos": True})
        ok = self.post("students/register", body)
        self.assertEqual(ok.status_code, 201, ok.content)
        sid = ok.json()["student"]["id"]
        dossier = self.client.get(self.base + f"students/{sid}/dossier").json()
        self.assertEqual(dossier["student"]["extra_fields"]["religion"], "Autre")
        self.assertEqual(dossier["missing_documents"], ["Certificat de radiation"])
        bad = dict(body); bad["student"] = dict(body["student"], extra_fields={"religion": "Inconnue"})
        self.assertEqual(self.post("students/register", bad).status_code, 422)
        r = self.client.patch(self.base + f"students/{sid}", json.dumps({"revision": 1, "documents": {"acte_naissance": True, "photos": True, "certificat_radiation": True}}),
                              content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get(self.base + f"students/{sid}/dossier").json()["missing_documents"], [])
