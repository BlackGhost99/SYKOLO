"""Payment-before-enrollment and independently verified government scholarships.

Checks real Django endpoints with distinct cashier/secretary/director/parent
sessions. An award is never a cash receipt or a fictitious payment.
"""
import json
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
