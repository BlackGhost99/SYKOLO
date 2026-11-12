"""Payment-before-enrollment and independently verified government scholarships.

Checks real Django endpoints with distinct cashier/secretary/director/parent
sessions. An award is never a cash receipt or a fictitious payment.
"""
import json
import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .admission_models import AdmissionApplication
from .admission_finance import finance_policy, scholarship_for_enrollment
from .finance_models import FeeSchedule, FeeCharge, FeePayment
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_admission_models import FamilyChild, ParentAdmissionRequest
from .parent_payment_models import AdmissionCashReceipt
from .services import ROLE_TEMPLATES
from .student_models import Student, Enrollment
from .registration_views import apply_fees


class EnrollmentFinancialConditionsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school = School.objects.create(
            organization=Organization.objects.create(name="Groupe bourses TEST"),
            name="Lycée privé fictif", school_type="lycee_general",
            education_cycles=["lycee_general"],
        )
        for code,label,perms in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school,code=code,label=label,permissions=perms)
        self.users={}
        for code in ("direction","secretariat","econome","comptabilite","parent"):
            user=User.objects.create_user(
                username="admission-"+code,password="Tests-conditions-scolaires-2026!",
                email="admission-"+code+"@example.test",
            )
            SchoolMember.objects.create(school=self.school,user=user,
                role=SchoolRole.objects.get(school=self.school,code=code))
            self.users[code]=user
        self.year=AcademicYear.objects.create(
            school=self.school, code="2026", name="2026-2027",
            start_date="2026-09-01", end_date="2027-07-31", status="current",
        )
        cycle=AcademicCycle.objects.create(school=self.school,code="lycee_general",name="Lycée")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="seconde",name="Seconde")
        self.room=AcademicClass.objects.create(school=self.school,year=self.year,level=level,
            code="seconde-s",name="Seconde S",capacity=30)
        self.client=Client(enforce_csrf_checks=True)
        self.login("direction")
        self.root=f"/api/v1/schools/{self.school.pk}/"

    def login(self,role):
        self.client.force_login(self.users[role])
        self.token=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,data):
        return self.client.post("/api/v1/"+path,
            data=json.dumps(data),content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token)

    def make_app(self,index=1,with_parent=True,with_fee=True):
        app=AdmissionApplication.objects.create(
            school=self.school,year=self.year,classroom=self.room,
            first_name=f"TEST-{index}",last_name="BOURSE-YEM",
            guardian_name="Responsable TEST",guardian_relationship="Parent",
            guardian_phone="+24107123456",source="parent_mobile" if with_parent else "guichet",
            submitted_by=self.users["parent"],status="accepted",
        )
        link=None
        if with_parent:
            child=FamilyChild.objects.create(owner=self.users["parent"],
                first_name=app.first_name,last_name=app.last_name)
            link=ParentAdmissionRequest.objects.create(
                owner=self.users["parent"],child=child,application=app,
                payment_choice="cash",fee_amount_xaf=2500 if with_fee else None,
            )
        return app,link

    def convert(self,app):
        app.refresh_from_db()
        return self.post(f"schools/{self.school.pk}/admissions/{app.pk}/convert",{
            "revision":app.revision,"enrolled_on":"2026-11-10",
        })

    def award(self,app,coverage="all",revision=0,action="approve",reference="ETAT-BOURSE-2026-001"):
        return self.post(f"schools/{self.school.pk}/admissions/{app.pk}/scholarship",{
            "action":action,"coverage":coverage,"revision":revision,"reference":reference,
        })

    def test_no_cash_no_scholarship_no_matricule_then_cashier_confirms(self):
        app,link=self.make_app()
        self.login("secretariat")
        blocked=self.convert(app)
        self.assertEqual(blocked.status_code,409,blocked.content)
        self.assertIn("espèces",blocked.json()["error"])
        self.assertEqual(Student.objects.count(),0)
        self.assertEqual(Enrollment.objects.count(),0)
        self.login("direction")
        self.assertEqual(self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm",{
            "reference":"TEST-COURT","received_on":"2026-11-10",
            "received_cash":True,"acknowledge_demo":False,
        }).status_code,403)
        self.login("econome")
        response=self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm",{
            "reference":"REÇU-TEST-2026-01","received_on":"2026-11-10",
            "received_cash":True,"acknowledge_demo":False,
        })
        self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(AdmissionCashReceipt.objects.count(),1)
        self.login("secretariat")
        result=self.convert(app)
        self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(Enrollment.objects.count(),1)
        self.assertTrue(Student.objects.get().matricule_yem.startswith("YEM-"))
        self.assertEqual(self.convert(app).status_code,200)

    def test_no_tariff_is_blocking_and_direct_enrollment_cannot_bypass(self):
        app,link=self.make_app(with_fee=False)
        self.login("secretariat")
        no_fee=self.convert(app)
        self.assertEqual(no_fee.status_code,409,no_fee.content)
        self.assertIn("Configurez",no_fee.json()["error"])
        student=Student.objects.create(school=self.school,first_name="AUTRE",last_name="TEST")
        self.assertEqual(self.post(f"schools/{self.school.pk}/enrollments",{
            "student":str(student.pk),"year":str(self.year.pk),
            "classroom":str(self.room.pk),"enrolled_on":"2026-11-10",
        }).status_code,409)
        self.assertEqual(self.post(f"schools/{self.school.pk}/classes/{self.room.pk}/enroll",{
            "students":[str(student.pk)],"enrolled_on":"2026-11-10",
        }).status_code,422)
        self.assertFalse(Enrollment.objects.exists())

    def test_full_scholarship_waives_admission_and_future_tuition_without_fake_payment(self):
        app,link=self.make_app()
        self.login("parent")
        self.assertEqual(self.award(app).status_code,403)
        self.login("econome")
        self.assertEqual(self.award(app).status_code,403)
        self.login("secretariat")
        self.assertEqual(self.award(app).status_code,403)
        self.login("direction")
        self.assertEqual(self.award(app,reference="x").status_code,422)
        granted=self.award(app)
        self.assertEqual(granted.status_code,201,granted.content)
        self.assertEqual(granted.json()["scholarship"]["coverage"],"all")
        self.assertTrue(granted.json()["ready_for_enrollment"])
        self.assertEqual(AdmissionCashReceipt.objects.count(),0)
        self.assertEqual(FeePayment.objects.count(),0)
        self.login("secretariat")
        converted=self.convert(app)
        self.assertEqual(converted.status_code,201,converted.content)
        enrollment=Enrollment.objects.get()
        self.assertEqual(scholarship_for_enrollment(enrollment).coverage,"all")
        schedule=FeeSchedule.objects.create(
            school=self.school,year=self.year,scope_key="",code="scolarite",
            label="Scolarité",amount=Decimal("60000.00"),currency="XAF",
        )
        self.assertEqual(apply_fees(self.school,enrollment,self.users["secretariat"]),0)
        self.assertEqual(FeeCharge.objects.count(),0)
        charge=FeeCharge(school=self.school,enrollment=enrollment,schedule=schedule,
            label=schedule.label,amount=schedule.amount,currency="XAF")
        with self.assertRaises(ValidationError):
            charge.full_clean()
        self.login("direction")
        self.assertEqual(self.award(app,revision=1,action="revoke").status_code,409)

    def test_admission_only_scholarship_still_charges_normal_tuition(self):
        app,link=self.make_app(index=2)
        self.login("direction")
        self.assertEqual(self.award(app,coverage="admission").status_code,201)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code,201)
        schedule=FeeSchedule.objects.create(
            school=self.school,year=self.year,scope_key="",code="scolarite",
            label="Scolarité",amount=Decimal("30000.00"),currency="XAF",
        )
        self.assertEqual(apply_fees(self.school,Enrollment.objects.get(),self.users["secretariat"]),1)
        self.assertEqual(FeeCharge.objects.count(),1)
        self.assertEqual(FeeCharge.objects.get().amount,Decimal("30000.00"))

    def test_disable_scholarship_and_configure_payment_rule_by_year(self):
        self.assertTrue(finance_policy(self.school,self.year.pk,self.room.level_id)["require_payment"])
        path=f"schools/{self.school.pk}/admissions/finance-policy"
        saved=self.post(path,{
            "year":str(self.year.pk),"level":str(self.room.level_id),
            "require_payment":True,"allow_government_scholarship":False,"revision":0,
        })
        self.assertEqual(saved.status_code,200,saved.content)
        app,link=self.make_app(index=3)
        self.assertEqual(self.award(app).status_code,409)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code,409)
        self.login("direction")
        changed=self.post(path,{
            "year":str(self.year.pk),"level":str(self.room.level_id),
            "require_payment":False,"allow_government_scholarship":True,"revision":1,
        })
        self.assertEqual(changed.status_code,200,changed.content)
        self.assertEqual(self.post(path,{
            "year":str(self.year.pk),"level":str(self.room.level_id),
            "require_payment":False,"allow_government_scholarship":True,"revision":1,
        }).status_code,409)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code,201)
        self.assertEqual(AdmissionCashReceipt.objects.count(),0)

    def test_scholarship_rejected_after_real_cash_to_avoid_double_funding(self):
        app,link=self.make_app(index=4)
        self.login("econome")
        received=self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm",{
            "reference":"PAIEMENT-RECETTE-2026","received_on":"2026-11-10",
            "received_cash":True,"acknowledge_demo":False,
        })
        self.assertEqual(received.status_code,201,received.content)
        self.login("direction")
        result=self.award(app)
        self.assertEqual(result.status_code,409,result.content)
        self.assertIn("remboursement",result.json()["error"])

    def test_awarded_scholarship_blocks_later_cash_and_cashier_queue_explains_why(self):
        app, link = self.make_app(index=20)
        self.login("direction")
        approved = self.award(app)
        self.assertEqual(approved.status_code, 201, approved.content)
        self.login("econome")
        queue = self.client.get(f"/api/v1/schools/{self.school.pk}/admission-cash?application={app.pk}")
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertEqual(len(queue.json()["payments"]), 1)
        self.assertTrue(queue.json()["payments"][0]["scholarship_active"])
        self.assertFalse(queue.json()["payments"][0]["can_pay"])
        self.assertEqual(queue.json()["payments"][0]["payment_status"], "dispense_bourse")
        received = self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm", {
            "reference": "CAISSE-INTERDITE-2026",
            "received_on": "2026-11-10", "received_cash": True,
            "acknowledge_demo": False,
        })
        self.assertEqual(received.status_code, 409, received.content)
        self.assertIn("Bourse gouvernementale", received.json()["error"])
        self.assertFalse(AdmissionCashReceipt.objects.exists())
        self.assertFalse(FeePayment.objects.exists())

    def test_online_payment_providers_cannot_start_after_government_award(self):
        app, link = self.make_app(index=21)
        link.payment_choice = "online"
        link.save(update_fields=["payment_choice"])
        self.login("direction")
        self.assertEqual(self.award(app).status_code, 201)
        self.login("parent")
        paycentral = self.post(f"parents/applications/{link.pk}/pay", {
            "channel": "airtel", "phone": "+24107123456",
        })
        self.assertEqual(paycentral.status_code, 409, paycentral.content)
        self.assertIn("Bourse gouvernementale", paycentral.json()["error"])
        singpay = self.post(f"parents/singpay/admission/{link.pk}/pay", {
            "amount_xaf": 2500, "channel": "airtel",
            "phone": "071234567",
            "merchant_revision": 0,
            "idempotency_key": str(uuid.uuid4()),
        })
        self.assertEqual(singpay.status_code, 409, singpay.content)
        self.assertIn("Bourse gouvernementale", singpay.json()["error"])
        from .parent_payment_models import ParentPaymentAttempt
        from .singpay_models import SingPayIntent
        self.assertFalse(ParentPaymentAttempt.objects.exists())
        self.assertFalse(SingPayIntent.objects.exists())

    def test_cashier_may_receive_after_scholarship_revoked_before_enrollment(self):
        app, link = self.make_app(index=22)
        self.login("direction")
        self.assertEqual(self.award(app).status_code, 201)
        revoked = self.award(app, revision=1, action="revoke",
                            reference="REVOCATION-BOURSE-2026")
        self.assertEqual(revoked.status_code, 200, revoked.content)
        self.assertFalse(revoked.json()["ready_for_enrollment"])
        self.login("econome")
        receipt = self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm", {
            "reference": "CASH-APRES-REVOCATION-2026",
            "received_on": "2026-11-10", "received_cash": True,
            "acknowledge_demo": False,
        })
        self.assertEqual(receipt.status_code, 201, receipt.content)
        self.assertTrue(receipt.json()["received_confirmed"])
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)

    def test_cannot_record_cash_against_an_already_enrolled_scholarship(self):
        app, link = self.make_app(index=23)
        self.login("direction")
        self.assertEqual(self.award(app).status_code, 201)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)
        self.login("econome")
        receipt = self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm", {
            "reference": "PAIEMENT-APRES-INSCRIPTION-2026",
            "received_on": "2026-11-10", "received_cash": True,
            "acknowledge_demo": False,
        })
        self.assertEqual(receipt.status_code, 409, receipt.content)
        self.assertIn("déjà inscrite", receipt.json()["error"])
        self.assertFalse(AdmissionCashReceipt.objects.exists())


    def test_disabling_new_awards_preserves_existing_award_and_allows_later_revoke(self):
        app, link = self.make_app(index=24)
        self.login("direction")
        self.assertEqual(self.award(app).status_code, 201)
        config = self.post(f"schools/{self.school.pk}/admissions/finance-policy", {
            "year": str(self.year.pk), "level": str(self.room.level_id),
            "require_payment": True, "allow_government_scholarship": False,
            "revision": 0,
        })
        self.assertEqual(config.status_code, 200, config.content)
        self.assertTrue(finance_policy(self.school, self.year.pk, self.room.level_id)["require_payment"])
        self.assertFalse(finance_policy(self.school, self.year.pk, self.room.level_id)["allow_government_scholarship"])
        from .admission_finance import payment_blocker
        self.assertIsNone(payment_blocker(app), "Une bourse vérifiée n'est pas annulée par un réglage futur")

        another, _ = self.make_app(index=25)
        self.assertEqual(self.award(another).status_code, 409)
        revoked = self.award(app, revision=1, action="revoke",
                            reference="ETAT-REVOCATION-2026-001")
        self.assertEqual(revoked.status_code, 200, revoked.content)
        self.assertFalse(revoked.json()["ready_for_enrollment"])
        self.login("secretariat")
        denied = self.convert(app)
        self.assertEqual(denied.status_code, 409, denied.content)
        self.assertIn("espèces", denied.json()["error"])
        self.assertFalse(AdmissionCashReceipt.objects.exists())


    def test_partial_percentage_makes_cash_due_and_tuition_net_without_fake_payment(self):
        app, link = self.make_app(index=40)
        fee = FeeSchedule.objects.create(
            school=self.school, year=self.year, scope_key="", code="scolarite-40",
            label="Scolarité - 1", amount=Decimal("60000.00"), currency="XAF",
        )
        grant = self.post(f"schools/{self.school.pk}/admissions/{app.pk}/scholarship", {
            "action": "approve", "coverage": "all", "reference": "BOURSE-PARTIELLE-40",
            "revision": 0, "calculation": "percent", "percentage": 40,
            "fixed_amount_xaf": None,
        })
        self.assertEqual(grant.status_code, 201, grant.content)
        amounts = grant.json()["amounts"]
        self.assertEqual(amounts["admission_gross_xaf"], 2500)
        self.assertEqual(amounts["admission_scholarship_xaf"], 1000)
        self.assertEqual(amounts["admission_due_xaf"], 1500)
        self.assertEqual(amounts["tuition_scholarship_xaf"], 24000)
        self.assertEqual(amounts["tuition_due_xaf"], 36000)
        self.assertFalse(grant.json()["ready_for_enrollment"])
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 409)
        self.assertFalse(Enrollment.objects.exists())
        self.login("econome")
        queue = self.client.get(f"/api/v1/schools/{self.school.pk}/admission-cash?application={app.pk}")
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertEqual(queue.json()["payments"][0]["amount_xaf"], 1500)
        self.assertTrue(queue.json()["payments"][0]["can_pay"])
        paid = self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm", {
            "reference": "CAISSE-PARTIELLE-2026", "received_on": "2026-11-10",
            "received_cash": True, "acknowledge_demo": False,
        })
        self.assertEqual(paid.status_code, 201, paid.content)
        self.assertEqual(paid.json()["amount_xaf"], 1500)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)
        enrollment = Enrollment.objects.get()
        self.assertEqual(apply_fees(self.school, enrollment, self.users["secretariat"]), 0)
        charge = FeeCharge.objects.get()
        self.assertEqual(charge.amount, Decimal("60000.00"))
        self.assertEqual(charge.scholarship_discount, Decimal("24000.00"))
        charges = self.client.get(f"/api/v1/schools/{self.school.pk}/finance/charges?enrollment={enrollment.pk}")
        self.assertEqual(charges.status_code, 200)
        self.assertEqual(charges.json()["charges"][0]["balance"], "36000.00")

    def test_fixed_grant_allocates_admission_first_then_tuition(self):
        FeeSchedule.objects.create(
            school=self.school, year=self.year, scope_key="", code="scolarite-fixe",
            label="Scolarité fixe", amount=Decimal("60000.00"), currency="XAF",
        )
        app, link = self.make_app(index=41)
        response = self.post(f"schools/{self.school.pk}/admissions/{app.pk}/scholarship", {
            "action": "approve", "coverage": "all", "reference": "ETAT-5000-2026",
            "revision": 0, "calculation": "fixed", "percentage": 100,
            "fixed_amount_xaf": 5000,
        })
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["amounts"]["admission_due_xaf"], 0)
        self.assertEqual(response.json()["amounts"]["tuition_scholarship_xaf"], 2500)
        self.assertTrue(response.json()["ready_for_enrollment"])
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)
        enrollment = Enrollment.objects.get()
        self.assertEqual(apply_fees(self.school, enrollment, self.users["secretariat"]), 0)
        self.assertEqual(FeeCharge.objects.get().scholarship_discount, Decimal("2500.00"))

    def test_guichet_direct_receipt_flows_through_finances_without_parent_account(self):
        from .parent_payment_models import SchoolAdmissionFee
        SchoolAdmissionFee.objects.create(
            school=self.school, year=self.year, level=self.room.level,
            amount_xaf=2500, active=True,
        )
        app, parent_link = self.make_app(index=42, with_parent=False)
        self.assertIsNone(parent_link)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 409)
        self.login("econome")
        queue = self.client.get(f"/api/v1/schools/{self.school.pk}/admission-cash?application={app.pk}")
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertEqual(len(queue.json()["payments"]), 1)
        self.assertTrue(queue.json()["payments"][0]["direct_cash"])
        cash = self.post(f"schools/{self.school.pk}/admission-cash/{app.pk}/confirm", {
            "reference": "GUICHET-DIRECT-42", "received_on": "2026-11-10",
            "received_cash": True, "acknowledge_demo": False,
        })
        self.assertEqual(cash.status_code, 201, cash.content)
        receipt = AdmissionCashReceipt.objects.get()
        self.assertIsNone(receipt.request_id)
        self.assertEqual(receipt.application_id, app.pk)
        self.assertEqual(receipt.amount_xaf, 2500)
        pdf = self.client.get(f"/api/v1/schools/{self.school.pk}/admission-cash/{app.pk}/receipt")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.login("direction")
        self.assertEqual(self.award(app).status_code, 409)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_tuition_only_grant_still_requires_admission_fee(self):
        app, link = self.make_app(index=43)
        self.login("direction")
        grant = self.post(f"schools/{self.school.pk}/admissions/{app.pk}/scholarship", {
            "action": "approve", "coverage": "tuition",
            "reference": "ETAT-SCOLARITE-2026", "revision": 0,
        })
        self.assertEqual(grant.status_code, 201, grant.content)
        self.assertEqual(grant.json()["amounts"]["admission_due_xaf"], 2500)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 409)
        self.login("econome")
        self.assertEqual(self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm", {
            "reference": "CASH-TUITION-2026", "received_on": "2026-11-10",
            "received_cash": True, "acknowledge_demo": False,
        }).status_code, 201)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)
        enrollment = Enrollment.objects.get()
        FeeSchedule.objects.create(
            school=self.school, year=self.year, scope_key="", code="scolarite-totale",
            label="Scolarité", amount=Decimal("60000.00"), currency="XAF",
        )
        self.assertEqual(apply_fees(self.school, enrollment, self.users["secretariat"]), 0)
        self.assertFalse(FeeCharge.objects.exists())

    def test_partial_admission_fixed_grant_cannot_be_settled_without_remainder(self):
        app, link = self.make_app(index=44)
        resp = self.post(f"schools/{self.school.pk}/admissions/{app.pk}/scholarship", {
            "action": "approve", "coverage": "admission",
            "reference": "PARTIELLE-FIXE-2026", "revision": 0,
            "calculation": "fixed", "percentage": 100, "fixed_amount_xaf": 1000,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["amounts"]["admission_due_xaf"], 1500)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 409)
        self.login("econome")
        paid = self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm", {
            "reference": "CASH-FIXE-44", "received_on": "2026-11-10",
            "received_cash": True, "acknowledge_demo": False,
        })
        self.assertEqual(paid.status_code, 201, paid.content)
        self.assertEqual(paid.json()["amount_xaf"], 1500)
        self.login("secretariat")
        self.assertEqual(self.convert(app).status_code, 201)
