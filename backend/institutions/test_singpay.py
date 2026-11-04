"""No provider network, credentials or real debits in these tests."""
import json
import uuid
from decimal import Decimal
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.db import connection, close_old_connections

from .finance_models import FeeCharge, FeeSchedule, FeePayment
from .models import OrganizationMember
from .parent_models import GuardianAccountLink
from .parent_payment_service import encrypt_secret, ProviderError
from .singpay_models import SingPayMerchant, SingPayIntent, SingPayEvent
from .singpay_service import reconcile, fee_quote, normalize_phone, verified_transaction
from . import test_parent_portal as portal_fixture


@override_settings(YEM_SINGPAY_ENABLED=True, YEM_PAYMENTS_LIVE_ENABLED=True,
                   YEM_PAYMENT_ENCRYPTION_KEY="test-only-encryption-abcdefghijklmnopqrstuvwxyz",
                   AUTH_PUBLIC_BASE_URL="https://school.example.test")
class SingPayTests(TestCase):
    login = portal_fixture.ParentPortalTests.login
    write = portal_fixture.ParentPortalTests.write

    def setUp(self):
        portal_fixture.ParentPortalTests.setUp(self)
        GuardianAccountLink.objects.create(school=self.school, guardian=self.guardians[0],
                                          user=self.parent_a, verified_by=self.director)
        self.login(self.parent_a)
        schedule = FeeSchedule.objects.create(school=self.school, year=self.year, code="novembre",
            label="Mensualité novembre", amount=10000, currency="XAF")
        self.charge = FeeCharge.objects.create(school=self.school, enrollment=self.enrollments[0],
            schedule=schedule, label=schedule.label, amount=schedule.amount, currency="XAF")
        self.merchant = SingPayMerchant.objects.create(school=self.school, wallet_id="wallet-school-a",
            disbursement_id="destination-a", beneficiary_name="École P15", contract_reference="test-contract",
            encrypted_credentials=encrypt_secret(json.dumps({"client_id":"fake-id", "client_secret":"fake-secret"})),
            mode="live", enabled=True, fee_basis_points=250, fee_fixed_xaf=25)
        self.root = f"/api/v1/parents/singpay/charge/{self.charge.pk}"
        self.body = {"amount_xaf":2500,"channel":"airtel","phone":"074000000",
                     "idempotency_key":str(uuid.uuid4()),"merchant_revision":1}

    def start(self, body=None):
        with patch("institutions.singpay_service.provider_request", return_value={"status":{"success":True}}) as provider:
            response = self.write(self.root+"/pay", body or self.body)
        return response, provider

    def evidence(self, intent, **changes):
        return {"id":"provider-tx-1", "reference":intent.reference, "amount":str(intent.amount_xaf),
                "client_msisdn":intent.phone, "portefeuille":{"id":intent.wallet_id},
                "isTransfer":False, "status":"Terminate", "result":"Success", **changes}

    def test_initiation_is_pending_not_credit_and_replay_is_one_debit(self):
        response, provider = self.start()
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(response.json()["state"],"pending")
        self.assertFalse(FeePayment.objects.exists())
        replay, second = self.start()
        self.assertEqual(replay.status_code,200)
        second.assert_not_called()
        self.assertEqual(SingPayIntent.objects.count(),1)
        sent = provider.call_args.args[3]
        self.assertEqual(sent["portefeuille"],self.merchant.wallet_id)
        self.assertEqual(sent["disbursement"],self.merchant.disbursement_id)
        self.assertIs(sent["isTransfer"],False)

    def test_replay_conflict_and_another_key_do_not_debit(self):
        self.start()
        response, provider = self.start({**self.body,"amount_xaf":3000})
        self.assertEqual(response.status_code,409)
        provider.assert_not_called()
        response, provider = self.start({**self.body,"idempotency_key":str(uuid.uuid4())})
        self.assertEqual(response.status_code,409)
        provider.assert_not_called()

    def test_timeout_is_unknown_and_never_retried(self):
        with patch("institutions.singpay_service.provider_request", side_effect=ProviderError("timeout")):
            result = self.write(self.root+"/pay",self.body)
        self.assertEqual(result.json()["state"],"unknown")
        replay, provider = self.start()
        provider.assert_not_called()
        self.assertEqual(replay.json()["state"],"unknown")

    def test_verified_partial_credit_exactly_once_and_receipt(self):
        self.start()
        intent=SingPayIntent.objects.get()
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent)):
            reconcile(intent,self.merchant)
            reconcile(intent,self.merchant)
        self.assertEqual(FeePayment.objects.count(),1)
        self.assertEqual(FeePayment.objects.get().amount,Decimal(2500))
        intent.refresh_from_db()
        self.assertEqual(intent.state,"success")
        response=self.client.get(f"/api/v1/parents/singpay/payments/{intent.pk}/receipt")
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["fee_xaf"],88)
        # Remaining monthly debt may receive a new partial payment.
        result,_=self.start({**self.body,"idempotency_key":str(uuid.uuid4()),"amount_xaf":7500})
        self.assertEqual(result.status_code,201,result.content)

    def test_test_wallet_never_credits_real_ledger_or_receipt(self):
        self.merchant.mode="test";self.merchant.save()
        self.start();intent=SingPayIntent.objects.get()
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent)):
            reconcile(intent,self.merchant)
        intent.refresh_from_db()
        self.assertEqual(intent.state,"test_success")
        self.assertFalse(FeePayment.objects.exists())
        self.assertEqual(self.client.get(f"/api/v1/parents/singpay/payments/{intent.pk}/receipt").status_code,409)

    def test_wrong_amount_wallet_reference_phone_stage_never_credits(self):
        self.start();intent=SingPayIntent.objects.get()
        for changes in ({"amount":"NaN"},{"amount":"2500.01"},{"amount":"2499"},
                        {"portefeuille":"other-school"},{"reference":"forged"},{"client_msisdn":"062000000"},
                        {"isTransfer":True},{"status":"Disbursement"},{"result":"Approved"},{"amount":None}):
            with self.subTest(changes=changes):
                self.assertIsNone(verified_transaction(intent,self.evidence(intent,**changes)))
                with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent,**changes)):
                    reconcile(intent,self.merchant)
                self.assertFalse(FeePayment.objects.exists())

    def test_manual_payment_race_preserves_unallocated_provider_money(self):
        self.start();intent=SingPayIntent.objects.get()
        FeePayment.objects.create(school=self.school,charge=self.charge,idempotency_key=uuid.uuid4(),
            amount=9000,currency="XAF",method="virement",paid_on="2026-11-01")
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent)):
            reconcile(intent,self.merchant)
        intent.refresh_from_db()
        self.assertEqual(intent.state,"review")
        self.assertEqual(FeePayment.objects.count(),1)
        self.assertTrue(SingPayEvent.objects.filter(intent=intent,kind="verified").exists())

    def test_cross_school_and_revoked_parent_access(self):
        self.start();intent=SingPayIntent.objects.get()
        self.login(self.parent_other)
        self.assertEqual(self.client.get(self.root+"/quote").status_code,404)
        self.assertEqual(self.write(f"/api/v1/parents/singpay/payments/{intent.pk}/refresh",{}).status_code,404)
        self.login(self.parent_a)
        GuardianAccountLink.objects.filter(user=self.parent_a).update(active=False)
        self.assertEqual(self.client.get(self.root+"/quote").status_code,404)

    def test_disabled_gates_and_csrf(self):
        with override_settings(YEM_SINGPAY_ENABLED=False):
            response, provider=self.start()
        self.assertEqual(response.status_code,503);provider.assert_not_called()
        response=self.client.post(self.root+"/pay",json.dumps(self.body),content_type="application/json")
        self.assertEqual(response.status_code,403)

    def test_callback_and_browser_cannot_credit(self):
        self.start();intent=SingPayIntent.objects.get()
        result=self.client.post("/api/v1/parents/singpay/webhook",json.dumps(self.evidence(intent)),content_type="application/json")
        self.assertEqual(result.status_code,503)
        self.assertEqual(self.client.get(f"/api/v1/parents/singpay/payments/{intent.pk}/refresh?success=true").status_code,405)
        self.assertFalse(FeePayment.objects.exists())

    def test_merchant_config_owner_only_secrets_never_returned_and_no_activation(self):
        self.login(self.director)
        path=f"/api/v1/schools/{self.school.pk}/singpay/merchant"
        self.assertEqual(self.client.get(path).status_code,403)
        OrganizationMember.objects.create(organization=self.school.organization,user=self.director,role="founder")
        result=self.client.get(path)
        self.assertEqual(result.status_code,200)
        self.assertNotIn("fake-secret",result.content.decode())
        body={"revision":1,"wallet_id":"wallet-school-a","disbursement_id":"destination-a",
              "client_id":"fake-id","client_secret":"fake-secret","beneficiary_name":"École P15",
              "contract_reference":"test-contract","mode":"live","enabled":True,"fee_basis_points":250,"fee_fixed_xaf":25}
        self.assertEqual(self.write(path,body).status_code,409)

    def test_changed_merchant_cannot_reconcile_old_payment(self):
        self.start();intent=SingPayIntent.objects.get()
        self.merchant.wallet_id="other-wallet"
        with patch("institutions.singpay_service.provider_request") as provider:
            with self.assertRaises(ProviderError):reconcile(intent,self.merchant)
        provider.assert_not_called()

    def test_fee_rounding_and_phone(self):
        self.assertEqual(fee_quote(self.merchant,2500)["total_parent_xaf"],2500)
        self.assertEqual(fee_quote(self.merchant,2500)["fee_xaf"],88)
        self.assertEqual(normalize_phone("+24174000000","airtel"),"074000000")
        with self.assertRaises(ValueError):normalize_phone("062000000","airtel")

    def test_cashier_cannot_reconcile_or_change_merchant(self):
        from .models import SchoolMember, SchoolRole
        SchoolMember.objects.filter(school=self.school,user=self.director).update(role=SchoolRole.objects.get(school=self.school,code="econome"))
        self.login(self.director)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/singpay/reconciliation").status_code,403)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/singpay/merchant").status_code,403)

    def test_refund_signal_preserves_credit_and_requires_accounting_review(self):
        self.start();intent=SingPayIntent.objects.get()
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent)):
            reconcile(intent,self.merchant)
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent,status="Refund")):
            reconcile(intent,self.merchant)
        intent.refresh_from_db()
        self.assertEqual(intent.state,"refund_review")
        self.assertEqual(FeePayment.objects.count(),1)

    def test_settlement_is_separate_and_requires_another_approver(self):
        from .models import SchoolMember, SchoolRole
        self.start();intent=SingPayIntent.objects.get()
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent)):
            reconcile(intent,self.merchant)
        self.login(self.director)
        path=f"/api/v1/schools/{self.school.pk}/singpay/payments/{intent.pk}/settlement"
        body={"statement_reference":"Statement-2026-001", "received_net_xaf":2400,"observed_fee_xaf":100}
        self.assertEqual(self.write(path,{**body,"received_net_xaf":2500}).status_code,422)
        result=self.write(path,body)
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()["fee_variance_xaf"],12)
        self.assertEqual(self.write(path,{"approve":True}).status_code,403)
        SchoolMember.objects.create(school=self.school,user=self.outsider,
            role=SchoolRole.objects.get(school=self.school,code="comptabilite"))
        self.login(self.outsider)
        result=self.write(path,{"approve":True})
        self.assertTrue(result.json()["approved"])
        self.assertEqual(FeePayment.objects.count(),1)

    def test_manual_ledger_cannot_impersonate_singpay_or_void_verified_receipt(self):
        from .models import SchoolMember, SchoolRole
        self.start();intent=SingPayIntent.objects.get()
        with patch("institutions.singpay_service.provider_request", return_value=self.evidence(intent)):
            reconcile(intent,self.merchant)
        self.login(self.director)
        SchoolMember.objects.filter(school=self.school,user=self.director).update(role=SchoolRole.objects.get(school=self.school,code="comptabilite"))
        payment=FeePayment.objects.get()
        result=self.write(f"/api/v1/schools/{self.school.pk}/finance/payments/{payment.pk}/void",{"reason":"Ne pas annuler un paiement bancaire"})
        self.assertEqual(result.status_code,409)

    def test_provider_transport_never_follows_redirect_or_leaks_error(self):
        from urllib.error import HTTPError
        from .singpay_service import provider_request, NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,"redirect",{},"https://evil.example"))
        with patch("institutions.singpay_service.build_opener") as opener:
            opener.return_value.open.side_effect=HTTPError("url",401,"fake-secret",{},None)
            with self.assertRaises(ProviderError) as error:
                provider_request(self.merchant,"GET","/transaction/api/search/by-reference/YEMSP-test")
            self.assertNotIn("fake-secret",str(error.exception))
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_header("X-wallet"),self.merchant.wallet_id)
            self.assertEqual(request.get_header("X-client-secret"),"fake-secret")


@skipUnless(connection.vendor == "postgresql", "Real row-lock concurrency requires PostgreSQL; exercised by CI")
@override_settings(YEM_SINGPAY_ENABLED=True,YEM_PAYMENTS_LIVE_ENABLED=True,
                   YEM_PAYMENT_ENCRYPTION_KEY="test-only-encryption-abcdefghijklmnopqrstuvwxyz",
                   AUTH_PUBLIC_BASE_URL="https://school.example.test")
class SingPayConcurrencyTests(TransactionTestCase):
    login=SingPayTests.login
    write=SingPayTests.write

    def setUp(self):
        SingPayTests.setUp(self)

    def test_two_concurrent_requests_issue_only_one_debit(self):
        gate=Barrier(2)
        cookies=self.client.cookies.copy()
        def send():
            close_old_connections()
            client=Client(enforce_csrf_checks=True);client.cookies=cookies.copy()
            gate.wait(timeout=10)
            try:
                return client.post(self.root+"/pay",json.dumps(self.body),content_type="application/json",
                    HTTP_X_CSRFTOKEN=self.csrf).status_code
            finally:
                close_old_connections()
        with patch("institutions.singpay_service.provider_request",return_value={}) as provider:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results=list(executor.map(lambda _:send(),range(2)))
        self.assertEqual(sorted(results),[200,201])
        self.assertEqual(provider.call_count,1)
        self.assertEqual(SingPayIntent.objects.count(),1)


@override_settings(YEM_SINGPAY_ENABLED=True, YEM_PAYMENTS_LIVE_ENABLED=True,
                   YEM_PAYMENT_ENCRYPTION_KEY="test-only-encryption-abcdefghijklmnopqrstuvwxyz",
                   AUTH_PUBLIC_BASE_URL="https://school.example.test")
class SingPayAdmissionTests(TestCase):
    def setUp(self):
        from . import test_parent_payments
        self.fixture=test_parent_payments.ParentPaymentTests
        self.fixture.setUp(self)
        self.merchant=SingPayMerchant.objects.create(school=self.school,wallet_id="admission-wallet",
            disbursement_id="admission-destination",beneficiary_name=self.school.name,
            contract_reference="school-contract",encrypted_credentials=encrypt_secret("{}"),enabled=True,mode="live")
        self.application_id=self.fixture.apply(self)
        self.path=f"/api/v1/parents/singpay/admission/{self.application_id}/pay"
        self.body={"amount_xaf":2500,"channel":"airtel","phone":"074000000",
                   "idempotency_key":str(uuid.uuid4()),"merchant_revision":1}

    def login(self,user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,data):
        return self.client.post("/api/v1/"+path,json.dumps(data),content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def test_admission_payment_never_enrolls_or_credits_tuition(self):
        from .student_models import Enrollment
        with patch("institutions.singpay_service.provider_request",return_value={}):
            result=self.post(self.path.removeprefix("/api/v1/"),self.body)
        self.assertEqual(result.status_code,201,result.content)
        intent=SingPayIntent.objects.get()
        evidence={"id":"admission-provider-tx", "reference":intent.reference,"amount":"2500",
                  "client_msisdn":intent.phone,"portefeuille":intent.wallet_id,"isTransfer":False,
                  "status":"Terminate","result":"Success"}
        with patch("institutions.singpay_service.provider_request",return_value=evidence):
            reconcile(intent,self.merchant)
        intent.refresh_from_db();self.assertEqual(intent.state,"success")
        self.assertFalse(Enrollment.objects.exists());self.assertFalse(FeePayment.objects.exists())
        result=self.post(f"parents/applications/{self.application_id}/pay",{"channel":"airtel","phone":"+24174000000"})
        self.assertEqual(result.status_code,409)

    def test_paycentral_attempt_prevents_second_provider_debit(self):
        from .parent_payment_models import ParentPaymentAttempt
        ParentPaymentAttempt.objects.create(request_id=self.application_id,school=self.school,payer=self.parent,
            amount_xaf=2500,channel="airtel",payer_phone="+24174000000",merchant_reference="PC-TEST",state="unknown")
        with patch("institutions.singpay_service.provider_request") as provider:
            result=self.post(self.path.removeprefix("/api/v1/"),self.body)
        self.assertEqual(result.status_code,409);provider.assert_not_called()
