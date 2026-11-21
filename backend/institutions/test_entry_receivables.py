"""Conservative categorised receivables: no capital or payment mutation."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .entry_income import fee_entries_by_category
from .entry_receivables import category_receivables
from .finance_models import FeeCharge, FeePayment, FeePaymentVoid, FeeSchedule
from .models import Organization, School, SchoolSetting
from .student_models import Enrollment, Student
from .entry_category_policy import POLICY_SCOPE


class ReceivableCategoryTests(TestCase):
    def setUp(self):
        self.day = timezone.localdate()
        self.user = get_user_model().objects.create_user(username="rec-decl", password="Secure-2026!")
        self.school = School.objects.create(organization=Organization.objects.create(name="Campus A"), name="Campus A")
        self.foreign = School.objects.create(organization=Organization.objects.create(name="Campus B"), name="Campus B")
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date=self.day - timedelta(days=100), end_date=self.day + timedelta(days=200))
        cycle = AcademicCycle.objects.create(school=self.school, code="primary", name="Primaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        cls = AcademicClass.objects.create(
            school=self.school, year=self.year, level=level, code="A", name="Classe A")
        pupil = Student.objects.create(school=self.school, first_name="Test", last_name="Secret")
        self.enrollment = Enrollment.objects.create(
            school=self.school, year=self.year, student=pupil, classroom=cls,
            enrolled_on=self.day-timedelta(days=30))
        self.tuition = self.charge("SCOL-202611", "50000", "10000", self.day-timedelta(days=5))
        self.extras = self.charge("transport-1", "12000", "0", self.day+timedelta(days=5))
        self.undated = self.charge("frais-inconnus", "3000", "0", None)
        self.demo = self.charge("DEMO-tarif", "4000", "0", self.day-timedelta(days=1))
        self.payment(self.tuition, "15000", "especes")
        self.payment(self.tuition, "5000", "simulation")
        voided = self.payment(self.tuition, "3000", "especes")
        FeePaymentVoid.objects.create(
            school=self.school, payment=voided, reason="Erreur", approved_by=self.user)

    def charge(self, code, amount, discount, due):
        schedule = FeeSchedule.objects.create(
            school=self.school, year=self.year, code=code, label=code, amount=Decimal(amount),
            due_date=due, currency="XAF")
        return FeeCharge.objects.create(
            school=self.school, enrollment=self.enrollment, schedule=schedule,
            label=code, currency="XAF", amount=Decimal(amount),
            scholarship_discount=Decimal(discount), due_date=due)

    def payment(self, charge, value, method):
        return FeePayment.objects.create(
            school=self.school, charge=charge, amount=Decimal(value),
            currency="XAF", method=method, paid_on=self.day,
            recorded_by=self.user, idempotency_key=uuid4())

    def test_due_buckets_and_no_double_count_or_demo(self):
        report=category_receivables(self.school,self.year,self.day)
        rows={r["category"]:r for r in report["rows"]}
        self.assertEqual(set(rows),{"scolarite","extrascolaire","a_classer"})
        self.assertEqual(rows["scolarite"]["billed_net"],"40000.00")
        self.assertEqual(rows["scolarite"]["paid_declared"],"15000.00")
        self.assertEqual(rows["scolarite"]["outstanding"],"25000.00")
        self.assertEqual(rows["scolarite"]["overdue"],"25000.00")
        self.assertEqual(rows["scolarite"]["future"],"0.00")
        self.assertEqual(rows["extrascolaire"]["future"],"12000.00")
        self.assertEqual(rows["extrascolaire"]["overdue"],"0.00")
        self.assertEqual(rows["a_classer"]["without_due_date"],"3000.00")
        self.assertFalse(report["revenue_certified"])
        self.assertEqual(sum(Decimal(v["outstanding"]) for v in rows.values()),Decimal("40000"))
        joined=fee_entries_by_category(self.school,self.year,self.day)
        self.assertEqual(joined["receivables"]["rows"],report["rows"])
        self.assertEqual(FeePayment.objects.filter(school=self.school).count(),3)

    def test_school_specific_override_and_a_second_school_are_isolated(self):
        SchoolSetting.objects.create(
            school=self.school, scope_key=POLICY_SCOPE,
            scope={"module":"income"},
            values={"assignments":{str(self.undated.schedule_id):"autre_scolaire"}})
        rows={r["category"]:r for r in category_receivables(self.school,self.year,self.day)["rows"]}
        self.assertIn("autre_scolaire",rows)
        self.assertNotIn("a_classer",rows)
        self.assertEqual(rows["autre_scolaire"]["without_due_date"],"3000.00")
        self.assertEqual(category_receivables(self.foreign,self.year,self.day)["rows"],[])
        self.assertEqual(category_receivables(self.school,None,self.day)["rows"],[])

    def test_future_dated_payments_do_not_reduce_current_debt(self):
        self.payment(self.tuition, "8000", "especes")
        later=FeePayment.objects.filter(charge=self.tuition,method="especes").order_by("-created_at").first()
        FeePayment.objects.filter(pk=later.pk).update(paid_on=self.day+timedelta(days=1))
        rows={r["category"]:r for r in category_receivables(self.school,self.year,self.day)["rows"]}
        self.assertEqual(rows["scolarite"]["outstanding"],"25000.00")
