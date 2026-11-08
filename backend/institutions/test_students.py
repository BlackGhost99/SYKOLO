import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .student_models import Student, StudentGuardian, Enrollment, EnrollmentEvent
from .services import ROLE_TEMPLATES


class StudentAdmissionsTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.director = U.objects.create_user(username="director-05", password="One password for YEM test 2026!")
        self.secretary = U.objects.create_user(username="secretary-05", password="One password for YEM test 2026!")
        self.teacher = U.objects.create_user(username="teacher-05", password="One password for YEM test 2026!")
        self.founder = U.objects.create_user(username="founder-05", password="One password for YEM test 2026!")
        self.stranger = U.objects.create_user(username="stranger-05", password="One password for YEM test 2026!")
        org = Organization.objects.create(name="Groupe scolaire test 05")
        OrganizationMember.objects.create(organization=org, user=self.founder, role="founder")
        self.school = School.objects.create(organization=org, name="École 1")
        self.other = School.objects.create(organization=org, name="École 2")
        for school in [self.school,self.other]:
            for code,label,perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=perms)
        for user,role in [(self.director,"direction"),(self.secretary,"secretariat"),(self.teacher,"enseignant")]:
            SchoolMember.objects.create(school=self.school,user=user,role=SchoolRole.objects.get(school=self.school,code=role))
        self.year=AcademicYear.objects.create(school=self.school,code="2026-2027",name="2026-27",start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="primaire",name="Primaire")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="ce2",name="CE2")
        self.classroom=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="ce2a",name="CE2 A",capacity=1)
        self.second_class=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="ce2b",name="CE2 B",capacity=30)
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base="/api/v1/schools/"+str(self.school.id)+"/"

    def login(self,user):
        self.client.force_login(user)
        self.token=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self,path,data,method="post"):
        return getattr(self.client,method)(self.base+path,json.dumps(data),content_type="application/json",HTTP_X_CSRFTOKEN=self.token)

    def add_student(self,code="EL001"):
        r=self.write("students",{"student_code":code,"first_name":"Mina","last_name":"Nkomo","date_of_birth":"2018-02-20"})
        self.assertEqual(r.status_code,201,r.content.decode())
        return r.json()

    def enroll(self,student,classroom=None):
        return self.write("enrollments",{
            "student":student["id"],"year":str(self.year.id),
            "classroom":str((classroom or self.classroom).id),"enrolled_on":"2026-10-01","status":"inscrit",
        })

    def test_private_student_and_guardians(self):
        s=self.add_student()
        self.assertNotIn("school",s)
        g=self.write(f"students/{s['id']}/guardians",{
            "full_name":"Mme Nkomo","relationship":"tutrice","email":"tutrice@example.test",
            "phone":"+241 01 02 03 04","is_primary":True,
        })
        self.assertEqual(g.status_code,201,g.content.decode())
        self.assertEqual(self.client.get(self.base+f"students/{s['id']}/guardians").json()["guardians"][0]["email"],"tutrice@example.test")
        changed=self.write(f"students/{s['id']}/guardians/{g.json()['id']}",{
            "revision":1,"phone":"+241 05 06 07 08",
        },method="patch")
        self.assertEqual(changed.status_code,200)
        self.assertEqual(changed.json()["revision"],2)
        self.assertEqual(self.write(f"students/{s['id']}",{"revision":1,"last_name":"Nkomo-2"},method="patch").status_code,200)
        self.assertEqual(self.write(f"students/{s['id']}",{"revision":1,"active":False},method="patch").status_code,409)
        self.assertEqual(StudentGuardian.objects.count(),1)

    def test_guardians_directory_uses_active_enrollments_and_school_permissions(self):
        first = self.add_student("EL001")
        second = self.add_student("EL002")
        self.assertEqual(self.enroll(first).status_code, 201)
        self.assertEqual(self.enroll(second, self.second_class).status_code, 201)
        for student, name in [(first, "Parent A"), (second, "Parent B")]:
            self.assertEqual(self.write(f"students/{student['id']}/guardians", {
                "full_name": name, "relationship": "Mère", "phone": "+241 01 02 03 04",
            }).status_code, 201)
        self.assertEqual(self.write(f"students/{first['id']}/guardians", {
            "full_name": "Ancien responsable", "active": False,
        }).status_code, 201)
        path = self.base + f"guardians-by-class?classroom={self.classroom.id}"
        families = self.client.get(path).json()["families"]
        self.assertEqual([family["student_id"] for family in families], [first["id"]])
        self.assertEqual([guardian["name"] for guardian in families[0]["guardians"]], ["Parent A"])
        self.assertEqual(self.client.get(self.base.replace(str(self.school.id), str(self.other.id)) +
                         f"guardians-by-class?classroom={self.classroom.id}").status_code, 404)
        self.login(self.secretary)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.login(self.founder)
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_capacity_and_transfer_history(self):
        a=self.add_student("EL001")
        b=self.add_student("EL002")
        one=self.enroll(a)
        self.assertEqual(one.status_code,201,one.content.decode())
        self.assertEqual(self.enroll(b).status_code,422)
        self.assertEqual(self.enroll(a).status_code,422)
        moved=self.write("enrollments/"+one.json()["id"],{
            "revision":1,"classroom":str(self.second_class.id),
        },method="patch")
        self.assertEqual(moved.status_code,200,moved.content.decode())
        self.assertEqual(self.enroll(b).status_code,201)
        self.assertEqual(self.client.get(self.base+"enrollments/"+one.json()["id"]+"/history").json()["history"][0]["new_class"],str(self.second_class.id))
        self.assertEqual(EnrollmentEvent.objects.filter(school=self.school).count(),3)
        self.assertEqual(Enrollment.objects.filter(school=self.school).count(),2)

    def test_isolation_roles_and_founder_not_director(self):
        s=self.add_student()
        self.login(self.secretary)
        self.assertEqual(self.client.get(self.base+"students").status_code,200)
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base+"students").status_code,403)
        self.assertEqual(self.write("students",{"student_code":"EL003","first_name":"T","last_name":"N"}).status_code,403)
        self.login(self.founder)
        self.assertEqual(self.client.get(self.base+"students").status_code,403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+"students").status_code,404)
        self.assertEqual(self.client.get(self.base+"students/"+s["id"]).status_code,404)
        self.login(self.director)
        self.assertEqual(self.client.get("/api/v1/schools/"+str(self.other.id)+"/students").status_code,404)

    def test_school_rule_previews_allocates_and_never_rewinds_existing_series(self):
        Student.objects.create(school=self.school, student_code="A/0500-G", first_name="Élève", last_name="Ancien")
        url = self.base + "student-numbering"
        body = {"enabled": True, "template": "A/{n}-G", "digits": 4, "start_number": 1, "revision": 0}
        preview = self.client.post(url, json.dumps(body), content_type="application/json", HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["largest_number"], "500")
        self.assertEqual(preview.json()["next_code"], "A/0501-G")
        self.assertFalse(self.client.get(url).json()["enabled"])

        def save(values):
            return self.client.put(url, json.dumps(values), content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

        result = save(body)
        self.assertEqual(result.status_code, 200, result.content)
        first = self.add_student()
        self.assertEqual(first["student_code"], "A/0501-G")
        self.assertNotEqual(first["student_code"], first["matricule_yem"])
        self.assertEqual(save(body).status_code, 409)
        result = save({**body, "revision": 1, "digits": 5})
        self.assertEqual(result.json()["next_code"], "A/00502-G")
        self.assertEqual(self.add_student()["student_code"], "A/00502-G")
        self.assertTrue(Student.objects.filter(school=self.school, student_code="A/0500-G").exists())

    def test_reject_foreign_relationships_and_duplicate(self):
        s=self.add_student()
        created = self.write("students",{"student_code":"EL001","first_name":"B","last_name":"N"})
        self.assertEqual(created.status_code, 201, created.content)
        self.assertNotEqual(created.json()["student_code"], "EL001")
        self.assertNotEqual(created.json()["matricule_yem"], s["matricule_yem"])
        self.assertEqual(self.write("enrollments",{"student":str(self.school.id),"year":str(self.year.id),"classroom":str(self.classroom.id),"enrolled_on":"2026-10-01"}).status_code,422)
        other_year=AcademicYear.objects.create(school=self.other,code="2026-2027",name="Other",start_date="2026-09-01",end_date="2027-07-31")
        self.assertEqual(self.write("enrollments",{"student":s["id"],"year":str(other_year.id),"classroom":str(self.classroom.id),"enrolled_on":"2026-10-01"}).status_code,422)

    def test_csrf_no_delete_and_anonymous(self):
        self.assertEqual(self.client.post(self.base+"students",json.dumps({"student_code":"X"}),content_type="application/json").status_code,403)
        self.assertEqual(self.write("students",{},method="delete").status_code,405)
        self.client.logout()
        self.assertEqual(self.client.get(self.base+"students").status_code,401)
