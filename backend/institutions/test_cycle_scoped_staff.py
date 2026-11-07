"""Non-régression du périmètre par cycle : isolation et refus par défaut."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .models import (
    Organization, OrganizationMember, School, SchoolAudit, SchoolLogin, SchoolMember, SchoolRole,
)
from .services import ROLE_TEMPLATES
from .student_models import Enrollment, Student
from .staff_models import StaffRecord


class CycleRestrictedStaffTests(TestCase):
    password = "Cycles-YEM-2026-Secure!43"

    def setUp(self):
        User = get_user_model()
        self.founder = User.objects.create_user("owner-cycles", password=self.password)
        self.org = Organization.objects.create(name="Complexe cycles")
        OrganizationMember.objects.create(organization=self.org,user=self.founder,role="founder")
        self.school = School.objects.create(
            organization=self.org, name="Complexe Maternelle et Primaire",
            school_type="groupe_scolaire", education_cycles=["prescolaire","primaire"],
        )
        self.other = School.objects.create(organization=self.org,name="École voisine",
            school_type="primaire",education_cycles=["primaire"])
        for school in (self.school,self.other):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=permissions)
        self.preschool=AcademicCycle.objects.create(school=self.school,code="prescolaire",name="Maternelle")
        self.primary=AcademicCycle.objects.create(school=self.school,code="primaire",name="Primaire")
        self.year=AcademicYear.objects.create(school=self.school,code="2026_2027",
            name="2026–2027",start_date=date(2026,9,1),end_date=date(2027,6,30))
        self.level_pre=AcademicLevel.objects.create(school=self.school,cycle=self.preschool,code="ps",name="Petite section")
        self.level_pri=AcademicLevel.objects.create(school=self.school,cycle=self.primary,code="cp",name="CP")
        self.class_pre=AcademicClass.objects.create(school=self.school,year=self.year,level=self.level_pre,
            code="psa",name="Petite section A")
        self.class_pri=AcademicClass.objects.create(school=self.school,year=self.year,level=self.level_pri,
            code="cpa",name="CP A")
        self.student_pre=Student.objects.create(school=self.school,student_code="PRE001",first_name="Enfant",last_name="Maternelle")
        self.student_pri=Student.objects.create(school=self.school,student_code="PRI001",first_name="Enfant",last_name="Primaire")
        for student, classroom in ((self.student_pre,self.class_pre),(self.student_pri,self.class_pri)):
            Enrollment.objects.create(school=self.school,student=student,year=self.year,
                classroom=classroom,enrolled_on=date(2026,9,10))
        self.manager=User.objects.create_user("manager-primary",password=self.password)
        self.member=SchoolMember.objects.create(
            school=self.school,user=self.manager,role=self.school.roles.get(code="direction"),
            access_cycle_ids=[str(self.primary.id)],
        )
        self.base=f"/api/v1/schools/{self.school.pk}/"
        self.client.force_login(self.manager)

    def send(self,method,path,data):
        return getattr(self.client,method)(self.base+path, data=json.dumps(data),
                content_type="application/json")

    def staff_payload(self,code="ENS001",target=None,appointments=None,classes=None):
        scope=[str(target or self.primary.id)]
        return {
            "staff":{"staff_code":code,"first_name":"Alice","last_name":"Essono","position":"Enseignante"},
            "account":{"username":"alice-"+code.lower(),"email":"alice@example.test",
                "password":self.password,"role":"enseignant","additional_roles":[],
                "access_cycle_ids":scope},
            "appointments":appointments if appointments is not None else [
                {"function_code":"directeur_primaire","cycle_code":"primaire"}],
            "class_assignments":classes if classes is not None else [],
            "ack_school_wide_permissions":True,
        }

    def test_scoped_reads_and_my_access(self):
        access=self.client.get(self.base+"my-access")
        self.assertEqual(access.status_code,200)
        self.assertTrue(access.json()["cycle_scope_restricted"])
        self.assertEqual(access.json()["access_cycle_ids"],[str(self.primary.id)])
        self.assertNotIn("school.finance.read",access.json()["permissions"])
        self.assertIn("school.students.read",access.json()["permissions"])
        data=self.client.get(self.base+"students")
        self.assertEqual(data.status_code,200,data.content)
        self.assertEqual([s["student_code"] for s in data.json()["students"]],["PRI001"])
        self.assertEqual(self.client.get(self.base+f"students/{self.student_pre.id}").status_code,404)
        self.assertEqual(self.client.get(self.base+f"students/{self.student_pri.id}").status_code,200)
        result=self.client.get(self.base+"enrollments")
        self.assertEqual(len(result.json()["enrollments"]),1)
        self.assertEqual(self.client.get(self.base+"academic/years").status_code,200)
        self.assertEqual([x["name"] for x in self.client.get(self.base+"academic/classes").json()["classes"]],["CP A"])
        self.assertEqual([x["name"] for x in self.client.get(self.base+"academic/cycles").json()["cycles"]],["Primaire"])
        self.assertEqual([x["name"] for x in self.client.get(self.base+"academic/levels").json()["levels"]],["CP"])
        self.assertEqual(self.client.get(self.base+f"academic/classes/{self.class_pre.id}").status_code,404)

    def test_matricule_search_respects_cycle_scope(self):
        hidden = self.client.get(self.base + "students", {"matricule": self.student_pre.matricule_yem})
        self.assertEqual(hidden.status_code, 200, hidden.content)
        self.assertEqual(hidden.json()["students"], [])

        visible = self.client.get(self.base + "students", {"matricule": self.student_pri.matricule_yem})
        self.assertEqual(visible.status_code, 200, visible.content)
        self.assertEqual([row["student_code"] for row in visible.json()["students"]], ["PRI001"])

    def test_closed_routes_cannot_leak_pupil_finance_or_grades(self):
        for route in (
            "overview/students", "finance/summary", "reports", "audit",
            "admissions","attendance/summary","staff", "organization/appointments",
            "roles", "subjects", "imports/students/export",
            f"students/{self.student_pre.id}/guardians",
            f"enrollments/{Enrollment.objects.get(student=self.student_pre).pk}/history",
        ):
            resp=self.client.get(self.base+route)
            if route.endswith("/guardians"):
                self.assertEqual(resp.status_code,404,route)
            else:
                self.assertEqual(resp.status_code,403,route)
        self.assertEqual(self.send("post","students",{
            "student_code":"LEAK","first_name":"Test","last_name":"Test"
        }).status_code,403)
        self.assertEqual(self.send("post","academic/classes",{
            "code":"new","name":"Interdit"
        }).status_code,403)

    def test_scoped_manager_can_create_staff_only_inside_allowed_cycle(self):
        options=self.client.get(self.base+"staff/onboard")
        self.assertEqual(options.status_code,200,options.content)
        self.assertEqual([x["name"] for x in options.json()["academic_cycles"]],["Primaire"])
        self.assertEqual([x["name"] for x in options.json()["classes"]],["CP A"])
        self.assertFalse(options.json()["can_manage_cycle_access"])
        good=self.send("post","staff/onboard",self.staff_payload())
        self.assertEqual(good.status_code,201,good.content)
        new=StaffRecord.objects.get(staff_code="ENS001",school=self.school)
        self.assertEqual(SchoolMember.objects.get(user=new.account,school=self.school).access_cycle_ids,[str(self.primary.id)])
        self.assertEqual(new.appointments.count(),1)
        self.assertFalse(StaffRecord.objects.filter(school=self.other).exists())

    def test_cross_cycle_or_global_grants_rejected_atomically(self):
        wrong=self.staff_payload(code="ENS002",target=self.preschool.id)
        self.assertEqual(self.send("post","staff/onboard",wrong).status_code,403)
        global_role=self.staff_payload(code="ENS003")
        global_role["account"]["access_cycle_ids"]=None
        self.assertEqual(self.send("post","staff/onboard",global_role).status_code,403)
        wrong_nom=self.staff_payload(code="ENS004",appointments=[
            {"function_code":"directeur_maternelle","cycle_code":"prescolaire"}
        ])
        self.assertEqual(self.send("post","staff/onboard",wrong_nom).status_code,403)
        wrong_class=self.staff_payload(code="ENS005",appointments=[],classes=[
            {"year":str(self.year.pk),"classroom":str(self.class_pre.pk),"duty":"enseignant"}
        ])
        self.assertEqual(self.send("post","staff/onboard",wrong_class).status_code,403)
        self.assertFalse(StaffRecord.objects.exists())
        self.assertFalse(SchoolLogin.objects.exists())

    def test_owner_can_change_scope_with_reason_and_revoke_immediately(self):
        self.client.force_login(self.founder)
        url=self.base+f"members/{self.member.id}/cycle-access"
        self.assertEqual(self.client.get(url).status_code,200)
        r=self.client.patch(url,data=json.dumps({"access_cycle_ids":[str(self.preschool.pk)],
            "reason":"Mutation vers maternelle"}),content_type="application/json")
        self.assertEqual(r.status_code,200,r.content)
        self.assertTrue(SchoolAudit.objects.filter(school=self.school,event="member_cycle_scope_changed").exists())
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.base+f"students/{self.student_pre.pk}").status_code,200)
        self.assertEqual(self.client.get(self.base+f"students/{self.student_pri.pk}").status_code,404)
        self.assertEqual(self.client.get(self.base+"finance/summary").status_code,403)

    def test_non_founder_cannot_modify_cycles(self):
        r=self.send("patch",f"members/{self.member.pk}/cycle-access",{
            "access_cycle_ids":None,"reason":"Autorisation globale refusée"
        })
        self.assertEqual(r.status_code,403)
        self.member.refresh_from_db()
        self.assertEqual(self.member.access_cycle_ids,[str(self.primary.id)])
