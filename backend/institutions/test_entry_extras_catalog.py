"""Isolation, audit and optimistic concurrency for extracurricular catalogue."""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicYear
from .finance_models import FeeCharge, FeePayment
from .entry_extras_catalog import SCOPE
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole, SchoolSetting


class ExtrasCatalogTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.writer = User.objects.create_user(username="extras-writer", password="Safe-Extras-2026!")
        self.reader = User.objects.create_user(username="extras-reader", password="Safe-Read-2026!")
        self.school = School.objects.create(organization=Organization.objects.create(name="Unité"), name="Campus A")
        self.foreign = School.objects.create(organization=Organization.objects.create(name="AWASSI"), name="Campus B")
        writer_role = SchoolRole.objects.create(
            school=self.school, code="extras_manager", label="Gestionnaire extras",
            permissions=["school.view", "school.finance.read", "school.finance.manage"])
        reader_role = SchoolRole.objects.create(
            school=self.school, code="extras_viewer", label="Lecteur extras",
            permissions=["school.view", "school.finance.read"])
        SchoolMember.objects.create(school=self.school, user=self.writer, role=writer_role)
        SchoolMember.objects.create(school=self.school, user=self.reader, role=reader_role)
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026-2027", code="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        self.other_year = AcademicYear.objects.create(
            school=self.foreign, name="2026-2027", code="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        self.url = f"/api/v1/schools/{self.school.pk}/finance/extras/catalog"
        self.item = {
            "code": "CANTINE-REPAS", "group": "B03", "kind": "produit",
            "label": "Repas du midi", "subcategory": "Restauration",
            "variant": "Standard", "unit": "repas", "unit_price": "2500.00",
            "currency": "XAF", "academic_year": str(self.year.pk), "active": True,
        }
        self.client.force_login(self.writer)

    def write(self, item=None, *, revision=0, action="upsert", reason="Catalogue scolaire contrôlé"):
        return self.client.post(self.url, data=json.dumps({
            "revision": revision, "action": action, "reason": reason,
            "item": item if item is not None else self.item,
        }), content_type="application/json")

    def test_create_read_update_archive_and_audit_without_financial_writes(self):
        first = self.client.get(self.url)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["revision"], 0)
        self.assertEqual(len(first.json()["groups"]), 8)
        self.assertFalse(first.json()["sales_recorded"])
        self.assertEqual(first.json()["items"], [])
        created = self.write()
        self.assertEqual(created.status_code, 201, created.content)
        row = created.json()["item"]
        self.assertEqual(row["unit_price"], "2500.00")
        self.assertEqual(created.json()["revision"], 1)
        self.assertEqual(FeeCharge.objects.count(), 0)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(SchoolAudit.objects.filter(school=self.school, event="income_extras_catalog").count(), 1)
        self.assertEqual(self.write(revision=0).status_code, 409)
        edited = self.write({**self.item, "id": row["id"], "unit_price": "3000.50"}, revision=1)
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertEqual(edited.json()["revision"], 2)
        archived = self.write({"id": row["id"]}, revision=2, action="archive")
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertFalse(archived.json()["item"]["active"])
        self.assertEqual(self.write({"id": row["id"]}, revision=3, action="archive").json()["unchanged"], True)
        self.assertEqual(SchoolAudit.objects.filter(school=self.school, event="income_extras_catalog").count(), 3)
        self.assertEqual(SchoolSetting.objects.filter(school=self.school, scope_key=SCOPE).count(), 1)
        self.assertEqual(self.client.get(self.url).json()["items"][0]["unit_price"], "3000.50")
        self.assertEqual(FeeCharge.objects.count(), 0)

    def test_role_and_school_separation(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.write().status_code, 403)
        self.client.force_login(self.writer)
        external_url = f"/api/v1/schools/{self.foreign.pk}/finance/extras/catalog"
        self.assertIn(self.client.get(external_url).status_code, (403, 404))
        bad = self.write({**self.item, "academic_year": str(self.other_year.pk)})
        self.assertEqual(bad.status_code, 422, bad.content)
        self.assertEqual(SchoolSetting.objects.filter(school=self.foreign).count(), 0)
        self.assertEqual(self.client.get(self.url).json()["revision"], 0)

    def test_refuses_invalid_prices_duplicate_codes_and_unsafe_mutations(self):
        for bad_price in (2500.0, "-1", "0", "NaN", "1e8", "2.000", "99999999999", "1,00"):
            response = self.write({**self.item, "unit_price": bad_price})
            self.assertEqual(response.status_code, 422, (bad_price, response.content))
        for changes in (
            {"code": "DEMO-SALES"}, {"group": "A01"}, {"kind": "depense"},
            {"currency": "XAF; DROP"}, {"label": ""}, {"active": "false"},
        ):
            self.assertEqual(self.write({**self.item, **changes}).status_code, 422, changes)
        self.assertEqual(self.write(reason="court").status_code, 422)
        self.assertEqual(self.write(revision=True).status_code, 422)
        good = self.write()
        self.assertEqual(good.status_code, 201, good.content)
        same_code = self.write({**self.item, "label": "Second repas"}, revision=1)
        self.assertEqual(same_code.status_code, 422, same_code.content)
        original_id = good.json()["item"]["id"]
        moved_family = self.write({**self.item, "id": original_id, "group": "B04"}, revision=1)
        self.assertEqual(moved_family.status_code, 422, moved_family.content)
        invalid_id = self.write({**self.item, "id": "not-a-uuid"}, revision=1)
        self.assertEqual(invalid_id.status_code, 422, invalid_id.content)
        self.assertEqual(SchoolAudit.objects.filter(event="income_extras_catalog").count(), 1)

    def test_services_and_variant_are_not_considered_as_sales(self):
        service = self.write({**self.item, "code": "NAVETTE-MOIS", "group": "B04",
                              "kind": "service", "label": "Navette mensuelle", "unit": "mois",
                              "variant": "Trajet 2", "academic_year": None,
                              "unit_price": "7500.00"})
        self.assertEqual(service.status_code, 201, service.content)
        result = self.client.get(self.url).json()
        self.assertEqual(result["items"][0]["kind"], "service")
        self.assertEqual(result["items"][0]["academic_year"], None)
        self.assertFalse(result["sales_recorded"])
        self.assertEqual(FeePayment.objects.count(), 0)
