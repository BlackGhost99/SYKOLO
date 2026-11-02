import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .staff_models import StaffRecord, StaffAssignment


class StaffAssignmentTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.director=User.objects.create_user(username="director06",password="Strong demo password 2026!")
        self.teacher=User.objects.create_user(username="teacher06",password="Strong demo password 2026!")
        self.founder=User.objects.create_user(username="founder06",password="Strong demo password 2026!")
        self.stranger=User.objects.create_user(username="stranger06",password="Strong demo password 2026!")
        org=Organization.objects.create(name="Groupement 06")
        OrganizationMember.objects.create(organization=org,user=self.founder,role="founder")
        self.school=School.objects.create(organization=org,name="Lycée 06")
        self.other=School.objects.create(organization=org,name="Autre lycée")
        for school in (self.school,self.other):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=permissions)
        for user,role in ((self.director,"direction"),(self.teacher,"enseignant")):
            SchoolMember.objects.create(school=self.school,user=user,role=SchoolRole.objects.get(school=self.school,code=role))
        year=AcademicYear.objects.create(school=self.school,code="2026-2027",name="2026-2027",start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="secondaire",name="Secondaire")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="seconde",name="Seconde")
        self.classroom=AcademicClass.objects.create(school=self.school,year=year,level=level,code="2a",name="Seconde A")
        self.year=year
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base="/api/v1/schools/"+str(self.school.id)+"/"

    def login(self,user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self,path,data,method="post"):
        return getattr(self.client,method)(self.base+path,json.dumps(data),content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def record(self):
        r=self.write("staff",{"staff_code":"EMP001","first_name":"Jules","last_name":"Mba","position":"Enseignant","username":"teacher06"})
        self.assertEqual(r.status_code,201,r.content.decode())
        return r.json()

    def test_create_linked_staff_assignment_and_personal_access(self):
        staff=self.record()
        a=self.write("staff-assignments",{"staff":staff["id"],"year":str(self.year.id),"classroom":str(self.classroom.id),"duty":"professeur_principal"})
        self.assertEqual(a.status_code,201,a.content.decode())
        self.assertEqual(self.client.get(self.base+"staff-assignments").json()["assignments"][0]["duty"],"professeur_principal")
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base+"staff").status_code,403)
        mine=self.client.get(self.base+"staff/me/assignments")
        self.assertEqual(mine.status_code,200)
        self.assertEqual(mine.json()["assignments"][0]["staff"],staff["id"])
        self.assertEqual(self.write("staff-assignments",{"staff":staff["id"],"year":str(self.year.id),"classroom":str(self.classroom.id)}).status_code,403)

    def test_conflict_archive_and_data_validation(self):
        staff=self.record()
        self.assertEqual(self.write("staff",{"staff_code":"EMP001","first_name":"Dup","last_name":"X","position":"Agent"}).status_code,422)
        updated=self.write("staff/"+staff["id"],{"revision":1,"position":"Surveillant"},method="patch")
        self.assertEqual(updated.status_code,200,updated.content.decode())
        self.assertEqual(self.write("staff/"+staff["id"],{"revision":1,"active":False},method="patch").status_code,409)
        archived=self.write("staff/"+staff["id"],{"revision":2,"active":False},method="patch")
        self.assertEqual(archived.status_code,200,archived.content.decode())
        self.assertEqual(self.write("staff-assignments",{"staff":staff["id"],"year":str(self.year.id),"classroom":str(self.classroom.id)}).status_code,422)
        self.assertEqual(self.write("staff/"+staff["id"],{"revision":3,"school":str(self.other.pk)},method="patch").status_code,422)
        self.assertEqual(self.write("staff",{},method="delete").status_code,405)

    def test_foreign_school_and_account_rejections(self):
        staff=self.record()
        self.assertEqual(self.write("staff",{"staff_code":"EMP003","first_name":"Myst","last_name":"U","position":"Enseignant","username":"stranger06"}).status_code,422)
        other_year=AcademicYear.objects.create(school=self.other,code="2026-2027",name="Autre",start_date="2026-09-01",end_date="2027-07-31")
        self.assertEqual(self.write("staff-assignments",{"staff":staff["id"],"year":str(other_year.id),"classroom":str(self.classroom.id)}).status_code,422)
        self.login(self.founder)
        self.assertEqual(self.client.get(self.base+"staff").status_code,403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+"staff").status_code,404)
        self.assertEqual(self.client.get(self.base+"staff/"+staff["id"]).status_code,404)
        self.login(self.teacher)
        self.assertEqual(self.client.get("/api/v1/schools/"+str(self.other.pk)+"/staff/me/assignments").status_code,404)

    def test_revocation_csrf_anonymous(self):
        staff=self.record()
        self.assertEqual(self.client.post(self.base+"staff",json.dumps({"staff_code":"A"}),content_type="application/json").status_code,403)
        SchoolMember.objects.filter(school=self.school,user=self.teacher).update(active=False)
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base+"staff/me/assignments").status_code,404)
        self.client.logout()
        self.assertEqual(self.client.get(self.base+"staff").status_code,401)
