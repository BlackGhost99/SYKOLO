"""Full family->school->gateway journey without sending real money.

Tests use a fake provider response plus signed PayCentral-shaped webhooks.
No school memberships or verified guardian links are minted by a payment.
"""
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .admission_models import AdmissionApplication
from .finance_models import FeePayment
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_admission_models import ParentAdmissionRequest, SchoolPublicListing
from .parent_models import GuardianAccountLink
from .parent_payment_models import SchoolAdmissionFee, SchoolPaymentGateway, ParentPaymentAttempt
from .parent_payment_service import encrypt_secret
from .services import ROLE_TEMPLATES
from .student_models import Enrollment

MOCK_TXN = "01a1918d-9c00-723d-8d39-3194bfddc9e2"
SECRET = "whsec_test_school_payment_hmac"
KEY = "sk_sandbox_school_merchant_fake"
PHONE = "+24107123333"


@override_settings(
    YEM_PAYMENT_ENCRYPTION_KEY="sandbox-test-only-YEM-encryption-key-abcdefghijklmnopqrstuvwxyz",
    YEM_PAYMENTS_LIVE_ENABLED=False,
    AUTH_PUBLIC_BASE_URL="https://yem.example.test",
)
class ParentPaymentTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.director=User.objects.create_user(username="parent-fees-director",password="Safe test 2026 director!")
        self.parent=User.objects.create_user(username="parent-fees-guardian",password="Safe test 2026 guardian!")
        self.other=User.objects.create_user(username="parent-fees-other",password="Safe test 2026 outsider!")
        org=Organization.objects.create(name="Groupe test frais YEM")
        self.school=School.objects.create(organization=org,name="École test frais",
            school_type="primaire",education_cycles=["primaire"])
        self.foreign=School.objects.create(organization=org,name="Autre école")
        for school in (self.school,self.foreign):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=permissions)
        SchoolMember.objects.create(school=self.school,user=self.director,
            role=SchoolRole.objects.get(school=self.school,code="direction"))
        SchoolMember.objects.get(school=self.school,user=self.director).additional_roles.add(SchoolRole.objects.get(school=self.school,code="tarification"))
        self.year=AcademicYear.objects.create(school=self.school,code="2026",name="2026/2027",
            start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="primaire",name="Primaire")
        self.level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="ce1",name="CE1")
        self.classroom=AcademicClass.objects.create(school=self.school,year=self.year,level=self.level,
            code="ce1a",name="CE1 A",capacity=12)
        SchoolPublicListing.objects.create(school=self.school,published=True,city="Libreville")
        self.fee=SchoolAdmissionFee.objects.create(school=self.school,year=self.year,level=self.level,
            amount_xaf=2500)
        self.gateway=SchoolPaymentGateway.objects.create(
            school=self.school,mode="sandbox",enabled=True,
            encrypted_api_key=encrypt_secret(KEY),encrypted_webhook_secret=encrypt_secret(SECRET),
        )
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.parent)

    def login(self,user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,data):
        return self.client.post("/api/v1/"+path, data=json.dumps(data),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def apply(self,choice="online"):
        child=self.post("parents/family-children",{
            "first_name":"Maya","last_name":"Ogooué","date_of_birth":"2018-03-17",
        })
        self.assertEqual(child.status_code,201,child.content)
        response=self.post("parents/applications",{
            "child":child.json()["id"],"classroom":str(self.classroom.pk),
            "route":"direct","payment_choice":choice,
            "guardian_relationship":"Mère","guardian_phone":PHONE,
            "origin_school":"","route_reference":"",
        })
        self.assertEqual(response.status_code,201,response.content)
        return response.json()["id"]

    def pay(self,application_id,**body):
        return self.post("parents/applications/"+application_id+"/pay",{
            "channel":body.get("channel","airtel"),"phone":body.get("phone",PHONE),
        })

    def fake_provider_response(self):
        return {"success":True,"data":{"transaction_id":MOCK_TXN,"status":"processing",
            "provider":"airtel","amount":2500,"currency":"XAF"}}

    def webhook(self,attempt,secret=SECRET,amount="2500.00",status="success",signed=True,reference=None,webhook_txn_id=MOCK_TXN):
        payload={"event":"payment."+status,"timestamp":"2026-11-04T08:00:00Z","data":{
            "id":webhook_txn_id,"provider":"airtel","amount":amount,
            "currency":"XAF","status":status,
            "merchant_reference":reference or attempt.merchant_reference,
            "provider_reference":"provider-ref-test",
        }}
        raw=json.dumps(payload,separators=(",",":")).encode()
        signature="sha256="+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest() if signed else "bad"
        return self.client.post("/api/v1/parents/paycentral/webhook",data=raw,
            content_type="application/json",HTTP_X_PAYCENTRAL_SIGNATURE=signature)

    def test_school_fees_and_gateway_keys_never_leak(self):
        self.login(self.director)
        url=f"schools/{self.school.pk}/admission-gateway"
        get=self.client.get("/api/v1/"+url)
        self.assertEqual(get.status_code,200)
        self.assertNotIn(KEY,get.content.decode())
        self.assertNotIn(SECRET,get.content.decode())
        self.assertEqual(get.json()["mode"],"sandbox")
        self.assertTrue(get.json()["active"])
        self.assertEqual(self.post(url,{"revision":1,"mode":"live","enabled":True,
                                        "api_key":"","webhook_secret":""}).status_code,409)
        self.login(self.other)
        self.assertEqual(self.client.get("/api/v1/"+url).status_code,404)

    def test_public_catalog_and_fee_snapshot(self):
        catalog=self.client.get("/api/v1/parents/catalog")
        self.assertEqual(catalog.status_code,200)
        room=catalog.json()["schools"][0]["classes"][0]
        self.assertEqual(room["fee_amount_xaf"],2500)
        self.assertTrue(room["online_payment_available"])
        application_id=self.apply()
        link=ParentAdmissionRequest.objects.get(pk=application_id)
        self.assertEqual(link.fee_amount_xaf,2500)
        self.fee.amount_xaf=5000
        self.fee.save()
        link.refresh_from_db()
        self.assertEqual(link.fee_amount_xaf,2500)
        self.assertEqual(AdmissionApplication.objects.count(),1)
        self.assertEqual(Enrollment.objects.count(),0)
        self.assertEqual(GuardianAccountLink.objects.count(),0)

    def test_payment_idempotence_and_hmac_with_amount_check(self):
        app_id=self.apply()
        with patch("institutions.parent_payment_views.paycentral_request",return_value=self.fake_provider_response()) as fake:
            response=self.pay(app_id)
            self.assertEqual(response.status_code,201,response.content)
            same=self.pay(app_id)
            self.assertEqual(same.status_code,200,same.content)
            self.assertEqual(response.json()["merchant_reference"],same.json()["merchant_reference"])
            self.assertEqual(fake.call_count,1)
        attempt=ParentPaymentAttempt.objects.get(request_id=app_id)
        self.assertEqual(attempt.state,"pending")
        self.assertEqual(self.webhook(attempt,signed=False).status_code,401)
        self.assertEqual(self.webhook(attempt,amount="50000.00").status_code,409)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state,"pending")
        # The signed webhook may expose a UUID, while initiation returned
        # another provider transaction identifier (per published API examples).
        response=self.webhook(attempt,webhook_txn_id="01a1918d-9bc8-7383-b422-79d779e1c1ea")
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(ParentPaymentAttempt.objects.get(pk=attempt.pk).transaction_id,MOCK_TXN)
        self.assertEqual(self.webhook(attempt).status_code,200)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state,"success")
        self.assertEqual(attempt.provider_mode,"sandbox")
        self.assertFalse(self.client.get("/api/v1/parents/applications/"+app_id+"/payments")
                         .json()["payments"][0]["paid_confirmed"])
        self.assertEqual(ParentPaymentAttempt.objects.count(),1)
        self.assertEqual(FeePayment.objects.count(),0)
        self.assertEqual(Enrollment.objects.count(),0)

    def test_signed_webhook_before_initiation_response_keeps_canonical_id_empty(self):
        # A signed event can beat the initiation response. PayCentral's
        # webhook data.id may be a UUID rather than the initiation ULID.
        import uuid
        app_id = self.apply()
        attempt = ParentPaymentAttempt.objects.create(
            request_id=app_id, school=self.school, payer=self.parent,
            amount_xaf=2500, channel="airtel", payer_phone=PHONE,
            provider_mode="sandbox", merchant_reference="YEM-" + uuid.uuid4().hex,
        )
        result = self.webhook(
            attempt, webhook_txn_id="01a1918d-9bc8-7383-b422-79d779e1c1ea",
        )
        self.assertEqual(result.status_code, 200, result.content)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state, "success")
        self.assertIsNone(attempt.transaction_id)
        # Later, the initiation response can safely establish the real ID.
        attempt.transaction_id = MOCK_TXN
        attempt.save(update_fields=["transaction_id"])
        attempt.refresh_from_db()
        self.assertEqual(attempt.transaction_id, MOCK_TXN)

    def test_cross_tenant_and_cross_parent_are_forbidden(self):
        app_id=self.apply()
        self.login(self.other)
        self.assertEqual(self.pay(app_id).status_code,404)
        self.assertEqual(self.client.get("/api/v1/parents/applications/"+app_id+"/payments").status_code,404)
        self.assertEqual(self.client.get("/api/v1/parents/notifications").json()["notifications"],[])
        self.assertEqual(self.client.get("/api/v1/schools/"+str(self.school.pk)+"/admission-payments").status_code,404)
        self.login(self.director)
        self.assertEqual(self.client.get("/api/v1/schools/"+str(self.school.pk)+"/admission-payments").status_code,200)
        self.assertEqual(self.client.get("/api/v1/schools/"+str(self.foreign.pk)+"/admission-payments").status_code,404)

    def test_gateway_missing_disables_online_but_cash_still_works(self):
        self.gateway.enabled=False
        self.gateway.save()
        room=self.client.get("/api/v1/parents/catalog").json()["schools"][0]["classes"][0]
        self.assertFalse(room["online_payment_available"])
        child=self.post("parents/family-children",{
            "first_name":"Nina","last_name":"T","date_of_birth":None,
        }).json()["id"]
        body={"child":child,"classroom":str(self.classroom.pk),"route":"direct",
            "payment_choice":"online","guardian_relationship":"Père",
            "guardian_phone":PHONE,"origin_school":"","route_reference":""}
        self.assertEqual(self.post("parents/applications",body).status_code,409)
        body["payment_choice"]="cash"
        self.assertEqual(self.post("parents/applications",body).status_code,201)

    def test_authenticated_provider_status_refresh_is_not_client_claim(self):
        app_id=self.apply()
        with patch("institutions.parent_payment_views.paycentral_request",return_value=self.fake_provider_response()):
            self.assertEqual(self.pay(app_id).status_code,201)
        attempt=ParentPaymentAttempt.objects.get(request_id=app_id)
        data={"success":True,"transaction":{
            "id":MOCK_TXN,"merchant_reference":attempt.merchant_reference,
            "amount":"2500.00","currency":"XAF","provider":"airtel","status":"success",
        }}
        with patch("institutions.parent_payment_views.paycentral_request",return_value=data):
            checked=self.post("parents/applications/"+app_id+"/payment-refresh",{})
            self.assertEqual(checked.status_code,200,checked.content)
        attempt.refresh_from_db()
        self.assertEqual(attempt.state,"success")
        notice=self.client.get("/api/v1/parents/notifications").json()["notifications"]
        self.assertTrue(any(n["kind"]=="payment" for n in notice))

    def test_unsigned_webhook_cannot_settle_and_cash_has_no_payment_initiation(self):
        app_id=self.apply("cash")
        self.assertEqual(self.pay(app_id).status_code,409)
        self.assertEqual(ParentPaymentAttempt.objects.count(),0)
        self.assertEqual(FeePayment.objects.count(),0)

    def test_gateway_configuration_requires_explicit_secrets(self):
        self.login(self.director)
        self.gateway.delete()
        url=f"schools/{self.school.pk}/admission-gateway"
        payload={"revision":0,"mode":"sandbox","enabled":True,
                 "api_key":KEY,"webhook_secret":SECRET}
        created=self.post(url,payload)
        self.assertEqual(created.status_code,200,created.content)
        self.assertTrue(created.json()["has_keys"])
        row=SchoolPaymentGateway.objects.get(school=self.school)
        self.assertNotIn(KEY,row.encrypted_api_key)
        self.assertNotIn(SECRET,row.encrypted_webhook_secret)
        with override_settings(YEM_PAYMENT_ENCRYPTION_KEY=""):
            response=self.post(url,{"revision":1,"mode":"sandbox","enabled":True,
                                    "api_key":"","webhook_secret":""})
            self.assertEqual(response.status_code,503)
