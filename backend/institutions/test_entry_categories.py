"""Contract tests: income taxonomy is school-scoped and never changes money."""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .entry_income import fee_entries_by_category
from .finance_models import FeeCharge, FeeSchedule
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole, SchoolSetting
from .student_models import Enrollment, Student


class EntryCategoryPolicyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.account = User.objects.create_user(username="entry-editor", password="Secure entry 2026!")
        self.reader = User.objects.create_user(username="entry-reader", password="Secure entry read 2026!")
        self.school = School.objects.create(organization=Organization.objects.create(name="École A"), name="École A")
        self.foreign = School.objects.create(organization=Organization.objects.create(name="École B"), name="École B")
        managing = SchoolRole.objects.create(school=self.school, code="tarification", label="Tarification",
                                             permissions=["school.view", "school.finance.read", "school.finance.manage"])
        reading = SchoolRole.objects.create(school=self.school, code="finance_read", label="Lecture finances",
                                            permissions=["school.view", "school.finance.read"])
        SchoolMember.objects.create(school=self.school, user=self.account, role=managing)
        SchoolMember.objects.create(school=self.school, user=self.reader, role=reading)
        self.year = AcademicYear.objects.create(school=self.school, code="2026-2027", name="2026-2027",
                                                start_date=date(2026,9,1), end_date=date(2027,7,30))
        self.other_year = AcademicYear.objects.create(school=self.foreign, code="2026-2027", name="2026-2027",
                                                      start_date=date(2026,9,1), end_date=date(2027,7,30))
        self.tariff = FeeSchedule.objects.create(school=self.school, year=self.year, code="option-perso",
                                                label="Atelier configurable", currency="XAF", amount=Decimal("12000.00"))
        self.foreign_tariff = FeeSchedule.objects.create(school=self.foreign, year=self.other_year,
                                                        code="autre", label="Privé", currency="XAF",
                                                        amount=Decimal("3000.00"))
        self.url = f"/api/v1/schools/{self.school.pk}/finance/entry-categories"
        self.client.force_login(self.account)

    def patch(self, schedule, category, revision=0, reason="Classement contrôlé par l'établissement",
              **extra):
        return self.client.patch(self.url, data=json.dumps({
            "schedule":str(schedule.pk), "category":category, "revision":revision,
            "reason":reason, **extra,
        }), content_type="application/json")

    def test_get_and_first_explicit_assignment_are_scoped_and_audited(self):
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()["revision"],0)
        self.assertEqual(response["Cache-Control"],"no-store")
        self.assertEqual(response.json()["assignments"],{})
        patch=self.patch(self.tariff,"extrascolaire")
        self.assertEqual(patch.status_code,200,patch.content)
        self.assertEqual(patch.json()["revision"],1)
        self.assertEqual(self.client.get(self.url).json()["assignments"][str(self.tariff.pk)],"extrascolaire")
        self.assertEqual(SchoolAudit.objects.filter(school=self.school,event="income_fee_classified").count(),1)
        self.assertEqual(SchoolSetting.objects.filter(school=self.school).count(),1)
        self.assertEqual(self.patch(self.tariff,"scolarite",revision=0).status_code,409)
        self.assertEqual(self.patch(self.foreign_tariff,"extrascolaire",revision=1).status_code,404)
        self.assertEqual(SchoolSetting.objects.filter(school=self.foreign).count(),0)

    def test_reader_cannot_change_classification_and_demo_cannot_be_relabelled(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.patch(self.tariff,"extrascolaire").status_code,403)
        self.client.force_login(self.account)
        demo=FeeSchedule.objects.create(school=self.school,year=self.year,code="DEMO-SCOL",
                                        label="Simulation",currency="XAF",amount=Decimal("5000"))
        self.assertEqual(self.patch(demo,"scolarite").status_code,422)
        self.assertEqual(self.patch(self.tariff,"autre_tresorerie").status_code,422)
        self.assertEqual(self.patch(self.tariff,"extrascolaire",reason="x").status_code,422)
        self.assertEqual(SchoolAudit.objects.filter(event="income_fee_classified").count(),0)

    def test_historical_first_assignment_requires_ack_then_is_frozen(self):
        cycle=AcademicCycle.objects.create(school=self.school,code="college",name="Collège")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="6e",name="Sixième")
        room=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="6A",name="Sixième A")
        student=Student.objects.create(school=self.school,first_name="Test",last_name="Élève")
        enrollment=Enrollment.objects.create(school=self.school,student=student,year=self.year,
                                             classroom=room,enrolled_on=date(2026,9,10))
        FeeCharge.objects.create(school=self.school,enrollment=enrollment,schedule=self.tariff,
                                 label="Atelier configurable",amount=Decimal("12000"),currency="XAF")
        before=fee_entries_by_category(self.school,self.year)
        self.assertEqual(before["rows"][0]["category"],"a_classer")
        refused=self.patch(self.tariff,"extrascolaire")
        self.assertEqual(refused.status_code,422,refused.content)
        self.assertEqual(SchoolAudit.objects.filter(event="income_fee_classified").count(),0)
        confirmed=self.patch(self.tariff,"extrascolaire",acknowledge_history=True)
        self.assertEqual(confirmed.status_code,200,confirmed.content)
        after=fee_entries_by_category(self.school,self.year)
        self.assertEqual(after["rows"][0]["category"],"extrascolaire")
        self.assertEqual(after["rows"][0]["billed"],before["rows"][0]["billed"])
        self.assertEqual(FeeCharge.objects.get(schedule=self.tariff).amount,Decimal("12000"))
        self.assertEqual(SchoolAudit.objects.get(event="income_fee_classified").details["historical_charges"],True)
        locked=self.patch(self.tariff,"scolarite",revision=1,acknowledge_history=True)
        self.assertEqual(locked.status_code,409,locked.content)
        self.assertEqual(self.patch(self.tariff,"extrascolaire",revision=1).json()["unchanged"],True)
        self.assertEqual(SchoolAudit.objects.filter(event="income_fee_classified").count(),1)
