"""PostgreSQL transaction races on synthetic school data only."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .admission_models import AdmissionApplication
from .finance_models import (
    FeeSchedule, FeeCharge, FeePayment, FeePaymentBatch,
    HistoricalFeeAdjustment, HistoricalFinancialMigration,
)
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_admission_models import FamilyChild, ParentAdmissionRequest
from .parent_payment_models import AdmissionCashReceipt
from .services import ROLE_TEMPLATES
from .student_models import Student, Enrollment


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentSchoolWritesTests(TransactionTestCase):
    def setUp(self):
        self.school = School.objects.create(
            organization=Organization.objects.create(name="Synthetic concurrency only"),
            name="École de test isolée", school_type="lycee_general",
            education_cycles=["lycee_general"])
        for code, label, permissions in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school, code=code, label=label, permissions=permissions)
        self.clients = {}
        for role, count in (("econome", 2), ("secretariat", 2), ("parent", 1), ("comptabilite", 2)):
            self.clients[role] = []
            for i in range(count):
                user = get_user_model().objects.create_user(username=f"race-{role}-{i}", password="Yem-Only-Synthetic-Race-2026!")
                SchoolMember.objects.create(school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code=role))
                client = Client(enforce_csrf_checks=True)
                client.force_login(user)
                token = client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
                self.clients[role].append((client, token, user))
        self.year = AcademicYear.objects.create(school=self.school, code="2026", name="2026–2027",
            start_date="2026-09-01", end_date="2027-07-31", status="current")
        cycle = AcademicCycle.objects.create(school=self.school, code="lycee_general", name="Lycée")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="seconde", name="Seconde")
        self.room = AcademicClass.objects.create(school=self.school, year=self.year, level=level,
            code="seconde-s", name="Seconde S", capacity=30)
        student = Student.objects.create(school=self.school, student_code="RACE-001",
            first_name="Fictif", last_name="Test")
        self.enrollment = Enrollment.objects.create(school=self.school, student=student,
            year=self.year, classroom=self.room, enrolled_on="2026-09-15")
        schedule = FeeSchedule.objects.create(school=self.school, year=self.year, code="inscription",
            label="Inscription", amount=Decimal("100000"), currency="XAF")
        self.charge = FeeCharge.objects.create(school=self.school, enrollment=self.enrollment, schedule=schedule,
            label=schedule.label, amount=schedule.amount, currency=schedule.currency)
        self.root = f"/api/v1/schools/{self.school.pk}/"

    def race(self, requests):
        barrier = Barrier(len(requests), timeout=15)

        def send(entry):
            client_data, route, payload = entry
            client, token, _user = client_data
            close_old_connections()
            try:
                barrier.wait()
                if route.startswith("imports/finance/"):
                    response = client.post(self.root + route, payload, HTTP_X_CSRFTOKEN=token)
                else:
                    response = client.post(
                        self.root + route, json.dumps(payload), content_type="application/json",
                        HTTP_X_CSRFTOKEN=token,
                    )
                return response.status_code, response.content
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(requests)) as pool:
            results = list(pool.map(send, requests))
        return sorted(x[0] for x in results), results

    def unit(self, amount, key=None):
        return {"charge": str(self.charge.pk), "amount": str(amount), "method": "especes",
                "reference": "RACE-TEST", "paid_on": timezone.localdate().isoformat(),
                "idempotency_key": str(key or uuid.uuid4())}

    def batch(self, amount, key):
        item = self.unit(amount, key)
        del item["charge"], item["amount"]
        return {**item, "enrollment": str(self.enrollment.pk),
                "lines": [{"charge": str(self.charge.pk), "amount": str(amount)}]}

    def historical_payload(self, amount):
        return {
            "file": SimpleUploadedFile(
                "historique-fictif.csv", f"Matricule;Montant\nRACE-001;{amount}".encode(),
            ),
            "year": str(self.year.pk),
            "cutoff": timezone.localdate().isoformat(),
            "mapping": json.dumps({
                "student_code": 0,
                "amounts": [{"column": 1, "schedule": str(self.charge.schedule_id)}],
            }),
        }

    def open_historical_year(self):
        today = timezone.localdate()
        AcademicYear.objects.filter(pk=self.year.pk).update(
            start_date=today - timedelta(days=90), end_date=today + timedelta(days=90),
        )

    def prepare_historical_batch(self, amount):
        client, token, _ = self.clients["econome"][0]
        response = client.post(
            self.root + "imports/finance/prepare", self.historical_payload(amount),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["batch"]

    def test_concurrent_historical_prepare_reuses_one_batch(self):
        self.open_historical_year()
        codes, results = self.race([
            (client, "imports/finance/prepare", self.historical_payload(40000))
            for client in self.clients["econome"]
        ])
        self.assertEqual(codes, [200, 200], results)
        responses = [json.loads(body) for _, body in results]
        self.assertEqual(responses[0]["batch"], responses[1]["batch"])
        self.assertEqual(sorted(body["idempotent"] for body in responses), [False, True])
        batch = HistoricalFinancialMigration.objects.get()
        self.assertEqual(batch.entries.count(), 1)
        self.assertFalse(HistoricalFeeAdjustment.objects.exists())
        self.assertFalse(FeePayment.objects.exists())

    def test_overlapping_historical_approvals_record_only_one_credit(self):
        self.open_historical_year()
        batches = [self.prepare_historical_batch(amount) for amount in (40000, 50000)]
        codes, results = self.race([
            (client, f"imports/finance/{batch}/approve", {"reason": "Justificatif fictif"})
            for client, batch in zip(self.clients["comptabilite"], batches, strict=True)
        ])
        self.assertEqual(codes, [200, 422], results)
        credit = HistoricalFeeAdjustment.objects.get()
        self.assertEqual(credit.charge_id, self.charge.pk)
        self.assertIn(credit.amount, (Decimal("40000"), Decimal("50000")))
        self.assertEqual(HistoricalFinancialMigration.objects.filter(status="approved").count(), 1)
        self.assertEqual(HistoricalFinancialMigration.objects.filter(status="prepared").count(), 1)
        self.assertFalse(FeePayment.objects.exists())

    def test_historical_approval_and_payment_cannot_overcredit_a_charge(self):
        self.open_historical_year()
        batch = self.prepare_historical_batch(40000)
        codes, results = self.race([
            (self.clients["comptabilite"][0], f"imports/finance/{batch}/approve",
             {"reason": "Justificatif fictif"}),
            (self.clients["econome"][1], "finance/payments", self.unit(70000)),
        ])
        self.assertIn(codes, ([200, 422], [201, 422]), results)
        self.assertEqual(HistoricalFeeAdjustment.objects.count() + FeePayment.objects.count(), 1)
        from .finance_views import cleared_total
        self.assertIn(cleared_total(self.charge), (Decimal("40000"), Decimal("70000")))

    def test_same_payment_key_replayed_once(self):
        payload = self.unit(50000)
        codes, results = self.race([(c,"finance/payments",payload) for c in self.clients["econome"]])
        self.assertEqual(codes, [200,201], results)
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(FeePayment.objects.get().amount, Decimal("50000"))

    def test_distinct_keys_cannot_overpay(self):
        codes, results = self.race([(c,"finance/payments",self.unit(70000)) for c in self.clients["econome"]])
        self.assertEqual(codes, [201,422], results)
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(FeePayment.objects.get().amount, Decimal("70000"))

    def test_shared_key_between_unit_and_batch(self):
        key = uuid.uuid4()
        codes, results = self.race([
            (self.clients["econome"][0],"finance/payments",self.unit(50000,key)),
            (self.clients["econome"][1],"finance/batches",self.batch(50000,key)),
        ])
        self.assertEqual(codes, [201,409], results)
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(FeePayment.objects.get().amount, Decimal("50000"))
        self.assertLessEqual(FeePaymentBatch.objects.count(), 1)

    def test_same_admission_cash_and_conversion_twice(self):
        parent = self.clients["parent"][0][2]
        app = AdmissionApplication.objects.create(
            school=self.school, year=self.year, classroom=self.room,
            first_name="FICTIF", last_name="ADMISSION", guardian_name="Parent test",
            guardian_relationship="Parent", guardian_phone="+24107123456",
            source="parent_mobile", submitted_by=parent, status="accepted")
        child = FamilyChild.objects.create(owner=parent, first_name=app.first_name, last_name=app.last_name)
        link = ParentAdmissionRequest.objects.create(owner=parent, child=child, application=app,
            payment_choice="cash", fee_amount_xaf=2500)
        payment = {"reference":"RACE-ADMISSION-001", "received_on":"2026-11-10",
                   "received_cash":True, "acknowledge_demo":False, "expected_amount_xaf":2500}
        codes, results = self.race([(c, f"admission-cash/{link.pk}/confirm", payment)
                                    for c in self.clients["econome"]])
        self.assertEqual(codes, [200,201], results)
        self.assertEqual(AdmissionCashReceipt.objects.filter(application=app).count(),1)
        app.refresh_from_db()
        conversion={"revision":app.revision,"enrolled_on":"2026-11-10"}
        codes, results = self.race([(c, f"admissions/{app.pk}/convert", conversion)
                                    for c in self.clients["secretariat"]])
        self.assertEqual(codes, [200,201], results)
        app.refresh_from_db()
        self.assertIsNotNone(app.enrollment_id)
        self.assertEqual(Student.objects.count(),2)
        self.assertEqual(Enrollment.objects.count(),2)
        self.assertEqual(AdmissionCashReceipt.objects.filter(application=app).count(),1)
