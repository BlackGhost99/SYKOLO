import json
import uuid
from datetime import date
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from .models import Organization, OrganizationMember, School
from .academic_models import AcademicYear
from .subscription_models import PlatformSubscription, PlatformSubscriptionPayment
from .commercial_singpay_models import PlatformSingPayMerchant, SubscriptionSingPayIntent as Intent
from .commercial_singpay import reconcile
from .parent_payment_service import encrypt_secret, ProviderError

@override_settings(YEM_SINGPAY_ENABLED=True,YEM_PAYMENTS_LIVE_ENABLED=True,
 YEM_PAYMENT_ENCRYPTION_KEY="test-encryption-key-abcdefghijklmnopqrstuvwxyz",AUTH_PUBLIC_BASE_URL="https://yem.example.test")
class CommercialSingPayTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user(username="owner")
        self.other=get_user_model().objects.create_user(username="other")
        org=Organization.objects.create(name="Org")
        OrganizationMember.objects.create(organization=org,user=self.owner,role="founder")
        self.school=School.objects.create(organization=org,name="School")
        year=AcademicYear.objects.create(school=self.school,code="2026",name="2026",start_date=date(2026,9,1),end_date=date(2027,7,1))
        self.sub=PlatformSubscription.objects.create(year=year,lines=[],total_xaf=10000)
        self.merchant=PlatformSingPayMerchant.objects.create(wallet_id="platform-wallet",disbursement_id="platform-distribution",beneficiary_name="BWETEK",contract_reference="contract",mode="live",enabled=True,
          encrypted_credentials=encrypt_secret(json.dumps({"client_id":"fake","client_secret":"fake"})))
        self.path=f"/api/v1/schools/{self.school.pk}/owner/subscriptions/{self.sub.pk}/singpay"
        self.body={"amount_xaf":2500,"phone":"074000000","channel":"airtel","idempotency_key":str(uuid.uuid4()),"merchant_revision":1}
        self.client.force_login(self.owner)
        session=self.client.session;session["mfa_verified"]=True;session.save()
    def start(self,body=None):
        with patch("institutions.commercial_singpay.provider_request",return_value={}) as provider:
            r=self.client.post(self.path,json.dumps(body or self.body),content_type="application/json")
        return r,provider
    def evidence(self,row,**kwargs):
        return {"id":"tx-sub-1","reference":row.reference,"amount":row.amount_xaf,"client_msisdn":row.phone,"portefeuille":row.wallet_id,"isTransfer":False,"status":"Terminate","result":"Success",**kwargs}
    def test_verified_success_credits_once_and_receipt_is_private(self):
        r,p=self.start();self.assertEqual(r.status_code,201,r.content);p.assert_called_once()
        self.assertFalse(PlatformSubscriptionPayment.objects.exists())
        row=Intent.objects.get()
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row)):
            reconcile(row,self.merchant);reconcile(row,self.merchant)
        self.assertEqual(PlatformSubscriptionPayment.objects.count(),1)
        payment=PlatformSubscriptionPayment.objects.get();self.assertEqual(payment.amount_xaf,2500)
        quote=self.client.get(self.path).json();self.assertEqual(quote["balance_xaf"],7500)
        self.assertEqual(self.client.get(quote["payments"][0]["receipt"]).status_code,200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(quote["payments"][0]["receipt"]).status_code,403)
    def test_duplicate_key_never_reposts_and_conflict_refused(self):
        self.start();r,p=self.start();self.assertEqual(r.status_code,200);p.assert_not_called()
        r,p=self.start(self.body|{"amount_xaf":3000});self.assertEqual(r.status_code,409);p.assert_not_called()
        r,p=self.start(self.body|{"idempotency_key":str(uuid.uuid4())});self.assertEqual(r.status_code,409);p.assert_not_called()
    def test_unknown_response_never_retries_debit(self):
        with patch("institutions.commercial_singpay.provider_request",side_effect=ProviderError("timeout")):
            r=self.client.post(self.path,json.dumps(self.body),content_type="application/json")
        self.assertEqual(r.json()["state"],"unknown")
        r,p=self.start();p.assert_not_called();self.assertEqual(r.json()["state"],"unknown")
    def test_test_wallet_never_credits_contract(self):
        self.merchant.mode="test";self.merchant.save();self.start();row=Intent.objects.get()
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row)):
            row=reconcile(row,self.merchant)
        self.assertEqual(row.state,"test_success");self.assertFalse(PlatformSubscriptionPayment.objects.exists())
    def test_mismatch_and_overpayment_require_review(self):
        self.start();row=Intent.objects.get()
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row,amount=999)):
            self.assertEqual(reconcile(row,self.merchant).state,"review")
        PlatformSubscriptionPayment.objects.create(subscription=self.sub,reference="cash",amount_xaf=10000,method="especes")
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row)):
            self.assertEqual(reconcile(row,self.merchant).state,"review")
        self.assertEqual(PlatformSubscriptionPayment.objects.count(),1)
    def test_foreign_user_and_platform_gate(self):
        self.client.force_login(self.other);r,p=self.start();self.assertEqual(r.status_code,403);p.assert_not_called()
        self.client.force_login(self.owner)
        with override_settings(YEM_PAYMENTS_LIVE_ENABLED=False):
            r,p=self.start();self.assertEqual(r.status_code,409);p.assert_not_called()
        self.assertEqual(self.client.get("/api/v1/platform/singpay/merchant").status_code,403)
    def test_refund_evidence_preserves_credit(self):
        self.start();row=Intent.objects.get()
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row)):
            row=reconcile(row,self.merchant)
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row,result="Refund")):
            row=reconcile(row,self.merchant)
        self.assertEqual(row.state,"refund_review");self.assertEqual(PlatformSubscriptionPayment.objects.count(),1)
    def test_platform_merchant_requires_mfa_approval_and_wallet_validation(self):
        admin=get_user_model().objects.create_superuser(username="admin",email="admin@example.test",password="test-only-password")
        self.client.force_login(admin)
        body={"revision":1,"wallet_id":"platform-wallet","disbursement_id":"platform-distribution","client_id":"fake","client_secret":"fake-secret","beneficiary_name":"BWETEK","contract_reference":"contract","mode":"live","enabled":True,"fee_basis_points":0,"fee_fixed_xaf":0}
        path="/api/v1/platform/singpay/merchant"
        self.assertEqual(self.client.post(path,json.dumps(body),content_type="application/json").status_code,403)
        session=self.client.session;session["mfa_verified"]=True;session.save()
        with patch("institutions.commercial_singpay_views.verify_wallet_access") as verify:
            self.assertEqual(self.client.post(path,json.dumps(body),content_type="application/json").status_code,409)
            verify.assert_not_called()
        with override_settings(YEM_SINGPAY_APPROVED_DESTINATIONS="platform:platform-wallet:platform-distribution:live"),patch("institutions.commercial_singpay_views.verify_wallet_access") as verify:
            r=self.client.post(path,json.dumps(body),content_type="application/json")
            self.assertEqual(r.status_code,200,r.content);verify.assert_called_once()
            self.assertNotIn("fake-secret",r.content.decode())
    def test_manual_console_cannot_void_provider_receipt(self):
        self.start();row=Intent.objects.get()
        with patch("institutions.commercial_singpay.provider_request",return_value=self.evidence(row)):
            row=reconcile(row,self.merchant)
        admin=get_user_model().objects.create_superuser(username="admin",email="admin@example.test",password="test-only-password")
        self.client.force_login(admin);session=self.client.session;session["mfa_verified"]=True;session.save()
        r=self.client.post(f"/api/v1/platform/schools/{self.school.pk}/subscriptions",json.dumps({"year_id":str(self.sub.year_id),"action":"void","payment_id":row.payment_id,"reason":"Test interdiction"}),content_type="application/json")
        self.assertEqual(r.status_code,409,r.content)
        self.assertIsNone(PlatformSubscriptionPayment.objects.get().voided_at)
    def test_restricted_school_can_pay_contract_without_unrestricting_school(self):
        from .subscription_models import PlatformCommercialAccessDecision
        decision=PlatformCommercialAccessDecision.objects.create(school=self.school,revision=1,restricted=True,reason="Contrat impayé")
        r,p=self.start();self.assertEqual(r.status_code,201,r.content);p.assert_called_once()
        decision.refresh_from_db();self.assertTrue(decision.restricted)
        r=self.client.post(f"/api/v1/schools/{self.school.pk}/owner/subscriptions/{self.sub.pk}/singpay/invalid/refresh", "{}",content_type="application/json")
        self.assertEqual(r.status_code,403)

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, connections
from django.test import TransactionTestCase, Client

@skipUnless(connection.vendor == "postgresql", "PostgreSQL row-lock concurrency runs in CI")
@override_settings(YEM_SINGPAY_ENABLED=True,YEM_PAYMENTS_LIVE_ENABLED=True,
 YEM_PAYMENT_ENCRYPTION_KEY="test-encryption-key-abcdefghijklmnopqrstuvwxyz",AUTH_PUBLIC_BASE_URL="https://yem.example.test")
class CommercialSingPayConcurrencyTests(TransactionTestCase):
    def setUp(self):
        CommercialSingPayTests.setUp(self)
    def test_two_requests_issue_one_debit_and_one_credit(self):
        cookies=self.client.cookies.copy()
        gate=Barrier(2)
        def send(_):
            connections.close_all()
            client=Client();client.cookies=cookies.copy()
            try:
                gate.wait(timeout=10)
                return client.post(self.path,json.dumps(self.body),content_type="application/json").status_code
            finally:
                connections.close_all()
        with patch("institutions.commercial_singpay.provider_request",return_value={}) as provider:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results=list(executor.map(send,range(2)))
        self.assertEqual(sorted(results),[200,201]);self.assertEqual(provider.call_count,1)
        self.assertEqual(Intent.objects.count(),1)
        row=Intent.objects.get()
        proof=CommercialSingPayTests.evidence(self,row)
        gate=Barrier(2)
        def confirm(_):
            connections.close_all()
            try:
                gate.wait(timeout=10)
                return reconcile(Intent.objects.get(pk=row.pk),PlatformSingPayMerchant.objects.get()).state
            finally:
                connections.close_all()
        with patch("institutions.commercial_singpay.provider_request",return_value=proof):
            with ThreadPoolExecutor(max_workers=2) as executor:
                self.assertEqual(list(executor.map(confirm,range(2))),["success","success"])
        self.assertEqual(PlatformSubscriptionPayment.objects.count(),1)
