"""Regression coverage for consolidated school receipts and transaction rollback."""
import json
import uuid
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

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
            "paid_on": timezone.localdate().isoformat(), "idempotency_key": idem or str(uuid.uuid4()),
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
            "reference": "TEST", "paid_on": timezone.localdate().isoformat(),
            "idempotency_key": str(uuid.uuid4()),
        }
        response = self.client.post(self.base + "payments", json.dumps(body),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(FeePayment.objects.get(pk=response.json()["id"]).batch)
        batch = self.send(self.payload(("50000", "20000")))
        self.assertEqual(batch.status_code, 422)

    def post_closing(self, counted, note=""):
        return self.client.post(self.base+"cash/closings", json.dumps({
            "day": timezone.localdate().isoformat(), "currency": "XAF",
            "counted": counted, "note": note,
        }), content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

    def approve_closing(self, closing_id, note=""):
        return self.client.post(self.base+"cash/closings/"+closing_id+"/approve",
            json.dumps({"note": note}), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token)

    def create_director(self):
        User=get_user_model()
        director=User.objects.create_user("batch-fin-director", password="Good Testing Pass 2026!")
        SchoolMember.objects.create(
            school=self.school,user=director,
            role=SchoolRole.objects.get(school=self.school, code="direction"),
        )
        return director

    def test_cash_close_blocks_new_cash_but_allows_idempotent_replay(self):
        original=self.payload()
        receipt=self.send(original)
        self.assertEqual(receipt.status_code,201,receipt.content)
        closing=self.post_closing("30000")
        self.assertEqual(closing.status_code,201,closing.content)
        self.assertEqual(closing.json()["expected"],"30000.00")
        self.assertEqual(closing.json()["difference"],"0.00")
        self.assertEqual(self.send(original).status_code,200)
        self.assertEqual(self.send(self.payload(("100", "100"))).status_code,409)
        self.assertEqual(self.post_closing("30000").status_code,409)
        single={
            "charge":str(self.charges[0].pk),"amount":"100",
            "method":"especes","reference":"","paid_on":timezone.localdate().isoformat(),
            "idempotency_key":str(uuid.uuid4()),
        }
        response=self.client.post(self.base+"payments", json.dumps(single),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code,409,response.content)
        self.assertEqual(FeePayment.objects.count(),2)

    def test_cash_variance_requires_justification_and_separate_approver(self):
        self.assertEqual(self.post_closing("1000").status_code,422)
        submitted=self.post_closing("1000","Comptage manuel différent du journal")
        self.assertEqual(submitted.status_code,201,submitted.content)
        data=submitted.json()
        self.assertEqual(data["difference"],"1000.00")
        director=self.create_director()
        self.login(director)
        self.assertEqual(self.approve_closing(data["id"],"trop court").status_code,422)
        approved=self.approve_closing(data["id"],"Écart vérifié, justification consignée dans le journal")
        self.assertEqual(approved.status_code,200,approved.content)
        self.assertEqual(approved.json()["status"],"approved")
        self.assertEqual(approved.json()["approved_by"],director.username)
        self.assertEqual(self.approve_closing(data["id"],"Encore").status_code,409)

    def test_cashier_cannot_approve_own_closure_even_as_director(self):
        director=self.create_director()
        self.login(director)
        submitted=self.post_closing("0")
        self.assertEqual(submitted.status_code,201,submitted.content)
        self.assertEqual(self.approve_closing(submitted.json()["id"]).status_code,403)

    def test_cash_closing_excludes_mobile_and_notes_post_closing_voids(self):
        original=self.payload()
        self.assertEqual(self.send(original).status_code,201)
        external=self.payload(("100", "200"))
        external["method"]="airtel_money"
        self.assertEqual(self.send(external).status_code,201)
        submitted=self.post_closing("30000")
        self.assertEqual(submitted.status_code,201,submitted.content)
        self.assertEqual(submitted.json()["expected"],"30000.00")
        director=self.create_director()
        self.login(director)
        payment_id=FeePayment.objects.get(batch__idempotency_key=original["idempotency_key"],charge=self.charges[0]).pk
        response=self.client.post(self.base+"payments/"+str(payment_id)+"/void", json.dumps({
            "reason":"Annulation ultérieure avec justificatif disponible",
        }),content_type="application/json",HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code,201,response.content)
        closings=self.client.get(self.base+"cash/closings")
        self.assertEqual(closings.status_code,200)
        self.assertEqual(closings.json()["closings"][0]["adjustment_since_submission"],"-10000.00")

    def test_teacher_cannot_create_or_approve_cash_closings(self):
        director=self.create_director()
        self.login(self.teacher)
        self.assertEqual(self.post_closing("0").status_code,403)
        self.assertEqual(self.client.get(self.base+"cash/closings").status_code,403)
        self.login(director)
        submitted=self.post_closing("0")
        self.login(self.teacher)
        self.assertEqual(self.approve_closing(submitted.json()["id"]).status_code,403)
