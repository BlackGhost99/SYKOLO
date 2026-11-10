"""Two end-to-end school application rehearsals, strictly using disposable test DB.

No paid provider, bank credentials, school fee ledger or production personal
information is involved. The guardrail is a per-school and per-parent allowlist.
"""
import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass, AcademicTrack
from .admission_models import AdmissionApplication, AdmissionPolicy
from .admission_policy import policy_key
from .finance_models import FeePayment
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_admission_models import ParentAdmissionRequest, SchoolPublicListing
from .parent_payment_models import ParentPaymentAttempt
from .services import ROLE_TEMPLATES, SECONDARY_ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment

@override_settings(PARENT_EMAIL_VERIFICATION_REQUIRED=False)
class DualPilotAdmissionTests(TestCase):
    def setUp(self):
        User=get_user_model()
        org=Organization.objects.create(name="YEM Recette fictive")
        self.school=School.objects.create(
            organization=org,name="Lycée Privé 2 (TEST)",
            school_type="lycee_general",education_cycles=["lycee_general"])
        for code,label,perms in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school,code=code,label=label,permissions=perms)
        # A test proviseur may approve, but does not accept or reverse payments.
        SchoolRole.objects.create(school=self.school,code="proviseur",label="Proviseur",
            permissions=SchoolRole.objects.get(school=self.school,code="direction").permissions)
        self.manager=User.objects.create_user(
            username="manager-test-pay",password="Mot-de-passe-fictif-long-2026!")
        member=SchoolMember.objects.create(school=self.school,user=self.manager,
            role=SchoolRole.objects.get(school=self.school,code="secretariat"))
        member.additional_roles.add(SchoolRole.objects.get(school=self.school,code="tarification"))
        self.secretary=User.objects.create_user(username="secretary-test-pay",password="Mot-de-passe-fictif-long-2026!")
        SchoolMember.objects.create(school=self.school,user=self.secretary,
            role=SchoolRole.objects.get(school=self.school,code="secretariat"))
        self.proviseur=User.objects.create_user(username="head-test-pay",password="Mot-de-passe-fictif-long-2026!")
        SchoolMember.objects.create(school=self.school,user=self.proviseur,
            role=SchoolRole.objects.get(school=self.school,code="proviseur"))
        self.year=AcademicYear.objects.create(school=self.school,code="2026-27",name="2026-2027",
            start_date="2026-09-01",end_date="2027-07-30",status="current")
        cycle=AcademicCycle.objects.create(school=self.school,code="lycee_general",name="Lycée général")
        self.pairs=[]
        for level_code, series, amount in (("seconde","S",2500),("terminale","C",3500)):
            level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code=level_code,name=level_code.title())
            track=AcademicTrack.objects.create(school=self.school,level=level,code=series.lower(),name=series)
            room=AcademicClass.objects.create(school=self.school,year=self.year,level=level,
                track=track,code=level_code+"-"+series.lower(),name=level_code.title()+" "+series,capacity=30)
            AdmissionPolicy.objects.create(school=self.school,year=self.year,level=level,
                scope_key=policy_key(self.year.id,level.id),
                enabled_routes=["direct"],required_documents={"direct":["birth_certificate","previous_reports"]})
            self.pairs.append((room,amount))
        SchoolPublicListing.objects.create(school=self.school,published=True,cash_at_school=True)
        self.client=Client(enforce_csrf_checks=True)

    def login(self,user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,data):
        return self.client.post("/api/v1/"+path,data=json.dumps(data),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def good(self,response,status):
        self.assertEqual(response.status_code,status,response.content)
        return response.json()

    def test_both_parents_are_enrolled_with_test_payment_only(self):
        parents=[]
        for name in ("yemtest-parent-s","yemtest-parent-c"):
            self.client.logout()
            self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
            status=self.good(self.client.get("/api/v1/auth/parents/registration-status"),200)
            self.assertFalse(status["email_verification_required"])
            self.good(self.post("auth/parents/register",{
                "username":name,"first_name":"Parent","last_name":"Fictif",
                "email":name+"@example.test","password":"Long-mot-de-passe-test-2026!",
            }),200)
            parents.append(get_user_model().objects.get(username=name))

        self.login(self.manager)
        amounts={f"{self.year.pk}:{r.level_id}":amount for r,amount in self.pairs}
        config=self.good(self.post(f"schools/{self.school.pk}/demo-admission-payments",{
            "revision":0,"enabled":True,"level_amounts_xaf":amounts,
            "allowed_usernames":[p.username for p in parents],
        }),200)
        self.assertEqual(config["level_amounts_xaf"],amounts)

        for idx,((room,amount),parent) in enumerate(zip(self.pairs,parents),1):
            self.client.logout()
            self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
            self.good(self.post("auth/login",{
                "username":parent.username,"password":"Long-mot-de-passe-test-2026!","scope":"parent",
            }),200)
            self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
            listed=self.good(self.client.get("/api/v1/parents/catalog"),200)
            school=next(s for s in listed["schools"] if s["id"]==str(self.school.pk))
            classroom=next(c for c in school["classes"] if c["id"]==str(room.pk))
            self.assertTrue(classroom["demo_payment_available"])
            self.assertEqual(classroom["demo_fee_amount_xaf"],amount)
            child=self.good(self.post("parents/family-children",{
                "first_name":f"TEST-{idx}","last_name":"ESSAI-YEM",
                "date_of_birth":"2010-01-02" if idx==1 else "2008-01-02",
            }),201)
            submission=self.good(self.post("parents/applications",{
                "child":child["id"],"classroom":str(room.pk),"route":"direct",
                "payment_choice":"demo","guardian_relationship":"Parent",
                "guardian_phone":"+24107123456","origin_school":"","route_reference":"",
            }),201)
            link=ParentAdmissionRequest.objects.get(pk=submission["id"])
            app=link.application
            self.assertEqual(app.status,"submitted")
            self.assertFalse(Enrollment.objects.filter(student__first_name=f"TEST-{idx}").exists())
            self.assertEqual(link.fee_amount_xaf,amount)
            payment=self.good(self.post(f"parents/applications/{link.pk}/demo-pay",{}),201)
            self.assertEqual(payment["provider_mode"],"sandbox")
            self.assertEqual(payment["state"],"success")
            self.assertFalse(payment["paid_confirmed"])
            self.assertIn("aucune somme reçue",payment["notice"])
            self.good(self.post(f"parents/applications/{link.pk}/demo-pay",{}),200)
            self.assertEqual(ParentPaymentAttempt.objects.filter(request=link).count(),1)
            self.assertEqual(FeePayment.objects.count(),0)

            self.login(self.secretary)
            base=f"schools/{self.school.pk}/admissions/{app.pk}"
            for code in app.required_documents:
                app.refresh_from_db()
                self.good(self.post(base+"/documents",{
                    "revision":app.revision,"code":code,
                    "reference":f"PIÈCE TEST papier {idx} {code}",
                }),201)
            self.assertEqual(self.post(base+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Ne peut pas s'auto-approuver",
            }).status_code,403)
            self.login(self.proviseur)
            app.refresh_from_db()
            self.assertEqual(self.post(base+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Preuves pas encore revues",
            }).status_code,409)
            for doc in app.documents.all():
                app.refresh_from_db()
                self.good(self.post(base+f"/documents/{doc.pk}/review",{
                    "revision":app.revision,"status":"verified","reason":"Vérification TEST",
                }),200)
            app.refresh_from_db()
            self.good(self.post(base+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Admis après vérification",
            }),200)
            self.login(self.secretary)
            app.refresh_from_db()
            result=self.good(self.post(base+"/convert",{
                "revision":app.revision,"enrolled_on":"2026-11-10",
            }),201)
            self.assertEqual(result["status"],"enrolled")
            pupil=Student.objects.get(school=self.school,first_name=f"TEST-{idx}")
            enrollment=Enrollment.objects.get(school=self.school,student=pupil)
            self.assertEqual(enrollment.classroom,room)
            self.assertTrue(pupil.matricule_yem.startswith("YEM-"))
            self.assertEqual(StudentGuardian.objects.filter(student=pupil).count(),1)
            self.assertEqual(FeePayment.objects.count(),0)
            self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/classes/{room.pk}/students").status_code,200)

            SchoolMember.objects.create(school=self.school,user=parent,
                role=SchoolRole.objects.get(school=self.school,code="parent"))
            self.login(self.proviseur)
            guardian=StudentGuardian.objects.get(student=pupil)
            self.good(self.post(f"schools/{self.school.pk}/parent-links",{
                "guardian":str(guardian.pk),"username":parent.username,
            }),201)
            self.login(parent)
            linked=self.good(self.client.get("/api/v1/parents/children"),200)
            self.assertTrue(any(p["student"]==str(pupil.pk) for p in linked["children"]))

        self.assertEqual(Enrollment.objects.filter(school=self.school).count(),2)
        self.assertEqual({e.classroom.name for e in Enrollment.objects.filter(school=self.school).select_related("classroom")},
                         {"Seconde S","Terminale C"})
        self.assertEqual(ParentPaymentAttempt.objects.filter(school=self.school).count(),2)
        self.assertEqual(FeePayment.objects.filter(school=self.school).count(),0)

    def test_non_authorized_parent_cannot_fake_pay(self):
        outsider=get_user_model().objects.create_user(username="nonpilot",password="Other-long-test-password-2026!")
        self.login(outsider)
        catalog=self.client.get("/api/v1/parents/catalog").json()
        school=next(s for s in catalog["schools"] if s["id"]==str(self.school.pk))
        self.assertFalse(any(c["demo_payment_available"] for c in school["classes"]))
