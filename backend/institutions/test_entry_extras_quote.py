"""A6b1 quotation is not a sale: school isolation and decimal safety."""
import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicYear
from .entry_extras_catalog import SCOPE
from .finance_models import FeeCharge, FeePayment
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole, SchoolSetting


class ExtrasQuoteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.reader = User.objects.create_user(username="quote-reader", password="Safepass-Extras-2026!")
        self.other = User.objects.create_user(username="quote-outsider", password="Safepass-Extra-Else!")
        self.school = School.objects.create(
            organization=Organization.objects.create(name="Unité"), name="Unité")
        self.foreign = School.objects.create(
            organization=Organization.objects.create(name="Autre"), name="Autre")
        role = SchoolRole.objects.create(school=self.school, code="compta_read",
                                         label="Comptable lecteur",
                                         permissions=["school.view", "school.finance.read"])
        SchoolMember.objects.create(school=self.school, user=self.reader, role=role)
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        self.other_year = AcademicYear.objects.create(
            school=self.foreign, code="2026-2027", name="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        self.lunch, self.bus, self.archived, self.euro = [str(uuid4()) for _ in range(4)]
        self.items = [
            {"id":self.lunch,"code":"CANTINE-REPAS","group":"B03","kind":"produit",
             "label":"Repas midi","variant":"Normal","unit":"repas","unit_price":"2500.00",
             "currency":"XAF","academic_year":str(self.year.pk),"active":True},
            {"id":self.bus,"code":"BUS-MOIS","group":"B04","kind":"service",
             "label":"Transport","variant":"","unit":"mois","unit_price":"7500.50",
             "currency":"XAF","academic_year":None,"active":True},
            {"id":self.archived,"code":"UNIFORME-OLD","group":"B01","kind":"produit",
             "label":"Ancien uniforme","variant":"","unit":"unité","unit_price":"5000.00",
             "currency":"XAF","academic_year":None,"active":False},
            {"id":self.euro,"code":"EURO-TEST","group":"B02","kind":"produit",
             "label":"Article devisé","variant":"","unit":"unité","unit_price":"10.00",
             "currency":"EUR","academic_year":None,"active":True},
        ]
        SchoolSetting.objects.create(
            school=self.school, scope_key=SCOPE,
            scope={"module":"income", "kind":"extras_catalog"},
            values={"items":self.items}, revision=3)
        self.url = f"/api/v1/schools/{self.school.pk}/finance/extras/quote"
        self.client.force_login(self.reader)

    def quote(self, items=None, year=None):
        return self.client.post(self.url, data=json.dumps({
            "academic_year": year if year is not None else str(self.year.pk),
            "items": items if items is not None else [
                {"id":self.lunch,"quantity":2}, {"id":self.bus,"quantity":1}],
        }), content_type="application/json")

    def test_success_with_exact_price_snapshot_and_no_cash_event(self):
        response = self.quote()
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["total"], "12500.50")
        self.assertEqual(data["currency"], "XAF")
        self.assertEqual(data["catalog_revision"], 3)
        self.assertEqual(data["lines"][0]["line_total"], "5000.00")
        self.assertEqual(data["lines"][1]["unit_price"], "7500.50")
        self.assertEqual(data["lines"][0]["quantity"], 2)
        self.assertEqual(data["state"], "estimation_non_enregistree")
        self.assertFalse(data["payable"])
        self.assertFalse(data["recorded_sale"])
        self.assertFalse(data["recorded_payment"])
        self.assertFalse(data["stock_reserved"])
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(FeeCharge.objects.count(), 0)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(SchoolAudit.objects.filter(school=self.school).count(), 0)
        self.assertEqual(SchoolSetting.objects.get(school=self.school, scope_key=SCOPE).revision, 3)

    def test_invalid_quantities_duplicates_missing_items_and_multicurrency(self):
        for quantity in (0, -1, True, 2.5, "3", 1001, None):
            result = self.quote([{"id":self.bus,"quantity":quantity}])
            self.assertEqual(result.status_code, 422, (quantity,result.content))
        self.assertEqual(self.quote([{"id":self.lunch,"quantity":1},
                                     {"id":self.lunch,"quantity":1}]).status_code, 422)
        self.assertEqual(self.quote([{"id":self.archived,"quantity":1}]).status_code, 404)
        self.assertEqual(self.quote([{"id":str(uuid4()),"quantity":1}]).status_code, 404)
        self.assertEqual(self.quote([{"id":self.lunch,"quantity":1},
                                     {"id":self.euro,"quantity":1}]).status_code, 422)
        self.assertEqual(self.quote([]).status_code, 422)
        self.assertEqual(self.quote([{"id":self.bus,"quantity":1}]*31).status_code, 422)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_tariff_year_isolation_and_permissions(self):
        self.assertEqual(self.quote([{"id":self.lunch,"quantity":1}],
                                    year=str(self.other_year.pk)).status_code, 422)
        self.assertEqual(self.quote([{"id":self.lunch,"quantity":1}],
                                    year=str(uuid4())).status_code, 422)
        no_year = self.client.post(self.url, data=json.dumps({
            "academic_year":None,"items":[{"id":self.lunch,"quantity":1}]
        }), content_type="application/json")
        self.assertEqual(no_year.status_code, 422)
        self.assertEqual(self.client.post(
            f"/api/v1/schools/{self.foreign.pk}/finance/extras/quote",
            data=json.dumps({"items":[{"id":self.bus,"quantity":1}]}),
            content_type="application/json").status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.quote().status_code,403)
        self.client.logout()
        self.assertIn(self.quote().status_code,(401,403))

    def test_price_comes_from_catalog_not_from_caller(self):
        tampered = self.client.post(self.url, data=json.dumps({
            "academic_year":str(self.year.pk),
            "items":[{"id":self.lunch,"quantity":1,"unit_price":"0.01"}],
        }), content_type="application/json")
        self.assertEqual(tampered.status_code, 422)
        plain = self.quote([{"id":self.bus,"quantity":1}])
        self.assertEqual(plain.json()["total"], "7500.50")
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_tampered_catalog_price_is_rejected_not_roundtrip(self):
        setting = SchoolSetting.objects.get(school=self.school, scope_key=SCOPE)
        items = list(setting.values["items"])
        items[0] = {**items[0], "unit_price": "NaN"}
        setting.values = {"items":items}
        setting.save(update_fields=["values"])
        self.assertEqual(self.quote([{"id":self.lunch,"quantity":1}]).status_code, 422)
