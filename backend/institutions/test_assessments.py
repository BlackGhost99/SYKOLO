import json
from copy import deepcopy
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from pedagogy.views import PRESETS

from .models import Organization, School, SchoolRole, SchoolMember, SchoolSetting
from .services import ROLE_TEMPLATES, key_for_scope
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass, AcademicPeriod
from .student_models import Student, Enrollment
from .staff_models import StaffRecord, StaffAssignment
from .curriculum_models import Subject, CourseOffering, CourseInstructor
from .assessment_models import Assessment, AssessmentGrade


def policy(name):
    return deepcopy(next(x["policy"] for x in PRESETS if x["id"]==name))


class AssessmentTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.director=U.objects.create_user(username="direct08",password="YEM Test Passphrase 2026 Great!")
        self.teacher=U.objects.create_user(username="teacher08",password="YEM Test Passphrase 2026 Great!")
        self.stranger=U.objects.create_user(username="stranger08",password="YEM Test Passphrase 2026 Great!")
        org=Organization.objects.create(name="Groupe scolaire 08")
        self.school=School.objects.create(organization=org,name="École principale")
        self.other=School.objects.create(organization=org,name="École externe")
        for school in (self.school,self.other):
            for code,label,perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=perms)
        for user,role in [(self.director,"direction"),(self.teacher,"enseignant")]:
            SchoolMember.objects.create(school=self.school,user=user,role=SchoolRole.objects.get(school=self.school,code=role))
        self.year=AcademicYear.objects.create(school=self.school,code="2026-2027",name="2026-27",start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="primaire",name="Primaire")
        self.level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="cm2",name="CM2")
        self.classroom=AcademicClass.objects.create(school=self.school,year=self.year,level=self.level,code="cm2a",name="CM2 A")
        self.another_class=AcademicClass.objects.create(school=self.school,year=self.year,level=self.level,code="cm2b",name="CM2 B")
        self.period=AcademicPeriod.objects.create(school=self.school,year=self.year,code="t1",name="Période libre",start_date="2026-09-01",end_date="2026-12-31")
        subject=Subject.objects.create(school=self.school,code="maths",name="Mathématiques")
        self.course=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.classroom,subject=subject,coefficient="2.000")
        self.other_course=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.another_class,subject=subject)
        student=Student.objects.create(school=self.school,student_code="EL-001",first_name="Lina",last_name="Mba")
        another=Student.objects.create(school=self.school,student_code="EL-002",first_name="Lina",last_name="Kou")
        self.enrollment=Enrollment.objects.create(school=self.school,student=student,year=self.year,classroom=self.classroom,enrolled_on="2026-09-15")
        self.foreign_class_enrollment=Enrollment.objects.create(school=self.school,student=another,year=self.year,classroom=self.another_class,enrolled_on="2026-09-15")
        member=StaffRecord.objects.create(school=self.school,staff_code="P-001",first_name="Paul",last_name="T",position="enseignant",account=self.teacher)
        assignment=StaffAssignment.objects.create(school=self.school,staff=member,year=self.year,classroom=self.classroom)
        CourseInstructor.objects.create(school=self.school,course=self.course,staff_assignment=assignment)
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base="/api/v1/schools/"+str(self.school.pk)+"/"

    def login(self,user):
        self.client.force_login(user)
        self.token=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self,path,data,method="post"):
        return getattr(self.client,method)(self.base+path,json.dumps(data),content_type="application/json",HTTP_X_CSRFTOKEN=self.token)

    def configure(self,grade_policy):
        SchoolSetting.objects.update_or_create(school=self.school,scope_key=key_for_scope({}),defaults={"scope":{},"values":{"grading":grade_policy}})

    def add_assessment(self,course=None):
        c=course or self.course
        return self.write("courses/"+str(c.pk)+"/assessments",{
            "name":"Contrôle test","assessment_date":"2026-10-01",
            "kind":"devoir","weight":"2.5","period":str(self.period.pk),
        })

    def test_grade_calculation_and_immutable_snapshot(self):
        self.configure(policy("numeric-20"))
        self.login(self.teacher)
        created=self.add_assessment()
        self.assertEqual(created.status_code,201,created.content.decode())
        assessment=created.json()
        self.assertEqual(assessment["policy"]["scale"]["max"],20)
        self.assertEqual(assessment["weight"],"2.500")
        roster=self.client.get(self.base+"assessments/"+assessment["id"]+"/roster")
        self.assertEqual(roster.status_code,200)
        self.assertEqual(roster.json()["students"][0]["student_code"],"EL-001")
        self.assertEqual(len(roster.json()["students"]),1)
        added=self.write("assessments/"+assessment["id"]+"/grades",{
            "enrollment":str(self.enrollment.id),"score":18,"feedback":"Bien",
        })
        self.assertEqual(added.status_code,201,added.content.decode())
        self.assertEqual(added.json()["percent"],"90.000000")
        self.configure(policy("numeric-10"))
        self.assertEqual(self.client.get(self.base+"assessments/"+assessment["id"]).json()["policy"]["scale"]["max"],20)
        changed=self.write("assessments/"+assessment["id"]+"/grades/"+added.json()["id"],{
            "revision":1,"score":16,
        },method="patch")
        self.assertEqual(changed.status_code,200,changed.content.decode())
        self.assertEqual(changed.json()["percent"],"80.000000")
        self.assertEqual(self.write("assessments/"+assessment["id"]+"/grades/"+added.json()["id"],{
            "revision":1,"score":17,
        },method="patch").status_code,409)

    def test_letter_competency_and_missing_score(self):
        for name,score in [("letters","A"),("competency",None)]:
            self.configure(policy(name))
            created=self.add_assessment()
            self.assertEqual(created.status_code,201,created.content.decode())
            result=self.write("assessments/"+created.json()["id"]+"/grades",{
                "enrollment":str(self.enrollment.id),"score":score,
            })
            self.assertEqual(result.status_code,201,result.content.decode())
            self.assertIn(result.json()["status"],["empty","calculated"])
            self.assertNotEqual(result.json()["score"],{})
            if name=="letters":self.assertIsNotNone(result.json()["percent"])

    def test_no_policy_or_cross_class_grade_is_rejected(self):
        self.assertEqual(self.add_assessment().status_code,422)
        self.configure(policy("numeric-20"))
        assessment=self.add_assessment().json()
        self.assertEqual(self.write("assessments/"+assessment["id"]+"/grades",{
            "enrollment":str(self.foreign_class_enrollment.id),"score":12,
        }).status_code,422)
        self.assertEqual(self.write("assessments/"+assessment["id"]+"/grades",{
            "enrollment":str(self.enrollment.id),"score":21,
        }).status_code,422)
        self.assertEqual(self.write("assessments/"+assessment["id"]+"/grades",{
            "enrollment":str(self.enrollment.id),"score":True,
        }).status_code,422)
        self.assertEqual(self.write("courses/"+str(self.course.pk)+"/assessments",{
            "name":"Hors période","assessment_date":"2027-04-10","period":str(self.period.pk),
        }).status_code,422)
        self.assertEqual(AssessmentGrade.objects.count(),0)

    def test_teacher_only_their_course_and_school_isolation(self):
        self.configure(policy("numeric-20"))
        self.login(self.teacher)
        self.assertEqual(self.add_assessment(course=self.other_course).status_code,404)
        own=self.add_assessment()
        self.assertEqual(own.status_code,201,own.content.decode())
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+"assessments/"+own.json()["id"]).status_code,404)
        self.assertEqual(self.client.get(self.base+"assessments/"+own.json()["id"]+"/roster").status_code,404)
        self.assertEqual(self.client.get(self.base+"courses/"+str(self.course.pk)+"/assessments").status_code,404)
        self.login(self.director)
        self.assertEqual(self.client.get(self.base+"assessments/"+own.json()["id"]).status_code,200)
        self.assertEqual(self.write("assessments/"+own.json()["id"],{"revision":1,"policy_snapshot":policy("numeric-10")},method="patch").status_code,422)
        self.assertEqual(self.write("assessments/"+own.json()["id"],{"revision":1,"name":"Nouvelle appellation"},method="patch").status_code,200)
        self.assertEqual(self.write("assessments/"+own.json()["id"],{},method="delete").status_code,405)
