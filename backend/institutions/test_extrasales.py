"""A6b2b: independent write-disabled-by-default extras sales ledger."""
import json
from datetime import date
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from extrasales.models import ExtraPayment, ExtraSale, ExtraSaleLine
from .academic_models import AcademicYear
from .entry_extras_catalog import SCOPE
from .finance_models import FeeCharge, FeePayment
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole, SchoolSetting


class ExtrasSalesLedgerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.manager = User.objects.create_user(username="extra-manager", password="Safe-Extra-2026!")
        self.receiver = User.objects.create_user(username="extra-cashier", password="Safe-Cash-2026!")
        self.reader = User.objects.create_user(username="extra-reader", password="Safe-Read-2026!")
        self.foreign_user = User.objects.create_user(username="extra-foreign", password="Safe-Foreign-2026!")
        self.school = School.objects.create(
            organization=Organization.objects.create(name="École témoin"), name="École A")
        self.foreign = School.objects.create(
            organization=Organization.objects.create(name="École B"), name="École B")
        for code, user, perms in (
            ("extra_manager",self.manager,["school.view","school.finance.read","school.finance.manage"]),
            ("extra_receiver",self.receiver,["school.view","school.finance.read","school.finance.receive"]),
            ("extra_reader",self.reader,["school.view","school.finance.read"]),
        ):
            role = SchoolRole.objects.create(
                school=self.school, code=code, label=code, permissions=perms)
            SchoolMember.objects.create(school=self.school, user=user, role=role)
        foreign_role = SchoolRole.objects.create(
            school=self.foreign, code="foreign", label="Étranger",
            permissions=["school.view","school.finance.read","school.finance.manage","school.finance.receive"])
        SchoolMember.objects.create(school=self.foreign, user=self.foreign_user, role=foreign_role)
        self.year = AcademicYear.objects.create(
            school=self.school, name="2026-2027", code="2026-2027",
            start_date=date(2026,9,1), end_date=date(2027,7,31),
            status=AcademicYear.STATUS_CURRENT)
        self.service_id, self.product_id = str(uuid4()), str(uuid4())
        SchoolSetting.objects.create(
            school=self.school, scope_key=SCOPE,
            scope={"module":"income", "kind":"extras_catalog"}, revision=3,
            values={"items":[
                {"id":self.service_id,"code":"BUS-MOIS","group":"B04",
                 "kind":"service","label":"Transport mensuel","variant":"",
                 "unit":"mois","unit_price":"15000.00",
                 "currency":"XAF","academic_year":str(self.year.pk),"active":True},
                {"id":self.product_id,"code":"UNIFORME-M","group":"B01",
                 "kind":"produit","label":"Uniforme taille M","variant":"M",
                 "unit":"unité","unit_price":"7500.00",
                 "currency":"XAF","academic_year":str(self.year.pk),"active":True},
            ]})
        self.url=f"/api/v1/schools/{self.school.pk}/finance/extras/sales"
        self.request={
            "idempotency_key":"extra-sale-first-20261121",
            "buyer_label":"Responsable témoin",
            "academic_year":str(self.year.pk),
            "catalog_revision":3,
            "items":[{"id":self.service_id,"quantity":1}],
        }
        self.client.force_login(self.manager)

    def post(self, url, body):
        return self.client.post(url,data=json.dumps(body),content_type="application/json")

    def create(self, payload=None):
        return self.post(self.url,self.request if payload is None else payload)

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=False)
    def test_write_switch_is_off_and_school_report_is_read_only(self):
        self.assertEqual(self.create().status_code,503)
        read=self.client.get(self.url)
        self.assertEqual(read.status_code,200,read.content)
        self.assertEqual(read.json()["total"],0)
        self.assertEqual(ExtraSale.objects.count(),0)
        self.assertEqual(ExtraPayment.objects.count(),0)
        self.assertEqual(FeePayment.objects.count(),0)

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True)
    def test_confirmed_service_sale_snapshots_prices_and_idempotence(self):
        first=self.create()
        self.assertEqual(first.status_code,201,first.content)
        payload=first.json()
        self.assertEqual(payload["sale"]["billed"],"15000.00")
        self.assertEqual(payload["sale"]["received_manual_declared"],"0.00")
        self.assertEqual(payload["sale"]["outstanding"],"15000.00")
        self.assertFalse(payload["sale"]["revenue_certified"])
        self.assertEqual(ExtraSale.objects.count(),1)
        sale=ExtraSale.objects.get()
        self.assertEqual(sale.lines.count(),1)
        self.assertEqual(sale.lines.first().unit_price,15000)
        replay=self.create()
        self.assertEqual(replay.status_code,200,replay.content)
        self.assertTrue(replay.json()["unchanged"])
        reused=self.create({**self.request,"buyer_label":"Autre acheteur"})
        self.assertEqual(reused.status_code,409,reused.content)
        self.assertEqual(ExtraSale.objects.count(),1)
        self.assertEqual(SchoolAudit.objects.filter(event="extras_sale_confirmed").count(),1)
        self.assertEqual(FeeCharge.objects.count(),0)
        self.assertEqual(FeePayment.objects.count(),0)
        setting=SchoolSetting.objects.get(school=self.school,scope_key=SCOPE)
        settings=dict(setting.values)
        changed=[dict(row) for row in settings["items"]]
        changed[0]["unit_price"]="20000.00"
        setting.values={"items":changed}
        setting.revision=4
        setting.save(update_fields=["values","revision"])
        self.assertEqual(ExtraSaleLine.objects.get().unit_price,15000)
        self.assertEqual(self.create({
            **self.request,
            "idempotency_key":"second-sale-20261121",
        }).status_code,422)

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True)
    def test_partial_payments_do_not_count_as_tuition_or_certified_cash(self):
        sale_id=self.create().json()["sale"]["id"]
        url=f"{self.url}/{sale_id}/payments"
        self.client.force_login(self.receiver)
        pay={"idempotency_key":"receipt-extra-20261121-first",
             "amount":"5000.00","method":"especes"}
        first=self.post(url,pay)
        self.assertEqual(first.status_code,201,first.content)
        self.assertEqual(first.json()["sale"]["outstanding"],"10000.00")
        self.assertEqual(first.json()["sale"]["received_manual_declared"],"5000.00")
        self.assertEqual(first.json()["sale"]["received_provider_confirmed"],"0.00")
        repeat=self.post(url,pay)
        self.assertEqual(repeat.status_code,200,repeat.content)
        self.assertTrue(repeat.json()["unchanged"])
        self.assertEqual(ExtraPayment.objects.count(),1)
        self.assertEqual(self.post(url,{**pay,"amount":"100.00"}).status_code,409)
        self.assertEqual(self.post(url,{**pay,"idempotency_key":"bad-overpay-20261121",
                                       "amount":"15000.00"}).status_code,422)
        self.assertEqual(self.post(url,{**pay,"idempotency_key":"bad-psp-20261121",
                                       "method":"singpay"}).status_code,422)
        settled=self.post(url,{"idempotency_key":"final-cash-extra-20261121",
                               "amount":"10000.00","method":"especes"})
        self.assertEqual(settled.status_code,201,settled.content)
        self.assertEqual(settled.json()["sale"]["outstanding"],"0.00")
        self.assertEqual(ExtraPayment.objects.count(),2)
        self.assertEqual(FeePayment.objects.count(),0)
        self.assertEqual(FeeCharge.objects.count(),0)
        self.assertEqual(SchoolAudit.objects.filter(event="extras_payment_declared").count(),2)

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True)
    def test_school_year_stock_and_role_isolation(self):
        self.assertEqual(self.create({
            **self.request,"items":[{"id":self.product_id,"quantity":1}],
        }).status_code,422)
        self.assertEqual(ExtraSale.objects.count(),0)
        self.client.force_login(self.reader)
        self.assertEqual(self.create().status_code,403)
        self.client.force_login(self.foreign_user)
        self.assertIn(self.client.get(self.url).status_code,(403,404))
        self.assertIn(self.create().status_code,(403,404))
        self.client.force_login(self.manager)
        foreign_year=AcademicYear.objects.create(
            school=self.foreign,name="2026-2027",code="2026-2027",
            start_date=date(2026,9,1),end_date=date(2027,7,31))
        self.assertEqual(self.create({
            **self.request, "academic_year":str(foreign_year.pk)
        }).status_code,422)
        self.year.status=AcademicYear.STATUS_CLOSED
        self.year.save(update_fields=["status"])
        self.assertEqual(self.create().status_code,422)
        self.assertEqual(ExtraSale.objects.count(),0)

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True)
    def test_owner_read_only_does_not_expose_buyer_label(self):
        sale=self.create().json()["sale"]
        self.assertEqual(sale["buyer_label"],"Responsable témoin")
        self.client.force_login(self.reader)
        read=self.client.get(self.url)
        self.assertEqual(read.status_code,200,read.content)
        self.assertEqual(read.json()["total"],1)
        self.assertNotIn("buyer_label",read.json()["rows"][0])
        self.assertEqual(read.json()["rows"][0]["billed"],"15000.00")
        self.assertEqual(read.json()["rows"][0]["outstanding"],"15000.00")

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True)
    def test_bank_transfer_requires_reference_and_receiver_permission(self):
        sale_id = self.create().json()["sale"]["id"]
        url = f"{self.url}/{sale_id}/payments"
        transfer = {
            "idempotency_key": "extras-transfer-reference-20261121",
            "amount": "5000.00",
            "method": "virement",
        }
        self.client.force_login(self.manager)
        self.assertEqual(self.post(url, transfer).status_code, 403)
        self.client.force_login(self.receiver)
        self.assertEqual(self.post(url, transfer).status_code, 422)
        self.assertEqual(ExtraPayment.objects.count(), 0)
        with_reference = {**transfer, "reference": "BANK-2026-001"}
        result = self.post(url, with_reference)
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(ExtraPayment.objects.count(), 1)
        self.assertEqual(ExtraPayment.objects.get().method, "virement")
        self.assertEqual(ExtraPayment.objects.get().reference, "BANK-2026-001")

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=False)
    def test_disabled_environment_prevents_manual_receipts_too(self):
        with override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True):
            sale_id = self.create().json()["sale"]["id"]
        self.client.force_login(self.receiver)
        url = f"{self.url}/{sale_id}/payments"
        before = ExtraPayment.objects.count()
        response = self.post(url, {
            "idempotency_key": "extras-disabled-payment-20261121",
            "amount": "5000.00",
            "method": "especes",
        })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(ExtraPayment.objects.count(), before)

    @override_settings(YEM_EXTRA_SALES_WRITES_ENABLED=True)
    def test_extras_invoice_and_receipt_are_distinct_private_pdfs(self):
        sale_id = self.create().json()["sale"]["id"]
        invoice_url = f"{self.url}/{sale_id}/invoice"
        invoice = self.client.get(invoice_url)
        self.assertEqual(invoice.status_code, 200, invoice.content[:200])
        self.assertEqual(invoice["Content-Type"], "application/pdf")
        self.assertTrue(invoice.content.startswith(b"%PDF"))
        self.assertIn("attachment;", invoice["Content-Disposition"])
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(invoice_url).status_code, 403)
        self.client.force_login(self.receiver)
        self.assertEqual(self.client.get(invoice_url).status_code, 403)
        pay = self.post(f"{self.url}/{sale_id}/payments", {
            "idempotency_key": "extra-a9-receipt-20261121",
            "amount": "5000.00", "method": "especes",
        })
        self.assertEqual(pay.status_code, 201, pay.content)
        receipt_url = f"{self.url}/{sale_id}/payments/{pay.json()['payment_id']}/receipt"
        receipt = self.client.get(receipt_url)
        self.assertEqual(receipt.status_code, 200, receipt.content[:200])
        self.assertTrue(receipt.content.startswith(b"%PDF"))
        self.assertEqual(receipt["Cache-Control"], "private, no-store")
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(receipt_url).status_code, 403)
        self.client.force_login(self.foreign_user)
        self.assertIn(self.client.get(invoice_url).status_code, (403, 404))
        self.assertIn(self.client.get(receipt_url).status_code, (403, 404))
        self.assertEqual(FeePayment.objects.count(), 0)
