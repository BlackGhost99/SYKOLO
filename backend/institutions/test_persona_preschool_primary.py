"""Persona recipe: a parent enrolls two children into preschool and primary.

Only an ephemeral Django CI database is touched. The same real HTTP views and
role permissions are used as the live product. Names and records are fictional.
"""
import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .admission_models import AdmissionApplication, AdmissionPolicy
from .admission_policy import policy_key
from .attendance_models import AttendanceSession
from .models import Organization, School, SchoolMember, SchoolRole, SchoolSetting
from .parent_admission_models import SchoolPublicListing, ParentAdmissionRequest
from .parent_payment_models import SchoolAdmissionFee, AdmissionCashReceipt
from .services import ROLE_TEMPLATES, key_for_scope
from .staff_models import StaffRecord, StaffAssignment
from .student_models import Student, StudentGuardian, Enrollment


@override_settings(PARENT_EMAIL_VERIFICATION_REQUIRED=False)
class PreschoolPrimaryPersonaTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.school=School.objects.create(
            organization=Organization.objects.create(name="Groupe école fictif YEM"),
            name="Complexe scolaire Les 8 (test isolé)",
            school_type="groupe_scolaire", education_cycles=["prescolaire","primaire"],
        )
        for code, label, permissions in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school,code=code,label=label,permissions=permissions)
        self.personnel={}
        for role in ("direction","secretariat","econome","comptabilite","enseignant"):
            user=User.objects.create_user(username="persona-"+role,password="Mot-de-passe-persona-test-2026!")
            SchoolMember.objects.create(
                school=self.school,user=user,
                role=SchoolRole.objects.get(school=self.school,code=role),
            )
            self.personnel[role]=user
        self.year=AcademicYear.objects.create(
            school=self.school,code="2026-27",name="2026-2027",
            start_date="2026-09-01",end_date="2027-07-31",status="current",
        )
        self.rooms=[]
        for cycle_code,level_code,name,fee in (
            ("prescolaire","moyenne_section","Moyenne section",1500),
            ("primaire","ce1","CE1 A",2000),
        ):
            cycle=AcademicCycle.objects.create(school=self.school,code=cycle_code,name=cycle_code)
            level=AcademicLevel.objects.create(school=self.school,cycle=cycle,
                code=level_code,name=level_code.title())
            room=AcademicClass.objects.create(
                school=self.school,year=self.year,level=level,
                code=level_code+"-a",name=name,capacity=2,
            )
            AdmissionPolicy.objects.create(
                school=self.school,year=self.year,level=level,
                scope_key=policy_key(self.year.pk,level.pk),enabled_routes=["direct"],
                required_documents={"direct":["birth_certificate"] if cycle_code=="prescolaire"
                                    else ["birth_certificate","previous_reports"]},
            )
            SchoolAdmissionFee.objects.create(
                school=self.school,year=self.year,level=level,amount_xaf=fee,active=True,
            )
            self.rooms.append((room,fee))
        SchoolPublicListing.objects.create(school=self.school,published=True,cash_at_school=True)
        SchoolSetting.objects.create(
            school=self.school,scope_key=key_for_scope({}),scope={},
            values={"attendance":{"statuses":[
                {"code":"p","label":"Présent","group":"present"},
                {"code":"a","label":"Absent","group":"absent"},
            ]}},
        )
        self.client=Client(enforce_csrf_checks=True)
        self.csrf=""

    def login(self,user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,body):
        return self.client.post("/api/v1/"+path,json.dumps(body),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def ok(self,response,status):
        self.assertEqual(response.status_code,status,response.content)
        return response.json()

    def test_maternal_and_primary_children_across_parent_cash_direction_secretary_teacher(self):
        User=get_user_model()
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value
        self.ok(self.post("auth/parents/register",{
            "username":"persona-parent","first_name":"Parent","last_name":"EXEMPLE",
            "email":"persona-parent@example.test","password":"Mot-de-passe-familial-de-test-2026!",
        }),200)
        parent=User.objects.get(username="persona-parent")
        self.login(parent)
        catalog=self.ok(self.client.get("/api/v1/parents/catalog"),200)["schools"]
        listing=next(x for x in catalog if x["id"]==str(self.school.pk))
        self.assertEqual({x["name"] for x in listing["classes"]},
                         {"Moyenne section","CE1 A"})
        self.assertTrue(listing["cash_at_school"])
        submissions=[]
        for i,(room,amount) in enumerate(self.rooms,1):
            child=self.ok(self.post("parents/family-children",{
                "first_name":f"ENFANT-{i}","last_name":"FICTIF-LES8",
                "date_of_birth":"2022-05-12" if i==1 else "2018-05-12",
            }),201)
            result=self.ok(self.post("parents/applications",{
                "child":child["id"],"classroom":str(room.pk),
                "route":"direct","payment_choice":"cash",
                "guardian_relationship":"Père","guardian_phone":"+24107123456",
                "origin_school":"","route_reference":"",
            }),201)
            link=ParentAdmissionRequest.objects.get(pk=result["id"])
            self.assertEqual(link.fee_amount_xaf,amount)
            self.assertFalse(link.is_demo_cash)
            self.assertFalse(Enrollment.objects.filter(school=self.school,
                student__first_name=f"ENFANT-{i}").exists())
            # A second application for the same child/year must be rejected.
            self.assertEqual(self.post("parents/applications",{
                "child":child["id"],"classroom":str(room.pk),"route":"direct",
                "payment_choice":"cash","guardian_relationship":"Père",
                "guardian_phone":"+24107123456","origin_school":"",
                "route_reference":"",
            }).status_code,409)
            submissions.append(link)

        self.login(self.personnel["direction"])
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/admission-cash"
        ).status_code,200)
        # Direction decides; she cannot pretend she physically received cash.
        for link in submissions:
            self.assertEqual(self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm",{
                "reference":"INTERDIT","received_on":"2026-11-10",
                "received_cash":True,"acknowledge_demo":False,
            }).status_code,403)
        self.login(self.personnel["econome"])
        for i,link in enumerate(submissions,1):
            receipt=self.ok(self.post(f"schools/{self.school.pk}/admission-cash/{link.pk}/confirm",{
                "reference":f"RECETTE-TEST-{i}","received_on":"2026-11-10",
                "received_cash":True,"acknowledge_demo":False,
            }),201)
            self.assertTrue(receipt["received_confirmed"])
            self.assertFalse(receipt["is_demo"])
        self.assertEqual(AdmissionCashReceipt.objects.filter(school=self.school).count(),2)

        for i,link in enumerate(submissions,1):
            app=link.application
            root=f"schools/{self.school.pk}/admissions/{app.pk}"
            self.login(self.personnel["secretariat"])
            for code in app.required_documents:
                app.refresh_from_db()
                self.ok(self.post(root+"/documents",{
                    "revision":app.revision,"code":code,
                    "reference":"PIECE DE TEST "+code,
                }),201)
            self.assertEqual(self.post(root+"/decide",{
                "revision":app.revision,"status":"accepted","reason":"Non autorisé",
            }).status_code,403)
            self.login(self.personnel["direction"])
            for doc in app.documents.all():
                app.refresh_from_db()
                self.ok(self.post(root+f"/documents/{doc.pk}/review",{
                    "revision":app.revision,"status":"verified",
                    "reason":"Pièce fictive validée en recette",
                }),200)
            app.refresh_from_db()
            self.ok(self.post(root+"/decide",{
                "revision":app.revision,"status":"accepted",
                "reason":"Admission de l'enfant fictif",
            }),200)
            self.login(self.personnel["secretariat"])
            app.refresh_from_db()
            self.ok(self.post(root+"/convert",{
                "revision":app.revision,"enrolled_on":"2026-11-10",
            }),201)
            enrolled=Enrollment.objects.get(school=self.school,
                student__first_name=f"ENFANT-{i}")
            self.assertEqual(enrolled.classroom_id,self.rooms[i-1][0].pk)
            self.assertTrue(enrolled.student.matricule_yem.startswith("YEM-"))

        members=SchoolMember.objects.create(school=self.school,user=parent,
            role=SchoolRole.objects.get(school=self.school,code="parent"))
        self.login(self.personnel["direction"])
        for link in submissions:
            pupil=Student.objects.get(school=self.school,
                first_name=link.child.first_name)
            guardian=StudentGuardian.objects.get(school=self.school,student=pupil)
            self.ok(self.post(f"schools/{self.school.pk}/parent-links",{
                "guardian":str(guardian.pk),"username":parent.username,
            }),201)
        self.login(parent)
        visible=self.ok(self.client.get("/api/v1/parents/children"),200)["children"]
        self.assertEqual({child["student"] for child in visible},
            {str(e.student_id) for e in Enrollment.objects.filter(school=self.school)})

        # An educator sees ONLY assigned classes, not broad family records.
        educator=self.personnel["enseignant"]
        staff=StaffRecord.objects.create(school=self.school,
            staff_code="EDUCATEUR-FICTIF",first_name="TEST",last_name="EDUCATRICE",
            account=educator,position="enseignant")
        for room,fee in self.rooms:
            StaffAssignment.objects.create(school=self.school,staff=staff,
                year=self.year,classroom=room,duty="enseignant")
            self.login(educator)
            roster=self.ok(self.client.get(
                f"/api/v1/schools/{self.school.pk}/classes/{room.pk}/students"
            ),200)["students"]
            self.assertEqual(len(roster),1)
            self.assertEqual(self.client.get(
                f"/api/v1/schools/{self.school.pk}/students"
            ).status_code,403)
            session=self.ok(self.post(f"schools/{self.school.pk}/attendance/sessions",{
                "classroom":str(room.pk),"date":"2026-11-10","slot":"matin",
                "label":"Appel de la classe",
            }),201)
            enroll=Enrollment.objects.get(school=self.school,classroom=room)
            mark=self.ok(self.post(f"schools/{self.school.pk}/attendance/sessions/{session['id']}/marks",{
                "marks":[{"enrollment":str(enroll.pk),"status":"p","note":"",
                          "justification":"","justified":False,"revision":0,"reason":""}],
            }),200)
            self.login(self.personnel["direction"])
            self.ok(self.post(f"schools/{self.school.pk}/attendance/sessions/{session['id']}/close",{
                "revision":mark["session_revision"],
            }),200)
            self.login(parent)
            seen=self.ok(self.client.get(
                f"/api/v1/parents/children/{enroll.student_id}/attendance"
            ),200)["attendance"]
            self.assertEqual(len(seen),1)

        self.login(self.personnel["comptabilite"])
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/admission-cash"
        ).status_code,200)
        # Cashier confirmation cannot be done by a financial controller.
        self.assertEqual(self.post(
            f"schools/{self.school.pk}/admission-cash/{submissions[0].pk}/confirm",{
                "reference":"INTERDIT","received_on":"2026-11-10",
                "received_cash":True,"acknowledge_demo":False,
            }).status_code,403)
        self.assertEqual(Enrollment.objects.filter(school=self.school).count(),2)
