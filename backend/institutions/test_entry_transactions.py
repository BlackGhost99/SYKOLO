"""Acceptance of paged, school-scoped income transaction drilldown."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .finance_models import FeeCharge, FeePayment, FeePaymentVoid, FeeSchedule
from .models import Organization, School, SchoolMember, SchoolRole, SchoolSetting
from .student_models import Enrollment, Student
from .entry_category_policy import POLICY_SCOPE


class IncomeTransactionTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.staff=User.objects.create_user(username="entries-trans",password="Secure entries 2026!")
        self.school=School.objects.create(organization=Organization.objects.create(name="École A"),name="A")
        self.foreign=School.objects.create(organization=Organization.objects.create(name="École B"),name="B")
        role=SchoolRole.objects.create(school=self.school,code="compta",
                                       label="Comptabilité",permissions=["school.finance.read","school.view"])
        SchoolMember.objects.create(school=self.school,user=self.staff,role=role)
        self.year=AcademicYear.objects.create(school=self.school,code="2026-2027",name="2026-2027",
                                              start_date=date(2026,9,1),end_date=date(2027,7,31))
        self.other_year=AcademicYear.objects.create(school=self.foreign,code="2026-2027",name="2026-2027",
                                                    start_date=date(2026,9,1),end_date=date(2027,7,31))
        cycle=AcademicCycle.objects.create(school=self.school,code="college",name="Collège")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="6e",name="Sixième")
        classroom=AcademicClass.objects.create(school=self.school,year=self.year,level=level,
                                               code="6A",name="6A")
        pupil=Student.objects.create(school=self.school,first_name="Secret",last_name="Personne")
        enrollment=Enrollment.objects.create(school=self.school,student=pupil,year=self.year,
                                             classroom=classroom,enrolled_on=date(2026,9,10))
        self.schedule=FeeSchedule.objects.create(school=self.school,year=self.year,code="SCOL-202611",
                                                label="Scolarité",currency="XAF",amount=Decimal("50000"))
        fee=FeeCharge.objects.create(school=self.school,schedule=self.schedule,enrollment=enrollment,
                                     label="Scolarité",amount=Decimal("50000"),currency="XAF")
        self.paid=FeePayment.objects.create(school=self.school,charge=fee,amount=Decimal("15000"),
                                            currency="XAF",method="especes",paid_on=date(2026,11,20),
                                            idempotency_key=uuid4(),recorded_by=self.staff)
        self.demo=FeePayment.objects.create(school=self.school,charge=fee,amount=Decimal("2500"),
                                            currency="XAF",method="simulation",paid_on=date(2026,11,20),
                                            idempotency_key=uuid4(),recorded_by=self.staff)
        old=FeePayment.objects.create(school=self.school,charge=fee,amount=Decimal("7000"),
                                      currency="XAF",method="especes",paid_on=date(2026,11,20),
                                      idempotency_key=uuid4(),recorded_by=self.staff)
        FeePaymentVoid.objects.create(school=self.school,payment=old,approved_by=self.staff,reason="Annulé")
        self.url=f"/api/v1/schools/{self.school.pk}/finance/entry-transactions"
        self.client.force_login(self.staff)

    def test_fee_receipts_are_filterable_dated_and_isolated(self):
        result=self.client.get(self.url,{"year":str(self.year.pk),"category":"scolarite",
                                         "currency":"XAF","fee_code":"SCOL-202611"})
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result["Cache-Control"],"no-store")
        report=result.json()
        self.assertFalse(report["revenue_certified"])
        self.assertEqual(report["total"],1)
        self.assertEqual(len(report["rows"]),1)
        row=report["rows"][0]
        self.assertEqual(row["amount"],"15000.00")
        self.assertEqual(row["category"],"scolarite")
        self.assertEqual(row["id"],str(self.paid.pk))
        self.assertIn(str(self.paid.pk),row["receipt_url"])
        self.assertNotIn("Secret",result.content.decode())
        demo=self.client.get(self.url,{"year":str(self.year.pk),"category":"demo"}).json()
        self.assertEqual(demo["total"],1)
        self.assertEqual(demo["rows"][0]["id"],str(self.demo.pk))
        self.assertEqual(demo["rows"][0]["evidence"],"simulation")

    def test_no_foreign_year_or_write_or_invalid_query(self):
        self.assertEqual(self.client.get(self.url,{"year":str(self.other_year.pk)}).status_code,422)
        self.assertEqual(self.client.get(self.url).status_code,422)
        self.assertEqual(self.client.get(self.url,{"year":str(self.year.pk),"page":"0"}).status_code,422)
        self.assertEqual(self.client.get(self.url,{"year":str(self.year.pk),"category":"profit"}).status_code,422)
        self.assertEqual(self.client.post(self.url,{}).status_code,405)
        foreign_url=f"/api/v1/schools/{self.foreign.pk}/finance/entry-transactions"
        self.assertIn(self.client.get(foreign_url,{"year":str(self.other_year.pk)}).status_code,(403,404))

    def test_explicit_school_classification_changes_lookup_not_receipt(self):
        SchoolSetting.objects.create(school=self.school,scope_key=POLICY_SCOPE,
            values={"assignments":{str(self.schedule.pk):"extrascolaire"}},
            scope={"module":"income"})
        query={"year":str(self.year.pk),"category":"extrascolaire"}
        report=self.client.get(self.url,query).json()
        self.assertEqual(report["total"],1)
        self.assertEqual(report["rows"][0]["id"],str(self.paid.pk))
        self.assertEqual(report["rows"][0]["amount"],"15000.00")
        self.assertEqual(FeePayment.objects.filter(school=self.school).count(),3)


    def test_period_filters_are_inclusive_and_defensive(self):
        year=str(self.year.pk)
        exact=self.client.get(self.url,{
            "year":year,"category":"scolarite","from":"2026-11-20","to":"2026-11-20",
        })
        self.assertEqual(exact.status_code,200,exact.content)
        self.assertEqual(exact.json()["total"],1)
        self.assertEqual(exact.json()["filters"]["from"],"2026-11-20")
        self.assertEqual(self.client.get(self.url,{"year":year,"from":"2026-11-21"}).json()["total"],0)
        self.assertEqual(self.client.get(self.url,{"year":year,"to":"2026-11-19"}).json()["total"],0)
        self.assertEqual(self.client.get(self.url,{
            "year":year,"from":"2026-11-21","to":"2026-11-20"}).status_code,422)
        self.assertEqual(self.client.get(self.url,{"year":year,"from":"2026-11-99"}).status_code,422)
        self.assertEqual(self.client.get(self.url,{"year":year,"to":"bad-date"}).status_code,422)
        self.assertEqual(self.client.get(self.url,{"year":year,"format":"xlsx"}).status_code,422)

    def test_csv_export_is_guarded_auditable_and_contains_no_student_data(self):
        response=self.client.get(self.url,{
            "year":str(self.year.pk),"category":"scolarite",
            "currency":"XAF","format":"csv","from":"2026-11-20","to":"2026-11-20",
        })
        self.assertEqual(response.status_code,200,response.content)
        self.assertIn("text/csv",response["Content-Type"])
        self.assertEqual(response["Cache-Control"],"no-store")
        self.assertIn("attachment",response["Content-Disposition"])
        self.assertTrue(response.content.decode("utf-8").startswith("\ufeff"))
        content=response.content.decode("utf-8-sig")
        self.assertIn("Montant déclaré",content)
        self.assertIn("15000.00",content)
        self.assertIn(str(self.paid.pk),content)
        self.assertNotIn(str(self.demo.pk),content)
        self.assertNotIn("Secret",content)
        self.assertNotIn("Personne",content)
        self.assertEqual(self.client.get(self.url,{
            "year":str(self.year.pk),"format":"csv","page":"2"}).status_code,422)
        self.assertEqual(self.client.post(self.url,{"format":"csv"}).status_code,405)

    def test_csv_cells_are_protected_from_spreadsheet_formula_injection(self):
        self.schedule.code="=2+2"
        self.schedule.save(update_fields=["code"])
        response=self.client.get(self.url,{
            "year":str(self.year.pk),"format":"csv","category":"a_classer",
        })
        self.assertEqual(response.status_code,200,response.content)
        self.assertIn("'=2+2",response.content.decode("utf-8-sig"))
