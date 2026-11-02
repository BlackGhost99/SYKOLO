"""Aggregated screen data: correct totals, permission checks and school isolation."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment, FeePaymentVoid
from .models import Organization, School, SchoolRole, SchoolMember
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment

ZERO_DEC = Decimal("0")


class OverviewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="dir-ov", password="Strong director password 2026!")
        self.teacher = User.objects.create_user(username="teacher-ov", password="Strong teacher password 2026!")
        org = Organization.objects.create(name="Groupe aperçu")
        self.school = School.objects.create(organization=org, name="École A")
        self.other = School.objects.create(organization=org, name="École B")
        for school in (self.school, self.other):
            for code, name, perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=name, permissions=perms)
        SchoolMember.objects.create(school=self.school, user=self.director, role=SchoolRole.objects.get(school=self.school, code="direction"))
        SchoolMember.objects.create(school=self.school, user=self.teacher, role=SchoolRole.objects.get(school=self.school, code="enseignant"))
        today = timezone.localdate()
        self.today = today
        self.year = AcademicYear.objects.create(school=self.school, code="y", name="Année en cours",
                                                start_date=today - timedelta(days=100), end_date=today + timedelta(days=200))
        cycle = AcademicCycle.objects.create(school=self.school, code="c", name="Collège")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        self.c6b = AcademicClass.objects.create(school=self.school, year=self.year, level=level, code="6b", name="6e B")
        self.schedule = FeeSchedule.objects.create(school=self.school, year=self.year, code="scol", label="Scolarité",
                                                   amount=Decimal("100000"), currency="XAF", due_date=today - timedelta(days=5))
        self.rows = {}
        for code, last, paid in [("A1", "NZE", Decimal("100000")), ("A2", "OBAME", Decimal("40000")), ("A3", "MINKO", ZERO_DEC)]:
            s = Student.objects.create(school=self.school, student_code=code, first_name="Test", last_name=last)
            e = Enrollment.objects.create(school=self.school, student=s, year=self.year, classroom=self.c6b, enrolled_on=today - timedelta(days=3))
            ch = FeeCharge.objects.create(school=self.school, enrollment=e, schedule=self.schedule, label="Scolarité",
                                          amount=Decimal("100000"), currency="XAF", due_date=self.schedule.due_date)
            if paid:
                FeePayment.objects.create(school=self.school, charge=ch, idempotency_key=uuid.uuid4(), amount=paid,
                                          currency="XAF", method="airtel_money", paid_on=today)
            self.rows[last] = (s, e, ch)
        StudentGuardian.objects.create(school=self.school, student=self.rows["NZE"][0], full_name="NZE Sylvie", phone="+241 77 43 21 08", is_primary=True)
        StudentGuardian.objects.create(school=self.school, student=self.rows["OBAME"][0], full_name="OBAME Sandra")
        # A voided payment must not count.
        bad = FeePayment.objects.create(school=self.school, charge=self.rows["MINKO"][2], idempotency_key=uuid.uuid4(),
                                        amount=Decimal("5000"), currency="XAF", method="especes", paid_on=today)
        FeePaymentVoid.objects.create(school=self.school, payment=bad, reason="Erreur de saisie de test")
        Student.objects.create(school=self.other, student_code="X", first_name="Autre", last_name="ÉCOLE")
        self.base = f"/api/v1/schools/{self.school.pk}/overview/"

    def test_students_overview_rows_and_metrics(self):
        self.client.force_login(self.director)
        r = self.client.get(self.base + "students")
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        by_name = {s["last_name"]: s for s in data["students"]}
        self.assertEqual(set(by_name), {"NZE", "OBAME", "MINKO"})
        self.assertEqual(by_name["NZE"]["finance"]["status"], "a_jour")
        self.assertEqual(by_name["OBAME"]["finance"]["status"], "partiel")
        self.assertEqual(by_name["OBAME"]["finance"]["balance"], "60000.00")
        self.assertEqual(by_name["MINKO"]["finance"]["status"], "impaye")
        self.assertEqual(by_name["NZE"]["guardian"]["phone"], "+241 77 43 21 08")
        self.assertEqual(by_name["NZE"]["enrollment"]["classroom"]["name"], "6e B")
        m = data["metrics"]
        self.assertEqual(m["active"], 3)
        self.assertEqual(m["new_30d"], 3)
        self.assertEqual(m["incomplete"], 1)
        self.assertEqual(m["missing_phone"], 1)

    def test_finance_overview_totals(self):
        self.client.force_login(self.director)
        r = self.client.get(self.base + "finance")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.json()
        self.assertEqual(d["today"]["total"], "140000.00")
        self.assertEqual(d["today"]["count"], 2)
        self.assertEqual(d["today"]["by_method"], {"airtel_money": "140000.00"})
        self.assertEqual(d["outstanding"], "160000.00")
        self.assertEqual(d["families_late"], 2)
        self.assertEqual([a["amount_due"] for a in d["arrears"]], ["100000.00", "60000.00"])
        self.assertEqual(d["arrears_by_class"], [{"classroom": "6e B", "families": 2}])
        self.assertEqual(d["monthly"][-1]["total"], "140000.00")
        self.assertEqual(len(d["monthly"]), 6)

    def test_teacher_refused_and_secretariat_without_finance(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.base + "students").status_code, 403)
        self.assertEqual(self.client.get(self.base + "finance").status_code, 403)
        secretary = get_user_model().objects.create_user(username="sec-ov", password="Strong secretary password 2026!")
        SchoolMember.objects.create(school=self.school, user=secretary, role=SchoolRole.objects.get(school=self.school, code="secretariat"))
        self.client.force_login(secretary)
        r = self.client.get(self.base + "students")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["finance_visible"])
        self.assertTrue(all(s["finance"] is None for s in r.json()["students"]))
        self.assertEqual(self.client.get(self.base + "finance").status_code, 403)

    def test_other_school_hidden(self):
        self.client.force_login(self.director)
        url = f"/api/v1/schools/{self.other.pk}/overview/students"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other.pk}/overview/finance").status_code, 404)

    def test_requires_login(self):
        self.assertIn(self.client.get(self.base + "students").status_code, (401, 403))

