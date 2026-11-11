"""Financial ledger: fees, staged/partial payments, separation of duties and privacy."""
import json
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment, FeePaymentVoid
from .models import Organization, School, SchoolRole, SchoolMember
from .services import ROLE_TEMPLATES
from .student_models import Student, Enrollment


class FinanceLedgerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="dir-fin", password="Strong director password 2026!")
        self.accountant = User.objects.create_user(username="cashier-fin", password="Strong accountant password 2026!")
        self.teacher = User.objects.create_user(username="teacher-fin", password="Strong teacher password 2026!")
        self.stranger = User.objects.create_user(username="visitor-fin", password="Strong visitor password 2026!")
        organization = Organization.objects.create(name="Groupe financier fictif")
        self.school = School.objects.create(organization=organization, name="École financière A")
        self.other_school = School.objects.create(organization=organization, name="École financière B")
        for school in (self.school, self.other_school):
            for code, name, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=name, permissions=permissions)
        for user, role in [
            (self.director, "tarification"),
            (self.accountant, "econome"),
            (self.teacher, "enseignant"),
        ]:
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=role),
            )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="Année", start_date="2026-09-01", end_date="2027-07-31",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="secondaire", name="Secondaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="6a", name="6A",
        )
        student = Student.objects.create(
            school=self.school, student_code="FIN-1", first_name="Lina", last_name="Essai",
        )
        self.enrollment = Enrollment.objects.create(
            school=self.school, student=student, year=self.year,
            classroom=self.classroom, enrolled_on="2026-09-08",
        )
        self.controller = User.objects.create_user(username="controller-fin", password="Strong controller password 2026!")
        SchoolMember.objects.create(school=self.school, user=self.controller, role=SchoolRole.objects.get(school=self.school, code="comptabilite"))
        SchoolMember.objects.get(school=self.school, user=self.director).additional_roles.add(SchoolRole.objects.get(school=self.school, code="econome"))
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base = "/api/v1/schools/" + str(self.school.pk) + "/finance/"

    def login(self, user):
        self.client.force_login(user)
        self.token = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, path, data, method="post"):
        return getattr(self.client, method)(
            self.base + path, json.dumps(data), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )

    def schedule(self, amount="120000", code="inscription", classroom=None, currency="XAF"):
        data = {"year": str(self.year.pk), "code": code, "label": "Frais scolaires", "amount": amount,
                "currency": currency, "due_date": "2026-10-15"}
        if classroom is not None:
            data["classroom"] = classroom
        r = self.post("schedules", data)
        self.assertEqual(r.status_code, 201, r.content.decode())
        return r.json()

    def charge(self, schedule):
        r = self.post("charges", {
            "enrollment": str(self.enrollment.pk), "schedule": schedule["id"],
        })
        self.assertEqual(r.status_code, 201, r.content.decode())
        return r.json()

    def pay(self, charge, amount, *, idem=None, method="especes", reference="CAISSE-2026"):
        return self.post("payments", {
            "charge": charge["id"], "amount": amount, "method": method,
            "reference": reference, "paid_on": "2026-11-02",
            "idempotency_key": idem or str(uuid.uuid4()),
        })

    def test_reschedule_applies_to_unpaid_tranches_without_rewriting_settled_charges(self):
        unpaid = self.schedule(code="tranche-1")
        settled = self.schedule(code="tranche-2")
        unpaid_charge = self.charge(unpaid)
        settled_charge = self.charge(settled)
        self.assertEqual(self.pay(unpaid_charge, "20000").status_code, 201)
        self.assertEqual(self.pay(settled_charge, "120000").status_code, 201)
        for schedule, expected in ((unpaid, 1), (settled, 0)):
            result = self.post("schedules/" + schedule["id"], {
                "due_date": "2026-12-15", "revision": schedule["revision"],
                "reschedule_open_charges": True,
            }, method="patch")
            self.assertEqual(result.status_code, 200, result.content.decode())
            self.assertEqual(result.json()["rescheduled_charges"], expected)
        self.assertEqual(self.client.get(self.base + "charges/" + unpaid_charge["id"]).json()["due_date"], "2026-12-15")
        self.assertEqual(self.client.get(self.base + "charges/" + settled_charge["id"]).json()["due_date"], "2026-10-15")
        self.login(self.accountant)
        result = self.post("schedules/" + unpaid["id"], {
            "due_date": "2026-12-16", "revision": unpaid["revision"] + 1,
            "reschedule_open_charges": True,
        }, method="patch")
        self.assertEqual(result.status_code, 403)

    def test_payment_lifecycle_partial_receipt_void_and_balance(self):
        schedule = self.schedule()
        charge = self.charge(schedule)
        first = self.pay(charge, "45000.50")
        self.assertEqual(first.status_code, 201, first.content.decode())
        first = first.json()
        self.assertEqual(first["amount"], "45000.50")
        self.assertEqual(self.client.get(self.base + "charges/" + charge["id"]).json()["balance"], "74999.50")
        self.assertEqual(self.client.get(self.base + "enrollments/" + str(self.enrollment.pk) + "/statement").json()["totals"]["XAF"],
            {"billed": "120000.00", "paid": "45000.50", "balance": "74999.50"})
        second = self.pay(charge, "74999.50")
        self.assertEqual(second.status_code, 201, second.content.decode())
        self.assertEqual(self.client.get(self.base + "charges/" + charge["id"]).json()["balance"], "0.00")
        self.assertEqual(self.pay(charge, "1.00").status_code, 422)
        receipt = self.client.get(self.base + "payments/" + first["id"] + "/receipt")
        self.assertEqual(receipt.status_code, 200)
        self.assertEqual(receipt["Cache-Control"], "private, no-store")
        self.assertTrue(receipt.content.startswith(b"%PDF-"))
        self.login(self.accountant)
        self.assertEqual(self.post("payments/" + first["id"] + "/void", {"reason": "Erreur de saisie documentée"}).status_code, 403)
        self.login(self.controller)
        voided = self.post("payments/" + first["id"] + "/void", {"reason": "Erreur de caisse vérifiée par la direction."})
        self.assertEqual(voided.status_code, 201, voided.content.decode())
        self.assertEqual(self.client.get(self.base + "charges/" + charge["id"]).json()["balance"], "45000.50")
        self.assertEqual(self.post("payments/" + first["id"] + "/void", {"reason": "Annulation répétée."}).status_code, 409)
        self.assertEqual(self.client.get(self.base + "payments?charge=" + charge["id"]).json()["payments"][0]["voided"], True)
        self.assertEqual(FeePayment.objects.count(), 2)
        self.assertEqual(FeePaymentVoid.objects.count(), 1)

    def test_idempotency_replay_never_double_counts(self):
        charge = self.charge(self.schedule())
        key = str(uuid.uuid4())
        one = self.pay(charge, 1000, idem=key)
        self.assertEqual(one.status_code, 201, one.content.decode())
        same = self.pay(charge, 1000, idem=key)
        self.assertEqual(same.status_code, 200, same.content.decode())
        self.assertEqual(same.json()["id"], one.json()["id"])
        self.assertEqual(self.pay(charge, 2000, idem=key).status_code, 409)
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(self.client.get(self.base + "charges/" + charge["id"]).json()["paid"], "1000.00")

    def test_schedule_revision_immutable_charge_and_class_scope(self):
        schedule = self.schedule()
        charge = self.charge(schedule)
        changed = self.post("schedules/" + schedule["id"], {
            "revision": 1, "amount": "135000", "label": "Nouveau tarif",
        }, method="patch")
        self.assertEqual(changed.status_code, 200, changed.content.decode())
        self.assertEqual(changed.json()["revision"], 2)
        self.assertEqual(changed.json()["amount"], "135000.00")
        self.assertEqual(self.client.get(self.base + "charges/" + charge["id"]).json()["amount"], "120000.00")
        self.assertEqual(self.client.get(self.base + "charges/" + charge["id"]).json()["label"], "Frais scolaires")
        self.assertEqual(self.post("schedules/" + schedule["id"], {
            "revision": 1, "label": "Écrasement",
        }, method="patch").status_code, 409)
        self.assertIn(self.post("charges", {
            "enrollment": str(self.enrollment.pk), "schedule": schedule["id"],
        }).status_code, (409, 422))
        self.assertEqual(self.post("charges/" + charge["id"], {}, method="delete").status_code, 405)

    def test_invalid_amount_currency_methods_and_overpayment(self):
        for invalid in ("0", "-1", "1.123", "10000000000", 0.1, True, "NaN"):
            self.assertEqual(self.post("schedules", {
                "year": str(self.year.pk), "code": "frais", "label": "Frais",
                "amount": invalid, "currency": "XAF",
            }).status_code, 422, str(invalid))
        self.assertEqual(self.post("schedules", {
            "year": str(self.year.pk), "code": "frais", "label": "Frais",
            "amount": "1000", "currency": "xaf",
        }).status_code, 422)
        charge = self.charge(self.schedule("1000"))
        for invalid in ("0", "-1", "0.001", "NaN", 0.5, True):
            self.assertEqual(self.pay(charge, invalid).status_code, 422, str(invalid))
        self.assertEqual(self.pay(charge, "1001").status_code, 422)
        self.assertEqual(self.pay(charge, "500").status_code, 201)
        self.assertEqual(self.pay(charge, "501").status_code, 422)

    def test_finance_role_can_record_but_cannot_void_or_change_permissions(self):
        charge = self.charge(self.schedule())
        self.login(self.accountant)
        self.assertEqual(self.client.get(self.base + "schedules").status_code, 200)
        self.assertEqual(self.pay(charge, "1200").status_code, 201)
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base + "schedules").status_code, 403)
        self.assertEqual(self.client.get(self.base + "charges").status_code, 403)
        self.assertEqual(self.pay(charge, "200").status_code, 403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base + "charges").status_code, 404)
        self.assertEqual(self.client.get(self.base + "payments?charge=" + charge["id"]).status_code, 404)
        self.assertEqual(self.client.get(self.base + "enrollments/" + str(self.enrollment.pk) + "/statement").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/schools/" + str(self.other_school.pk) + "/finance/charges").status_code, 404)

    def test_other_school_year_and_class_cannot_be_invoiced(self):
        other_year = AcademicYear.objects.create(
            school=self.other_school, code="2026-2027", name="Autre",
            start_date="2026-09-01", end_date="2027-07-31",
        )
        self.assertEqual(self.post("schedules", {
            "year": str(other_year.pk), "code": "frais", "label": "Autre",
            "amount": "1000", "currency": "XAF",
        }).status_code, 422)
        other_cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        other_level = AcademicLevel.objects.create(school=self.school, cycle=other_cycle, code="cm2", name="CM2")
        other_class = AcademicClass.objects.create(school=self.school, year=self.year, level=other_level, code="cm2", name="CM2")
        schedule = self.schedule("5000", code="cm2", classroom=str(other_class.pk))
        self.assertEqual(self.post("charges", {
            "enrollment": str(self.enrollment.pk), "schedule": schedule["id"],
        }).status_code, 422)

    def test_anon_csrf_and_no_external_payment_claim(self):
        self.assertEqual(self.client.post(self.base + "schedules", json.dumps({"code": "x"}), content_type="application/json").status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "schedules").status_code, 401)
