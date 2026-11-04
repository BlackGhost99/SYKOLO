"""Regression coverage for consolidated school receipts and transaction rollback."""
import json
import uuid
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment, FeePaymentBatch
from .models import Organization, School, SchoolRole, SchoolMember
from .services import ROLE_TEMPLATES
from .student_models import Student, Enrollment


class MultiFeeReceiptTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.cashier = User.objects.create_user("batch-fin-cashier", password="Good Testing Pass 2026!")
        self.teacher = User.objects.create_user("batch-fin-teacher", password="Good Testing Pass 2026!")
        self.school = School.objects.create(
            organization=Organization.objects.create(name="YEM finance groupe"),
            name="École primaire test",
        )
        self.other_school = School.objects.create(
            organization=Organization.objects.create(name="Autre établissement"),
            name="Collège privé test",
        )
        for school in (self.school, self.other_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        for user, role in ((self.cashier, "comptabilite"), (self.teacher, "enseignant")):
            SchoolMember.objects.create(school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=role))
        year = AcademicYear.objects.create(
            school=self.school, code="2026-27", name="Année 2026–27",
            start_date="2026-09-01", end_date="2027-07-30",
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="cm1", name="CM1")
        classroom = AcademicClass.objects.create(
            school=self.school, year=year, level=level, code="cm1a", name="CM1 A",
        )
        student = Student.objects.create(school=self.school, student_code="REC-01",
                                         first_name="Sonia", last_name="Essai")
        self.enrollment = Enrollment.objects.create(
            school=self.school, student=student, year=year,
            classroom=classroom, enrolled_on="2026-09-01",
        )
        self.other_enrollment = Enrollment.objects.create(
            school=self.school,
            student=Student.objects.create(school=self.school, student_code="REC-02",
                                           first_name="Michel", last_name="Essai"),
            year=year, classroom=classroom, enrolled_on="2026-09-01",
        )
        self.charges = []
        for code, amount, currency in (
            ("inscription", "50000", "XAF"),
            ("tranche", "120000", "XAF"),
            ("devise", "10000", "EUR"),
        ):
            schedule = FeeSchedule.objects.create(
                school=self.school, year=year, classroom=classroom,
                scope_key=str(classroom.pk), code=code, label=code,
                amount=amount, currency=currency,
            )
            self.charges.append(FeeCharge.objects.create(
                school=self.school, enrollment=self.enrollment, schedule=schedule,
                label=code, amount=amount, currency=currency,
            ))
        self.base = f"/api/v1/schools/{self.school.pk}/finance/"
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.cashier)

    def login(self, user):
        self.client.force_login(user)
        self.token = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def payload(self, amounts=("10000", "20000"), *, idem=None):
        return {
            "enrollment": str(self.enrollment.pk),
            "lines": [
                {"charge": str(charge.pk), "amount": amount}
                for charge, amount in zip(self.charges, amounts)
            ],
            "method": "especes", "reference": "CAISSE-GABON-001",
            "paid_on": "2026-11-04", "idempotency_key": idem or str(uuid.uuid4()),
        }

    def send(self, data):
        return self.client.post(self.base + "batches", json.dumps(data),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

    def test_atomic_two_fee_payment_and_single_receipt(self):
        response = self.send(self.payload())
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["total"], "30000.00")
        self.assertEqual(data["currency"], "XAF")
        self.assertEqual(len(data["payments"]), 2)
        self.assertEqual(FeePayment.objects.filter(batch_id=data["id"]).count(), 2)
        self.assertEqual(self.client.get(self.base + "batches/" + data["id"]).status_code, 200)
        pdf = self.client.get(self.base + "batches/" + data["id"] + "/receipt")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(pdf["Cache-Control"], "private, no-store")

    def test_bad_line_rolls_back_every_payment(self):
        too_much = self.send(self.payload(("10000", "150000")))
        self.assertEqual(too_much.status_code, 422, too_much.content)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(FeePaymentBatch.objects.count(), 0)

    def test_replay_and_key_conflict_do_not_duplicate(self):
        key = str(uuid.uuid4())
        original = self.payload(idem=key)
        one = self.send(original)
        self.assertEqual(one.status_code, 201, one.content)
        again = self.send(original)
        self.assertEqual(again.status_code, 200, again.content)
        self.assertEqual(again.json()["id"], one.json()["id"])
        different = self.payload(("10000", "10000"), idem=key)
        self.assertEqual(self.send(different).status_code, 409)
        self.assertEqual(FeePaymentBatch.objects.count(), 1)
        self.assertEqual(FeePayment.objects.count(), 2)

    def test_cross_school_enrollment_and_mixed_currency_rejected(self):
        cross_school = self.payload()
        cross_school["lines"][1]["charge"] = str(uuid.uuid4())
        self.assertEqual(self.send(cross_school).status_code, 404)
        another = self.payload()
        another["enrollment"] = str(self.other_enrollment.pk)
        self.assertEqual(self.send(another).status_code, 404)
        mixed = self.payload()
        mixed["lines"][1]["charge"] = str(self.charges[2].pk)
        self.assertEqual(self.send(mixed).status_code, 422)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_access_and_invalid_input(self):
        data = self.payload()
        duplicate = self.payload()
        duplicate["lines"][1]["charge"] = duplicate["lines"][0]["charge"]
        self.assertEqual(self.send(duplicate).status_code, 422)
        self.assertEqual(self.send(self.payload(("0", "200"))).status_code, 422)
        self.login(self.teacher)
        self.assertEqual(self.send(data).status_code, 403)
        self.assertEqual(self.client.get(self.base + "batches/" + str(uuid.uuid4())).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "batches/" + str(uuid.uuid4())).status_code, 401)
        self.assertEqual(FeePaymentBatch.objects.count(), 0)

    def test_legacy_single_payment_unaffected(self):
        charge = self.charges[0]
        body = {
            "charge": str(charge.pk), "amount": "2500", "method": "especes",
            "reference": "TEST", "paid_on": "2026-11-04",
            "idempotency_key": str(uuid.uuid4()),
        }
        response = self.client.post(self.base + "payments", json.dumps(body),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(FeePayment.objects.get(pk=response.json()["id"]).batch)
        batch = self.send(self.payload(("50000", "20000")))
        self.assertEqual(batch.status_code, 422)
