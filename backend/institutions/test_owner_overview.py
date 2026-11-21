"""Recette : la visibilité propriétaire est indépendante des pouvoirs métier."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .admission_models import AdmissionApplication
from .finance_models import FeeCharge, FeePayment, FeePaymentVoid, FeeSchedule
from .parent_payment_models import AdmissionCashReceipt, AdmissionCashReceiptVoid
from .models import Organization, OrganizationMember, School, SchoolAudit, SchoolMember, SchoolRole
from .services import OWNER_ROLE_TEMPLATE, ROLE_TEMPLATES
from .staff_models import StaffRecord, StaffAssignment
from .student_models import Student, Enrollment


class OwnerOverviewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner-pilot", password="Owner-2026-secure!")
        self.founder = User.objects.create_user(username="founder-pilot", password="Founder-2026-secure!")
        self.director = User.objects.create_user(username="director-pilot", password="Director-2026-secure!")
        self.fake_owner = User.objects.create_user(username="fake-owner-pilot", password="Fake-2026-secure!")
        self.stranger = User.objects.create_user(username="stranger-pilot", password="Stranger-2026-secure!")
        org = Organization.objects.create(name="Établissement propriétaire test")
        OrganizationMember.objects.create(organization=org, user=self.founder, role="founder")
        self.school = School.objects.create(
            organization=org, name="Collège propriétaire test",
            school_type="college", education_cycles=["college"],
        )
        self.other_org = Organization.objects.create(name="Établissement isolé")
        self.other = School.objects.create(organization=self.other_org,name="Collège isolé")
        owner_role = SchoolRole.objects.create(
            school=self.school, code=OWNER_ROLE_TEMPLATE[0],
            label=OWNER_ROLE_TEMPLATE[1], permissions=list(OWNER_ROLE_TEMPLATE[2]),
        )
        director_role = SchoolRole.objects.create(
            school=self.school, code="direction", label="Direction",
            permissions=["school.view","school.finance.read","school.students.read","school.staff.read"],
        )
        SchoolMember.objects.create(
            school=self.school, user=self.owner, role=owner_role, is_school_owner=True,
        )
        SchoolMember.objects.create(
            school=self.school, user=self.fake_owner, role=owner_role,
        )
        SchoolMember.objects.create(
            school=self.school, user=self.director, role=director_role,
        )
        self.year=AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026–2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
            status="current",
        )
        self.foreign_year=AcademicYear.objects.create(
            school=self.other, code="2026-2027", name="2026–2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
        )
        cycle=AcademicCycle.objects.create(school=self.school,code="college",name="Collège")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="6e",name="Sixième")
        room=AcademicClass.objects.create(
            school=self.school,year=self.year,level=level,code="6A",name="Sixième A",capacity=35,
        )
        pupil=Student.objects.create(
            school=self.school,first_name="MineurSecret",last_name="Masqué",
            address="Adresse privée à ne pas révéler",
        )
        enrollment=Enrollment.objects.create(
            school=self.school,student=pupil,year=self.year,classroom=room,
            enrolled_on=date(2026, 9, 10),
        )
        for code, currency, amount in (("scolarite","XAF","120000"),("transport","USD","30")):
            schedule=FeeSchedule.objects.create(
                school=self.school,year=self.year,code=code,label=code,
                currency=currency,amount=Decimal(amount),due_date=date(2026,10,20),
            )
            charge=FeeCharge.objects.create(
                school=self.school,enrollment=enrollment,schedule=schedule,
                label=code,currency=currency,amount=schedule.amount,due_date=schedule.due_date,
            )
            if code=="scolarite":
                FeePayment.objects.create(
                    school=self.school,charge=charge,amount=Decimal("50000"),
                    currency="XAF",method="especes",paid_on=timezone.localdate(),
                    idempotency_key=uuid4(),recorded_by=self.director,
                )
                voided=FeePayment.objects.create(
                    school=self.school,charge=charge,amount=Decimal("10000"),
                    currency="XAF",method="especes",paid_on=timezone.localdate(),
                    idempotency_key=uuid4(),recorded_by=self.director,
                )
                FeePaymentVoid.objects.create(
                    school=self.school,payment=voided,reason="Erreur de saisie",approved_by=self.director,
                )
        AdmissionApplication.objects.create(
            school=self.school,year=self.year,classroom=room,
            first_name="AutreSecret",last_name="Candidat",guardian_name="ParentSecret",
            guardian_phone="077123456",source="ecole",status="submitted",
        )
        teacher=StaffRecord.objects.create(
            school=self.school,staff_code="STAFF-01",first_name="EmployéSecret",
            last_name="Personnel",position="Enseignant",
        )
        StaffAssignment.objects.create(
            school=self.school,staff=teacher,year=self.year,classroom=room,duty="enseignant",
        )
        SchoolAudit.objects.create(
            school=self.school,actor=self.director,event="student_created",
            subject="MineurSecret",details={"private":"Très confidentiel"},
        )
        self.url=f"/api/v1/schools/{self.school.pk}/owner/overview"

    def test_owner_sees_counts_without_student_or_staff_personal_data(self):
        self.client.force_login(self.owner)
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200,response.content)
        d=response.json()
        self.assertTrue(d["read_only"])
        self.assertEqual(response["Cache-Control"],"no-store")
        self.assertEqual(d["schooling"]["active_students"],1)
        self.assertEqual(d["schooling"]["active_classes"],1)
        self.assertEqual(d["schooling"]["enrollment_by_cycle"][0]["cycle"],"Collège")
        self.assertEqual(d["schooling"]["total_defined_places"],35)
        self.assertEqual(d["staff"]["active"],1)
        self.assertEqual(d["staff"]["assigned_to_classes"],1)
        self.assertEqual(d["admissions"]["pending"],1)
        self.assertEqual(d["activity"]["total_30d"],1)
        finance={row["currency"]:row for row in d["finance"]["currencies"]}
        self.assertEqual(set(finance),{"XAF","USD"})
        self.assertEqual(finance["XAF"]["billed"],"120000.00")
        self.assertEqual(finance["XAF"]["paid"],"50000.00")
        self.assertEqual(finance["XAF"]["outstanding"],"70000.00")
        self.assertEqual(finance["USD"]["paid"],"0.00")
        text=response.content.decode()
        for private in ("MineurSecret","EmployéSecret","ParentSecret",
                        "077123456","Très confidentiel","Adresse privée"):
            self.assertNotIn(private,text)

    def test_owner_finance_separates_unverified_cash_and_uses_net_scholarship_amount(self):
        billed = FeeCharge.objects.get(school=self.school, currency="XAF")
        FeeCharge.objects.filter(pk=billed.pk).update(scholarship_discount=Decimal("10000.00"))
        for method, amount in (("cash", "20000"), ("simulation", "5000")):
            FeePayment.objects.create(
                school=self.school, charge=billed, method=method,
                amount=Decimal(amount), currency="XAF",
                paid_on=timezone.localdate(), idempotency_key=uuid4(),
                recorded_by=self.director,
            )
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        finance = next(x for x in response.json()["finance"]["currencies"] if x["currency"] == "XAF")
        self.assertEqual(finance["billed"], "110000.00")
        self.assertEqual(finance["paid"], "75000.00")
        self.assertEqual(finance["outstanding"], "35000.00")
        self.assertEqual(finance["evidence"], {
            "explicit_demo": "5000.00",
            "legacy_cash_unverified": "20000.00",
            "other_declared": "50000.00",
        })
        self.assertFalse(response.json()["finance"]["revenue_certified"])


    def test_admission_cash_income_is_isolated_from_tuition_and_excludes_voids_demo(self):
        application = AdmissionApplication.objects.get(school=self.school)
        today = timezone.localdate()
        AdmissionCashReceipt.objects.create(
            school=self.school, application=application, amount_xaf=15000,
            is_demo=False, received_on=today, recorded_by=self.director,
        )
        demo_application = AdmissionApplication.objects.create(
            school=self.school, year=self.year, classroom=application.classroom,
            first_name="Simulation", last_name="Exclue", status="submitted", source="ecole",
        )
        AdmissionCashReceipt.objects.create(
            school=self.school, application=demo_application, amount_xaf=35000,
            is_demo=True, received_on=today, recorded_by=self.director,
        )
        void_application = AdmissionApplication.objects.create(
            school=self.school, year=self.year, classroom=application.classroom,
            first_name="Annulation", last_name="Exclue", status="submitted", source="ecole",
        )
        cancelled = AdmissionCashReceipt.objects.create(
            school=self.school, application=void_application, amount_xaf=25000,
            is_demo=False, received_on=today, recorded_by=self.director,
        )
        AdmissionCashReceiptVoid.objects.create(
            school=self.school, receipt=cancelled,
            reason="Erreur de caisse", voided_by=self.owner,
        )
        future_application = AdmissionApplication.objects.create(
            school=self.school, year=self.year, classroom=application.classroom,
            first_name="Future", last_name="Exclue", status="submitted", source="ecole",
        )
        AdmissionCashReceipt.objects.create(
            school=self.school, application=future_application, amount_xaf=40000,
            is_demo=False, received_on=today + timedelta(days=1), recorded_by=self.director,
        )
        # A second school with the same academic year cannot influence this total.
        other_cycle = AcademicCycle.objects.create(school=self.other, code="college", name="Collège")
        other_level = AcademicLevel.objects.create(
            school=self.other, cycle=other_cycle, code="6e", name="Sixième",
        )
        other_room = AcademicClass.objects.create(
            school=self.other, year=self.foreign_year, level=other_level,
            code="6A", name="Sixième A",
        )
        foreign_application = AdmissionApplication.objects.create(
            school=self.other, year=self.foreign_year, classroom=other_room,
            first_name="Autre", last_name="École", status="submitted", source="ecole",
        )
        AdmissionCashReceipt.objects.create(
            school=self.other, application=foreign_application, amount_xaf=90000,
            is_demo=False, received_on=today, recorded_by=self.director,
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        income = response.json()["finance"]["admission_cash"]
        self.assertEqual(income["currency"], "XAF")
        self.assertEqual(income["total"], "15000.00")
        self.assertEqual(income["today"], "15000.00")
        self.assertEqual(income["this_month"], "15000.00")
        self.assertEqual(income["count"], 1)
        self.assertEqual(income["demo_excluded"], 1)
        self.assertEqual(income["voided_excluded"], 1)
        self.assertEqual(income["future_dated_excluded"], 1)
        self.assertFalse(income["revenue_certified"])
        # The original fee ledger keeps its own figures; no implicit summation.
        fee = next(row for row in response.json()["finance"]["currencies"] if row["currency"] == "XAF")
        self.assertEqual(fee["paid"], "50000.00")
        for secret in ("Simulation Exclue", "Autre École"):
            self.assertNotIn(secret, response.content.decode())


    def test_owner_income_categories_separate_scolarite_extrascolaire_and_unknown_codes(self):
        self.client.force_login(self.owner)
        initial = self.client.get(self.url)
        self.assertEqual(initial.status_code, 200, initial.content)
        rows = {
            (row["category"], row["currency"]): row
            for row in initial.json()["finance"]["fee_income_categories"]["rows"]
        }
        self.assertEqual(rows[("scolarite", "XAF")]["billed"], "120000.00")
        self.assertEqual(rows[("scolarite", "XAF")]["paid"], "50000.00")
        self.assertEqual(rows[("extrascolaire", "USD")]["billed"], "30.00")
        self.assertEqual(rows[("extrascolaire", "USD")]["paid"], "0.00")
        self.assertFalse(initial.json()["finance"]["fee_income_categories"]["revenue_certified"])

        charge = FeeCharge.objects.get(school=self.school, currency="XAF")
        unknown = FeeSchedule.objects.create(
            school=self.school, year=self.year, code="frais-a-verifier",
            label="Libellé sans classement", currency="XAF",
            amount=Decimal("3000"), due_date=timezone.localdate(),
        )
        other_charge = FeeCharge.objects.create(
            school=self.school, enrollment=charge.enrollment, schedule=unknown,
            label="Libellé sans classement", currency="XAF", amount=Decimal("3000"),
            due_date=timezone.localdate(),
        )
        FeePayment.objects.create(
            school=self.school, charge=other_charge, amount=Decimal("1000"),
            currency="XAF", method="especes", paid_on=timezone.localdate(),
            idempotency_key=uuid4(), recorded_by=self.director,
        )
        FeePayment.objects.create(
            school=self.school, charge=charge, amount=Decimal("5000"),
            currency="XAF", method="simulation", paid_on=timezone.localdate(),
            idempotency_key=uuid4(), recorded_by=self.director,
        )
        classified = self.client.get(self.url).json()["finance"]["fee_income_categories"]
        rows = {(row["category"], row["currency"]): row for row in classified["rows"]}
        self.assertEqual(rows[("scolarite", "XAF")]["paid"], "50000.00")
        self.assertEqual(rows[("demo", "XAF")]["paid"], "5000.00")
        self.assertEqual(rows[("a_classer", "XAF")]["billed"], "3000.00")
        self.assertEqual(rows[("a_classer", "XAF")]["paid"], "1000.00")
        self.assertIn(
            "frais-a-verifier",
            [d["fee_code"] for d in classified["details"] if d["category"] == "a_classer"],
        )
        # Every non-void posted transaction is represented exactly once.
        self.assertEqual(
            sum(Decimal(row["paid"]) for row in classified["rows"] if row["currency"] == "XAF"),
            Decimal("56000.00"),
        )
        original = self.client.get(self.url).json()["finance"]["currencies"]
        self.assertEqual(next(x for x in original if x["currency"] == "XAF")["paid"], "56000.00")
        self.assertTrue(self.client.get(self.url)["Cache-Control"].startswith("no-store"))

    def test_real_founder_without_director_role_may_monitor(self):
        self.client.force_login(self.founder)
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()["schooling"]["active_students"],1)

    def test_director_and_fake_owner_cannot_use_owner_view(self):
        for user in (self.director,self.fake_owner):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code,403)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.other.pk}/owner/overview"
        ).status_code,404)

    def test_read_only_and_year_isolation(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url,{}).status_code,405)
        self.assertEqual(self.client.get(self.url+"?year=no").status_code,422)
        self.assertEqual(self.client.get(
            self.url+f"?year={self.foreign_year.pk}"
        ).status_code,422)
        requested=self.client.get(self.url+f"?year={self.year.pk}")
        self.assertEqual(requested.status_code,200)
        self.assertEqual(requested.json()["year"]["id"],str(self.year.pk))

    def test_owner_deactivation_revokes_oversight(self):
        self.client.force_login(self.owner)
        SchoolMember.objects.filter(school=self.school,user=self.owner).update(active=False)
        self.assertEqual(self.client.get(self.url).status_code,404)
