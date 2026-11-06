import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .staff_models import StaffRecord, StaffAssignment
from .curriculum_models import Subject, CourseOffering, CourseUnit, CourseInstructor


class CurriculumTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.director=U.objects.create_user(username="direct07",password="Passphrase for YEM module seven 2026!")
        self.teacher=U.objects.create_user(username="teacher07",password="Passphrase for YEM module seven 2026!")
        self.other_user=U.objects.create_user(username="outsider07",password="Passphrase for YEM module seven 2026!")
        org=Organization.objects.create(name="Organisation 07")
        self.school=School.objects.create(organization=org,name="École A")
        self.other=School.objects.create(organization=org,name="École B")
        for school in (self.school,self.other):
            for code,label,perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=perms)
        for user,role in [(self.director,"direction"),(self.teacher,"enseignant")]:
            SchoolMember.objects.create(school=self.school,user=user,role=SchoolRole.objects.get(school=self.school,code=role))
        self.year=AcademicYear.objects.create(school=self.school,code="2026-2027",name="2026-2027",start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="secondaire",name="Secondaire")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="6eme",name="6e")
        self.classroom=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="6a",name="6A")
        self.staff=StaffRecord.objects.create(school=self.school,staff_code="P001",first_name="M",last_name="T",position="enseignant",account=self.teacher)
        self.assignment=StaffAssignment.objects.create(school=self.school,staff=self.staff,year=self.year,classroom=self.classroom,duty="enseignant")
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base="/api/v1/schools/"+str(self.school.id)+"/"

    def login(self,user):
        self.client.force_login(user)
        self.token=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self,path,data,method="post"):
        return getattr(self.client,method)(self.base+path,json.dumps(data),content_type="application/json",HTTP_X_CSRFTOKEN=self.token)

    def subject(self):
        r=self.write("subjects",{"code":"mathematiques","name":"Mathématiques"})
        self.assertEqual(r.status_code,201,r.content.decode())
        return r.json()

    def course(self):
        subject=self.subject()
        r=self.write("courses",{"year":str(self.year.pk),"classroom":str(self.classroom.pk),"subject":subject["id"],"coefficient":"2.750"})
        self.assertEqual(r.status_code,201,r.content.decode())
        return r.json()

    def test_subject_course_units_and_editable_coefficients(self):
        c=self.course()
        self.assertEqual(c["coefficient"],"2.750")
        changed=self.write("courses/"+c["id"],{"revision":1,"coefficient":"3.125"},method="patch")
        self.assertEqual(changed.status_code,200)
        self.assertEqual(changed.json()["revision"],2)
        self.assertEqual(self.write("courses/"+c["id"],{"revision":1,"coefficient":"5"},method="patch").status_code,409)
        unit=self.write("courses/"+c["id"]+"/units",{"code":"nombres","title":"Les nombres","objectives":"Savoir compter"})
        self.assertEqual(unit.status_code,201,unit.content.decode())
        self.assertEqual(self.client.get(self.base+"courses/"+c["id"]+"/units").json()["units"][0]["title"],"Les nombres")
        self.assertEqual(self.write("courses/"+c["id"]+"/units",{"code":"nombres","title":"Doublon"}).status_code,422)
        self.assertEqual(CourseUnit.objects.count(),1)

    def test_instructor_can_change_only_own_course_units(self):
        c=self.course()
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base+"courses").status_code,200)
        self.assertEqual(self.write("courses/"+c["id"]+"/units",{"code":"chap1","title":"Chapitre 1"}).status_code,403)
        self.assertEqual(self.write("courses/"+c["id"],{"revision":1,"coefficient":"10"},method="patch").status_code,403)
        self.login(self.director)
        attached=self.write("courses/"+c["id"]+"/instructors",{"staff_assignment":str(self.assignment.pk)})
        self.assertEqual(attached.status_code,201,attached.content.decode())
        self.login(self.teacher)
        add=self.write("courses/"+c["id"]+"/units",{"code":"chap1","title":"Chapitre 1"})
        self.assertEqual(add.status_code,201,add.content.decode())
        update=self.write("courses/"+c["id"]+"/units/"+add.json()["id"],{"revision":1,"objectives":"Compétences"},method="patch")
        self.assertEqual(update.status_code,200,update.content.decode())
        self.assertEqual(self.write("subjects",{"code":"pirate","name":"Privé"}).status_code,403)

    def test_cross_school_and_invalid_links(self):
        c=self.course()
        other=Subject.objects.create(school=self.other,code="physique",name="Physique")
        self.assertEqual(self.write("courses",{"year":str(self.year.pk),"classroom":str(self.classroom.pk),"subject":str(other.pk)}).status_code,422)
        self.assertEqual(self.write("courses",{"year":str(self.year.pk),"classroom":str(self.classroom.pk),"subject":c["subject"]}).status_code,422)
        self.assertEqual(self.write("courses",{"year":str(self.year.pk),"classroom":str(self.classroom.pk),"subject":c["subject"],"coefficient":0}).status_code,422)
        self.assertEqual(self.write("courses/"+c["id"],{"revision":1,"classroom":str(self.other.pk)},method="patch").status_code,422)
        self.login(self.other_user)
        self.assertEqual(self.client.get(self.base+"courses").status_code,404)
        self.assertEqual(self.client.get(self.base+"courses/"+c["id"]).status_code,404)
        self.assertEqual(CourseOffering.objects.count(),1)

    def test_invalid_instructor_and_archive(self):
        c=self.course()
        wrong_year=AcademicYear.objects.create(school=self.other,code="2026-2027",name="Année autre",start_date="2026-09-01",end_date="2027-07-31")
        other_cycle=AcademicCycle.objects.create(school=self.other,code="primaire",name="Primaire")
        other_level=AcademicLevel.objects.create(school=self.other,cycle=other_cycle,code="ce1",name="CE1")
        other_class=AcademicClass.objects.create(school=self.other,year=wrong_year,level=other_level,code="ce1a",name="CE1A")
        other_staff=StaffRecord.objects.create(school=self.other,staff_code="P002",first_name="F",last_name="X",position="Enseignant")
        other_assignment=StaffAssignment.objects.create(school=self.other,staff=other_staff,year=wrong_year,classroom=other_class)
        self.assertEqual(self.write("courses/"+c["id"]+"/instructors",{"staff_assignment":str(other_assignment.pk)}).status_code,422)
        self.assertEqual(self.write("courses/"+c["id"],{"revision":1,"active":False},method="patch").status_code,200)
        self.assertFalse(CourseOffering.objects.get(pk=c["id"]).active)
        self.assertEqual(self.write("courses",{},method="delete").status_code,405)

    def test_generate_reuses_catalog_and_preserves_existing_coefficients(self):
        course = self.course()
        body = {"classroom": str(self.classroom.pk), "names": ["mathématiques", "Anglais", " anglais "]}
        first = self.write("courses/generate", body)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["created"], ["Anglais"])
        self.assertEqual(CourseOffering.objects.get(pk=course["id"]).coefficient, 2.75)
        self.assertEqual(self.write("courses/generate", body).status_code, 200)
        self.assertEqual(Subject.objects.filter(school=self.school).count(), 2)
        self.assertEqual(self.write("courses/generate", {**body, "names": ["Sciences", " "]}).status_code, 422)
        self.assertFalse(Subject.objects.filter(name="Sciences").exists())
        self.login(self.teacher)
        self.assertEqual(self.write("courses/generate", body).status_code, 403)

    def test_only_unused_curriculum_objects_can_be_deleted(self):
        course = self.course()
        subject_path = "subjects/" + course["subject"]
        course_path = "courses/" + course["id"]
        self.assertEqual(self.write(subject_path, {"revision": 1}, method="delete").status_code, 409)
        self.assertEqual(self.write(course_path, {"revision": 2}, method="delete").status_code, 409)
        self.assertEqual(self.write(course_path, {"revision": 1}, method="delete").status_code, 200)
        self.assertEqual(self.write(subject_path, {"revision": 1}, method="delete").status_code, 200)

        course = self.course()
        course_path = "courses/" + course["id"]
        self.assertEqual(self.write(course_path + "/units", {"code": "unite", "title": "Unité"}).status_code, 201)
        self.assertEqual(self.write(course_path, {"revision": 1}, method="delete").status_code, 409)
        self.assertTrue(CourseUnit.objects.filter(course_id=course["id"]).exists())
