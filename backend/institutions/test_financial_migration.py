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
from .finance_models import (
    FeeCharge,
    FeeSchedule,
    FeePayment,
    HistoricalFinancialMigration,
    HistoricalFeeAdjustment,
)
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
        self.secretary = get_user_model().objects.create_user(username="migration-readonly")
        readonly = SchoolRole.objects.create(school=self.school, code="migration_readonly", label="Lecture élèves", permissions=["school.students.profile.read"])
        SchoolMember.objects.create(school=self.school, user=self.secretary, role=readonly)
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
        self.client.force_login(self.secretary)
        self.assertEqual(self.preview().status_code, 403)
        self.client.force_login(self.econome)
        self.assertEqual(self.preview().status_code, 200)
        self.client.force_login(self.comptabilite)
        other_year = AcademicYear.objects.create(school=self.foreign, code="b", name="B",
            start_date=self.today-timedelta(days=60), end_date=self.today+timedelta(days=60))
        foreign_tariff = FeeSchedule.objects.create(school=self.foreign, year=other_year, code="b",
            label="Scolarité", amount=50000, currency="XAF")
        mapping = json.dumps({"student_code": 0, "amounts": [{"column": 1, "schedule": str(foreign_tariff.pk)}]})
        self.assertEqual(self.preview(mapping=mapping).status_code, 422)
        self.assertEqual(self.preview(year=str(other_year.pk)).status_code, 422)
        self.assertFalse(FeeCharge.objects.exists())

    def test_prepare_approve_and_repeat_are_atomic_and_not_receipts(self):
        self.client.force_login(self.econome)
        data = {
            "file": SimpleUploadedFile("historique.csv", "Matricule;Octobre\n0001;25000".encode("utf-8")),
            "year": str(self.year.pk),
            "cutoff": self.today.isoformat(),
            "mapping": json.dumps({"student_code": 0, "amounts": [{"column": 1, "schedule": str(self.tariff.pk)}]}),
        }
        prepared = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/prepare", data
        )
        self.assertEqual(prepared.status_code, 200, prepared.content)
        batch_id = prepared.json()["batch"]
        self.assertEqual(HistoricalFinancialMigration.objects.count(), 1)
        self.assertFalse(FeeCharge.objects.exists())
        self.assertFalse(FeePayment.objects.exists())
        self.assertFalse(HistoricalFeeAdjustment.objects.exists())

        data["file"] = SimpleUploadedFile(
            "historique.csv", "Matricule;Octobre\n0001;25000".encode("utf-8")
        )
        repeated = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/prepare", data
        )
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertTrue(repeated.json()["idempotent"])
        self.assertEqual(HistoricalFinancialMigration.objects.count(), 1)

        approved_as_preparer = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/{batch_id}/approve",
            {"reason": "Justificatif historique vérifié"},
        )
        self.assertEqual(approved_as_preparer.status_code, 403)

        self.client.force_login(self.comptabilite)
        approved = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/{batch_id}/approve",
            {"reason": "Justificatif historique vérifié"},
        )
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertFalse(approved.json()["idempotent"])
        charge = FeeCharge.objects.get(school=self.school, enrollment=self.enrollment)
        adjustment = HistoricalFeeAdjustment.objects.get(batch_id=batch_id, charge=charge)
        self.assertEqual(adjustment.amount, Decimal("25000"))
        self.assertFalse(FeePayment.objects.exists())
        from .finance_views import cleared_total
        self.assertEqual(cleared_total(charge), Decimal("25000"))

        repeated = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/{batch_id}/approve",
            {"reason": "Justificatif historique vérifié"},
        )
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertTrue(repeated.json()["idempotent"])
        self.assertEqual(HistoricalFeeAdjustment.objects.count(), 1)
        self.assertFalse(FeePayment.objects.exists())

    def test_cancel_prepared_batch_and_closed_year_guard(self):
        self.client.force_login(self.econome)
        data = {
            "file": SimpleUploadedFile("historique.csv", "Matricule;Octobre\n0001;25000".encode("utf-8")),
            "year": str(self.year.pk),
            "cutoff": self.today.isoformat(),
            "mapping": json.dumps({"student_code": 0, "amounts": [{"column": 1, "schedule": str(self.tariff.pk)}]}),
        }
        prepared = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/prepare", data
        )
        batch_id = prepared.json()["batch"]
        cancelled = self.client.post(
            f"/api/v1/schools/{self.school.pk}/imports/finance/{batch_id}/cancel",
            {"reason": "Justificatif incomplet"},
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        batch = HistoricalFinancialMigration.objects.get(pk=batch_id)
        self.assertEqual(batch.status, HistoricalFinancialMigration.STATUS_CANCELLED)
        self.assertFalse(FeeCharge.objects.exists())

    def test_inspection_is_finance_only_and_filters_tariffs(self):
        def inspect():
            f = SimpleUploadedFile("historique.csv", "Matricule;Octobre\n0001;25000".encode("utf-8"))
            return self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/inspect", {"file": f})
        FeeSchedule.objects.create(school=self.school, year=self.year, code="demo",
            label="DÉMO - Scolarité", amount=50000, currency="XAF")
        other_year = AcademicYear.objects.create(school=self.foreign, code="b", name="B",
            start_date=self.today-timedelta(days=60), end_date=self.today+timedelta(days=60))
        FeeSchedule.objects.create(school=self.foreign, year=other_year, code="foreign",
            label="Étranger", amount=50000, currency="XAF")
        response = inspect()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["suggested_student_code"], 0)
        self.assertEqual(data["financial_columns"], [1])
        self.assertEqual(data["financial_hints"], {"1": "ambiguous"})
        self.assertEqual([t["id"] for t in data["tariffs"]], [str(self.tariff.pk)])
        self.assertEqual([y["id"] for y in data["years"]], [str(self.year.pk)])
        self.assertNotIn("samples", data)
        self.assertNotIn("0001", response.content.decode())
        self.assertFalse(FeeCharge.objects.exists())
        self.client.force_login(self.econome)
        self.assertEqual(inspect().status_code, 200)
        self.client.force_login(self.secretary)
        self.assertEqual(inspect().status_code, 403)

    def prepare_history(self, value="25000"):
        self.client.force_login(self.econome)
        return self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/prepare", {
            "file": SimpleUploadedFile("historique.csv", ("Matricule;Octobre\n0001;"+value).encode("utf-8")),
            "year": str(self.year.pk), "cutoff": self.today.isoformat(),
            "mapping": json.dumps({"student_code": 0, "amounts": [{"column": 1, "schedule": str(self.tariff.pk)}]}),
        })

    def test_unknown_payment_is_not_a_zero_or_debt(self):
        response = self.prepare_history("")
        self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(HistoricalFinancialMigration.objects.exists())
        self.assertFalse(FeeCharge.objects.exists())

    def test_approval_rejects_stale_tariff(self):
        response = self.prepare_history()
        self.assertEqual(response.status_code, 200, response.content)
        batch_id = response.json()["batch"]
        FeeSchedule.objects.filter(pk=self.tariff.pk).update(amount=60000)
        self.client.force_login(self.comptabilite)
        result = self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/{batch_id}/approve",
                                  {"reason": "Justificatif vérifié"})
        self.assertEqual(result.status_code, 422, result.content)
        self.assertFalse(FeeCharge.objects.exists())
        self.assertFalse(HistoricalFeeAdjustment.objects.exists())
        self.assertEqual(HistoricalFinancialMigration.objects.get(pk=batch_id).status, "prepared")

    def test_credit_changes_balance_not_received(self):
        response = self.prepare_history()
        self.assertEqual(response.status_code, 200, response.content)
        batch_id = response.json()["batch"]
        self.client.force_login(self.comptabilite)
        result = self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/{batch_id}/approve",
                                  {"reason": "Justificatif vérifié"})
        self.assertEqual(result.status_code, 200, result.content)
        from .finance_views import charge_data
        from .overview_views import enrollment_balances
        from .year_closure import annual_closure_snapshot
        charge = FeeCharge.objects.get(enrollment=self.enrollment)
        data = charge_data(charge)
        self.assertEqual(data["historical_credit"], "25000.00")
        self.assertEqual(data["recorded_payments"], "0.00")
        self.assertEqual(data["balance"], "25000.00")
        _, balances = enrollment_balances(self.school, [self.enrollment.pk])
        self.assertEqual(balances[self.enrollment.pk]["paid"], Decimal("25000"))
        summary = self.client.get(f"/api/v1/schools/{self.school.pk}/finance/summary?year={self.year.pk}")
        self.assertEqual(summary.status_code, 200, summary.content)
        totals = summary.json()["currencies"]["XAF"]
        self.assertEqual(totals["paid"], "0.00")
        self.assertEqual(totals["historical_credit"], "25000.00")
        self.assertEqual(totals["balance"], "25000.00")
        snapshot = annual_closure_snapshot(self.school, self.year)["finance"]["XAF"]
        self.assertEqual(Decimal(snapshot["received"]), 0)
        self.assertEqual(Decimal(snapshot["historical_credit"]), 25000)
        self.assertEqual(Decimal(snapshot["outstanding"]), 25000)
        self.assertFalse(FeePayment.objects.exists())

    def test_financial_batch_review_only_authorized_and_own_prepared(self):
        prepared = self.prepare_history()
        self.assertEqual(prepared.status_code, 200, prepared.content)
        batch = prepared.json()["batch"]
        root = f"/api/v1/schools/{self.school.pk}/imports/finance/"
        self.assertTrue(self.client.get(root+"batches").json()["can_prepare"])
        detail = self.client.get(root+batch)
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["can_cancel"])
        self.assertFalse(detail.json()["can_approve"])
        self.assertEqual(detail.json()["entries"][0]["student_code"], "0001")
        self.client.force_login(self.comptabilite)
        self.assertTrue(self.client.get(root+batch).json()["can_approve"])
        self.assertFalse(self.client.get(root+"batches").json()["can_prepare"])
        self.client.force_login(self.secretary)
        self.assertEqual(self.client.get(root+batch).status_code, 403)
        self.assertEqual(self.client.get(root+"batches").status_code, 403)
        self.assertFalse(FeeCharge.objects.exists())

    def test_multiclass_maps_real_enrollment_not_claimed_class(self):
        klass = self.enrollment.classroom
        other = AcademicClass.objects.create(school=self.school, year=self.year, level=klass.level,
            code="6b", name="6B")
        student = Student.objects.create(school=self.school, student_code="0002", first_name="Autre", last_name="Fictif")
        Enrollment.objects.create(school=self.school, year=self.year, student=student, classroom=other,
                                  enrolled_on=self.today-timedelta(days=60))
        cheap = self.tariff
        cheap.classroom = klass
        cheap.scope_key = str(klass.pk)
        cheap.save(update_fields=["classroom", "scope_key"])
        expensive = FeeSchedule.objects.create(school=self.school, year=self.year, classroom=other,
            scope_key=str(other.pk), code=cheap.code, label="Scolarité 6B", amount=75000,
            currency="XAF", due_date=cheap.due_date)
        mapping = json.dumps({"student_code": 0, "amounts": [{"column": 1,
            "schedules": [str(cheap.pk), str(expensive.pk)]}]})
        response = self.preview("0001;25000\n0002;25000", mapping=mapping)
        self.assertEqual(response.status_code, 200, response.content)
        cells = [row["cells"][0] for row in response.json()["rows"]]
        self.assertEqual([c["net_due"] for c in cells], ["50000.00","75000.00"])
        self.assertEqual([c["declared_balance"] for c in cells], ["25000.00","50000.00"])
        self.assertEqual([c["schedule"] for c in cells], [str(cheap.pk),str(expensive.pk)])
        self.assertFalse(FeeCharge.objects.exists())
        response = self.preview("0001;25000\n0002;25000")
        self.assertEqual(response.json()["rows"][1]["cells"][0]["status"], "invalid")
        self.client.force_login(self.econome)
        response = self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/prepare", {
            "file": SimpleUploadedFile("classes.csv", b"Matricule;Octobre\n0001;25000\n0002;25000"),
            "year":str(self.year.pk), "cutoff":self.today.isoformat(), "mapping":mapping,
        })
        self.assertEqual(response.status_code, 200, response.content)
        batch = response.json()["batch"]
        self.client.force_login(self.comptabilite)
        approved = self.client.post(f"/api/v1/schools/{self.school.pk}/imports/finance/{batch}/approve",
                                    {"reason":"Registre historique contrôlé"})
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(FeeCharge.objects.count(), 2)
        self.assertEqual(HistoricalFeeAdjustment.objects.count(), 2)
        self.assertFalse(FeePayment.objects.exists())

    def test_multiclass_rejects_mixed_periods(self):
        other = FeeSchedule.objects.create(school=self.school, year=self.year, code="novembre",
            label="Novembre", amount=50000, currency="XAF")
        mapping = json.dumps({"student_code": 0, "amounts": [{"column":1,
            "schedules":[str(self.tariff.pk),str(other.pk)]}]})
        self.assertEqual(self.preview(mapping=mapping).status_code, 422)

    def test_preparation_ignores_mapping_order_and_can_replace_cancelled_batch(self):
        other_tariff = FeeSchedule.objects.create(
            school=self.school, year=self.year, code="novembre",
            label="Novembre", amount=50000, currency="XAF",
        )
        amounts = [
            {"column": 1, "schedule": str(self.tariff.pk)},
            {"column": 2, "schedule": str(other_tariff.pk)},
        ]
        endpoint = f"/api/v1/schools/{self.school.pk}/imports/finance"
        self.client.force_login(self.econome)

        def prepare(mapping):
            return self.client.post(f"{endpoint}/prepare", {
                "file": SimpleUploadedFile("historique.csv", b"Matricule;Octobre;Novembre\n0001;0;5000"),
                "year": str(self.year.pk), "cutoff": self.today.isoformat(),
                "mapping": json.dumps({"student_code": 0, "amounts": mapping}),
            })

        first = prepare(amounts)
        self.assertEqual(first.status_code, 200, first.content)
        batch = first.json()["batch"]
        duplicate = prepare([
            {"column": item["column"], "schedules": [item["schedule"]]}
            for item in reversed(amounts)
        ])
        self.assertEqual(duplicate.status_code, 200, duplicate.content)
        self.assertEqual(duplicate.json()["batch"], batch)
        self.assertTrue(duplicate.json()["idempotent"])

        cancelled = self.client.post(f"{endpoint}/{batch}/cancel", {"reason": "Erreur initiale"})
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        replacement = prepare(amounts[::-1])
        self.assertEqual(replacement.status_code, 200, replacement.content)
        self.assertNotEqual(replacement.json()["batch"], batch)
        self.assertEqual(prepare(amounts).json()["batch"], replacement.json()["batch"])
        self.assertEqual(HistoricalFinancialMigration.objects.count(), 2)
        self.assertFalse(FeeCharge.objects.exists())

    def test_reversal_is_independent_audited_and_keeps_original_entries(self):
        from .finance_views import cleared_total

        self.client.force_login(self.econome)
        response = self.prepare_history()
        self.assertEqual(response.status_code, 200, response.content)
        batch = response.json()["batch"]
        root = f"/api/v1/schools/{self.school.pk}/imports/finance/{batch}"
        reason = {"reason": "Registre rectifié et contrôlé"}
        self.client.force_login(self.comptabilite)
        self.assertEqual(self.client.post(root+"/approve", reason).status_code, 200)
        charge = FeeCharge.objects.get()
        self.assertEqual(cleared_total(charge), Decimal("25000"))
        self.assertEqual(self.client.post(root+"/reversal/confirm", reason).status_code, 409)

        self.client.force_login(self.econome)
        requested = self.client.post(root+"/reversal/request", reason)
        self.assertEqual(requested.status_code, 200, requested.content)
        self.assertTrue(self.client.post(root+"/reversal/request", reason).json()["idempotent"])
        self.assertEqual(cleared_total(charge), Decimal("25000"))
        role = SchoolRole.objects.get(school=self.school, code="econome")
        role.permissions = [*role.permissions, "school.finance.approve"]
        role.save(update_fields=["permissions"])
        self.assertEqual(self.client.post(root+"/reversal/confirm", reason).status_code, 403)
        self.assertEqual(self.client.post(root+"/reversal/withdraw", reason).status_code, 200)
        self.assertIsNone(HistoricalFinancialMigration.objects.get(pk=batch).reversal_requested_at)
        self.assertEqual(self.client.post(root+"/reversal/request", reason).status_code, 200)

        self.client.force_login(self.comptabilite)
        self.year.status = AcademicYear.STATUS_CLOSED
        self.year.save(update_fields=["status"])
        self.assertEqual(self.client.post(root+"/reversal/confirm", reason).status_code, 409)
        self.year.status = AcademicYear.STATUS_CURRENT
        self.year.save(update_fields=["status"])
        confirmed = self.client.post(root+"/reversal/confirm", reason)
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        self.assertTrue(self.client.post(root+"/reversal/confirm", reason).json()["idempotent"])
        self.assertEqual(cleared_total(charge), Decimal("0"))
        record = HistoricalFinancialMigration.objects.get(pk=batch)
        self.assertEqual(record.status, record.STATUS_REVERSED)
        self.assertEqual(record.reversal_requested_by, self.econome)
        self.assertEqual(record.reversed_by, self.comptabilite)
        self.assertEqual(record.reversal_reason, reason["reason"])
        self.assertEqual(record.reversal_evidence, reason["reason"])
        self.assertEqual(HistoricalFeeAdjustment.objects.get(batch=record).amount, Decimal("25000"))
        self.assertFalse(FeePayment.objects.exists())

        self.client.force_login(self.econome)
        self.assertEqual(self.client.post(root+"/cancel", reason).status_code, 409)
        replacement = self.prepare_history()
        self.assertEqual(replacement.status_code, 200, replacement.content)
        self.assertNotEqual(replacement.json()["batch"], batch)
        self.client.force_login(self.comptabilite)
        replacement_root = root.rsplit("/", 1)[0] + "/" + replacement.json()["batch"]
        self.assertEqual(self.client.post(replacement_root+"/approve", reason).status_code, 200)
        self.assertEqual(cleared_total(charge), Decimal("25000"))
        self.assertFalse(FeePayment.objects.exists())
