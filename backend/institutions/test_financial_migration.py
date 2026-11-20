"""Read-only financial migration, with explicit mappings and isolated permissions."""
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeCharge, FeeSchedule, FeePayment
from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .student_models import Enrollment, Student


class FinancialMigrationPreviewTests(TestCase):
    def setUp(self):
        today = timezone.localdate()
        self.today = today
        org = Organization.objects.create(name="Migration fictive")
        self.school = School.objects.create(organization=org, name="École A")
        self.foreign = School.objects.create(organization=org, name="École B")
        self.year = AcademicYear.objects.create(
            school=self.school, code="a", name="Année", start_date=today-timedelta(days=90),
            end_date=today+timedelta(days=90), status=AcademicYear.STATUS_CURRENT,
        )
        cycle = AcademicCycle.objects.create(school=self.school, code="c", name="Collège")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        klass = AcademicClass.objects.create(school=self.school, year=self.year, level=level, code="6a", name="6A")
        student = Student.objects.create(school=self.school, student_code="0001", first_name="Élève", last_name="Fictif")
        self.enrollment = Enrollment.objects.create(school=self.school, year=self.year,
            student=student, classroom=klass, enrolled_on=today-timedelta(days=60))
        self.tariff = FeeSchedule.objects.create(school=self.school, year=self.year, code="octobre",
            label="Scolarité", amount=50000, currency="XAF", due_date=today-timedelta(days=10))
        for role in ("comptabilite", "econome"):
            user = get_user_model().objects.create_user(username="migration-"+role)
            template = next(item for item in ROLE_TEMPLATES if item[0] == role)
            sr = SchoolRole.objects.create(school=self.school, code=role, label=template[1], permissions=template[2])
            SchoolMember.objects.create(school=self.school, user=user, role=sr)
            setattr(self, role, user)
        self.client.force_login(self.comptabilite)

    def preview(self, rows="0001;25 000", **kwargs):
        data = {
            "file": SimpleUploadedFile("historique.csv", ("Matricule;Octobre\n"+rows).encode("utf-8")),
            "year": str(self.year.pk), "cutoff": self.today.isoformat(),
            "mapping": json.dumps({"student_code": 0, "amounts": [{"column": 1, "schedule": str(self.tariff.pk)}]}),
        }
        data.update(kwargs)
        return self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/preview", data)

    def test_partial_amount_and_no_writes(self):
        response = self.preview()
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertFalse(result["commit_available"])
        cell = result["rows"][0]["cells"][0]
        self.assertEqual(cell["status"], "proposed")
        self.assertEqual(cell["declared"], "25000.00")
        self.assertEqual(cell["declared_balance"], "25000.00")
        self.assertFalse(FeeCharge.objects.exists())
        self.assertFalse(FeePayment.objects.exists())

    def test_zero_blank_invalid_overpayment_and_duplicate(self):
        for value, expected in [("", "unknown"), ("0", "zero"), ("NaN", "invalid"), ("75 000", "overpayment"), ("payé", "invalid")]:
            with self.subTest(value=value):
                response = self.preview("0001;"+value)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()["rows"][0]["cells"][0]["status"], expected)
        self.assertEqual(self.preview("0001;100\n0001;200").json()["counts"]["identity_review"], 2)
        self.assertEqual(self.preview("1;100").json()["counts"]["identity_review"], 1)
        self.assertFalse(FeeCharge.objects.exists())

    def test_existing_payment_needs_review(self):
        charge = FeeCharge.objects.create(school=self.school, enrollment=self.enrollment, schedule=self.tariff,
            label="Scolarité", amount=50000, currency="XAF")
        FeePayment.objects.create(school=self.school, charge=charge, amount=10000, currency="XAF",
            method="especes", paid_on=self.today, idempotency_key=uuid.uuid4(), recorded_by=self.econome)
        response = self.preview()
        self.assertEqual(response.json()["rows"][0]["cells"][0]["status"], "existing_review")
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(FeePayment.objects.first().amount, Decimal("10000"))

    def test_permission_and_cross_school_mapping(self):
        self.client.force_login(self.econome)
        self.assertEqual(self.preview().status_code, 403)
        self.client.force_login(self.comptabilite)
        other_year = AcademicYear.objects.create(school=self.foreign, code="b", name="B",
            start_date=self.today-timedelta(days=60), end_date=self.today+timedelta(days=60))
        foreign_tariff = FeeSchedule.objects.create(school=self.foreign, year=other_year, code="b",
            label="Scolarité", amount=50000, currency="XAF")
        mapping = json.dumps({"student_code": 0, "amounts": [{"column": 1, "schedule": str(foreign_tariff.pk)}]})
        self.assertEqual(self.preview(mapping=mapping).status_code, 422)
        self.assertEqual(self.preview(year=str(other_year.pk)).status_code, 422)
        self.assertFalse(FeeCharge.objects.exists())
