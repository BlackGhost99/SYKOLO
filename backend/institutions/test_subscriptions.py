import json
from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .models import Organization, School, PlatformAudit
from .student_models import Student, Enrollment
from .subscription_models import PlatformSubscription, PlatformSubscriptionPayment
from .finance_models import FeePayment
from .subscription_views import quote_lines
from .subscription_pricing import calculate_terms, DEFAULT_RATES, DEFAULT_MINIMUMS
from unittest.mock import patch


class PlatformSubscriptionTests(TestCase):
    def setUp(self):
        clock = patch('institutions.subscription_views.timezone.localdate', return_value=date(2026, 11, 17))
        clock.start()
        self.addCleanup(clock.stop)
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(username="billing", email="billing@example.test", password="Test-billing-2026!")
        self.ordinary = user_model.objects.create_user(username="staff", email="staff@example.test", password="Test-staff-2026!")
        self.client.force_login(self.admin)
        self.mfa()
        org = Organization.objects.create(name="Complexe test")
        self.school = School.objects.create(organization=org, name="Complexe", school_type="groupe_scolaire",
            education_cycles=["prescolaire", "primaire", "college"])
        self.other = School.objects.create(organization=org, name="Autre")
        self.year = AcademicYear.objects.create(school=self.school, code="2026", name="2026–2027",
            start_date=date(2026,9,1), end_date=date(2027,7,31), status="current")
        self.foreign_year = AcademicYear.objects.create(school=self.other, code="2026", name="2026–2027",
            start_date=date(2026,9,1), end_date=date(2027,7,31), status="current")
        self.path = f"/api/v1/platform/schools/{self.school.pk}/subscriptions"
        self.counts = {"prescolaire":1, "primaire":2, "college":3}
        self.rates = {"prescolaire":1000, "primaire":1500, "college":2000}
        for code, count in self.counts.items():
            cycle = AcademicCycle.objects.create(school=self.school, code=code, name=code)
            level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="test", name="Test")
            room = AcademicClass.objects.create(school=self.school, year=self.year, level=level, code=code, name=code)
            for i in range(count):
                student = Student.objects.create(school=self.school, student_code=f"{code}-{i}", first_name="Test", last_name="Élève")
                Enrollment.objects.create(school=self.school, student=student, year=self.year, classroom=room, enrolled_on=date(2026,9,12))

    def mfa(self):
        session = self.client.session
        session["mfa_verified"] = True
        session.save()

    def post(self, action, **kwargs):
        payload = {"action": action, "year_id": str(self.year.pk), **kwargs}
        return self.client.post(self.path, json.dumps(payload), content_type="application/json")

    def issue(self, **kwargs):
        return self.post("issue", **({"policy_revision":1,"expected_counts":self.counts,"reason":"Contrat test","period":"annuel","discount_xaf":0,"include_setup":False,"expected_total_xaf":100000} | kwargs))

    def test_quote_uses_real_counts_and_snapshot(self):
        self.assertEqual(self.client.get(self.path).json()["suggested_year"], str(self.year.pk))
        quote = self.post("quote")
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(quote.json()["counts"], self.counts)
        self.assertEqual(quote.json()["rates"], self.rates)
        self.assertEqual(PlatformSubscription.objects.count(), 0)
        result = self.issue()
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.json()["subscription"]["total_xaf"], 100000)
        self.assertEqual(self.issue().status_code, 409)
        Enrollment.objects.filter(school=self.school, classroom__level__cycle__code="college").update(active=False)
        self.assertEqual(self.post("quote").json()["subscription"]["total_xaf"], 100000)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_payment_idempotence_overpayment_and_void(self):
        self.assertEqual(self.issue().status_code, 201)
        values = {"reference":"X-1", "amount_xaf":3000, "method":"especes", "reason":"Justificatif"}
        self.assertEqual(self.post("payment", **values).status_code, 201)
        self.assertEqual(self.post("payment", **values).status_code, 200)
        self.assertEqual(self.post("payment", **{**values,"amount_xaf":4000}).status_code, 409)
        self.assertEqual(self.post("payment", **{**values,"reference":"X-2","amount_xaf":98000}).status_code, 409)
        self.assertEqual(PlatformSubscriptionPayment.objects.count(), 1)
        payment = PlatformSubscriptionPayment.objects.get()
        result = self.post("void", payment_id=payment.pk, reason="Erreur de saisie")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["subscription"]["balance_xaf"], 100000)
        self.assertEqual(self.post("payment", **values).status_code, 409)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(PlatformAudit.objects.filter(event__startswith="subscription_").count(), 3)

    def test_wrong_year_permissions_and_stale_quote(self):
        self.assertEqual(self.post("quote", year_id=str(self.foreign_year.pk)).status_code, 404)
        self.assertEqual(self.issue(expected_counts={"college":3}).status_code, 409)
        self.client.force_login(self.ordinary)
        self.mfa()
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.post("quote").status_code, 403)
        self.assertEqual(PlatformSubscription.objects.count(), 0)

    def test_rates_validated_zero_and_unknown(self):
        with self.assertRaises(ValueError):
            quote_lines({"college":2}, {"college":True})
        with self.assertRaises(ValueError):
            quote_lines({"unknown":3}, {})
        self.assertEqual(quote_lines({"college":2}, {"college":0})[0]["amount_xaf"], 0)
        rows = quote_lines({"primaire":4,"college":2}, {"primaire":1250,"college":2300})
        self.assertEqual(sum(r["amount_xaf"] for r in rows), 9600)

    def test_actual_cycle_prices_and_one_minimum(self):
        quote=self.post("quote").json()
        self.assertEqual(quote["terms"]["gross_xaf"],10000)
        self.assertEqual(quote["terms"]["minimum_xaf"],100000)
        self.assertEqual(quote["terms"]["minimum_adjustment_xaf"],90000)
        result=self.issue(period="trimestriel",discount_xaf=3,include_setup=True,expected_total_xaf=149997)
        self.assertEqual(result.status_code,201,result.content)
        sub=result.json()["subscription"]
        self.assertEqual(sub["terms"]["annual_xaf"],99997)
        self.assertEqual(sum(x["amount_xaf"] for x in sub["schedule"]),149997)
        self.assertEqual([x["amount_xaf"] for x in sub["schedule"]],[50000,25000,24999,24999,24999])
        self.assertEqual(sub["schedule"][1]["due_date"],"2026-11-17")
        self.assertEqual(sub["schedule"][2]["due_date"],"2027-02-17")
        self.assertEqual(FeePayment.objects.count(),0)

    def test_global_policy_revision_and_existing_contract_immutable(self):
        url="/api/v1/platform/subscription-pricing"
        self.assertEqual(self.client.get(url).json()["rates"],DEFAULT_RATES)
        self.assertEqual(self.issue().status_code,201)
        updated=dict(DEFAULT_RATES,primaire=1600)
        data={"rates":updated,"minimums":DEFAULT_MINIMUMS,"revision":1,"reason":"Révision commerciale"}
        r=self.client.post(url,json.dumps(data),content_type="application/json")
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(r.json()["revision"],2)
        self.assertEqual(self.client.post(url,json.dumps(data),content_type="application/json").status_code,409)
        self.assertEqual(self.post("quote").json()["subscription"]["total_xaf"],100000)
        self.assertEqual(PlatformSubscription.objects.get().lines[1]["rate_xaf"],1500)

    def test_stale_total_and_revision_refused_without_contract(self):
        self.assertEqual(self.issue(expected_total_xaf=99999).status_code,409)
        self.assertEqual(self.issue(policy_revision=99).status_code,409)
        self.assertEqual(PlatformSubscription.objects.count(),0)

    def test_complex_example(self):
        counts={"prescolaire":80,"primaire":200,"college":250,"lycee_general":150}
        terms=calculate_terms(counts,{k:DEFAULT_RATES[k] for k in counts},DEFAULT_MINIMUMS,
                              period="trimestriel",first_due=date(2026,9,1))
        self.assertEqual(terms["annual_xaf"],1180000)
        self.assertEqual([r["amount_xaf"] for r in terms["schedule"]],[295000]*4)
