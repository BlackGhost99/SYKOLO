import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from .test_finance_batch import MultiFeeReceiptTests
from .models import SchoolMember, SchoolRole
from .services import has_permission


class FinancialControlTests(TestCase):
    setUp = MultiFeeReceiptTests.setUp
    login = MultiFeeReceiptTests.login
    payload = MultiFeeReceiptTests.payload
    send = MultiFeeReceiptTests.send
    post_closing = MultiFeeReceiptTests.post_closing
    approve_closing = MultiFeeReceiptTests.approve_closing

    def post(self, path, data):
        return self.client.post(self.base + path, json.dumps(data), content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

    def controller(self):
        user = get_user_model().objects.create_user("independent-controller")
        SchoolMember.objects.create(school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code="comptabilite"))
        return user

    def test_roles_and_cumulative_functions(self):
        controller = self.controller()
        self.assertFalse(has_permission(controller, self.school, "school.finance.receive"))
        self.assertFalse(has_permission(controller, self.school, "school.finance.manage"))
        self.assertFalse(has_permission(self.cashier, self.school, "school.finance.reverse"))
        member = SchoolMember.objects.get(user=self.cashier, school=self.school)
        member.additional_roles.add(SchoolRole.objects.get(school=self.school, code="comptabilite"))
        receipt = self.send(self.payload()).json()
        self.assertEqual(self.post("payments/"+receipt["payments"][0]["id"]+"/void", {"reason":"Erreur documentée du caissier"}).status_code, 403)
        closure = self.post_closing("30000").json()
        self.assertEqual(self.approve_closing(closure["id"]).status_code, 403)
        access = self.client.get(f"/api/v1/schools/{self.school.pk}/my-access").json()
        self.assertIn("econome", access["roles"])
        self.assertIn("comptabilite", access["roles"])
        foreign = SchoolRole.objects.get(school=self.other_school, code="tarification")
        member.additional_roles.add(foreign)
        self.assertFalse(has_permission(self.cashier, self.school, "school.finance.manage"))

    def test_transfer_limits_and_independent_receipt_control(self):
        self.send(self.payload())
        closure = self.post_closing("30000").json()
        path = "cash/closings/"+closure["id"]+"/transfers"
        data = {"kind":"handover", "amount":"30000", "reference":"PIECE-1", "destination":"Trésorerie", "day":timezone.localdate().isoformat()}
        self.assertEqual(self.post(path,data).status_code,409)
        controller = self.controller()
        self.login(controller)
        self.assertEqual(self.approve_closing(closure["id"]).status_code,200)
        self.login(self.cashier)
        transfer = self.post(path,data)
        self.assertEqual(transfer.status_code,201,transfer.content)
        self.assertEqual(self.post(path,data).status_code,409)
        deposit = {**data,"kind":"deposit","reference":"BANQUE-1"}
        self.assertEqual(self.post(path,deposit).status_code,409)
        approval = path+"/"+transfer.json()["id"]+"/approve"
        self.login(controller)
        self.assertEqual(self.post(approval,{}).status_code,200)
        self.login(self.cashier)
        self.assertEqual(self.post(path,{**deposit,"amount":"30001"}).status_code,409)
        deposit_response = self.post(path,deposit)
        self.assertEqual(deposit_response.status_code,201,deposit_response.content)
        member = SchoolMember.objects.get(school=self.school,user=self.cashier)
        member.additional_roles.add(SchoolRole.objects.get(school=self.school,code="comptabilite"))
        self.assertEqual(self.post(path+"/"+deposit_response.json()["id"]+"/approve",{}).status_code,403)
        self.login(controller)
        self.assertEqual(self.post(path+"/"+deposit_response.json()["id"]+"/approve",{}).status_code,200)

    def test_overview_explicit_currency_and_year(self):
        self.send(self.payload())
        base = f"/api/v1/schools/{self.school.pk}/overview/finance"
        eur = self.client.get(base+"?currency=EUR").json()
        self.assertEqual(eur["currency"],"EUR")
        self.assertEqual(eur["outstanding"],"10000.00")
        self.assertEqual(eur["today"]["total"],"0.00")
        self.assertEqual(set(eur["currencies"]),{"EUR","XAF"})
