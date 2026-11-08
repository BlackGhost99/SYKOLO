import json
from copy import deepcopy
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from pedagogy.views import PRESETS
from .models import Organization, School, SchoolRole, SchoolMember, SchoolSetting
from .services import ROLE_TEMPLATES, key_for_scope
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass, AcademicPeriod
from .student_models import Student, Enrollment
from .curriculum_models import Subject, CourseOffering
from .assessment_models import Assessment, AssessmentGrade
from .report_models import SchoolReport


def preset(name):
    return deepcopy(next(p["policy"] for p in PRESETS if p["id"]==name))


class SchoolReportTests(TestCase):
    def setUp(self):
        User=get_user_model()
        self.director=User.objects.create_user(username="director09",password="YEM Test Strong Password For Reports!")
        self.secretary=User.objects.create_user(username="secretary09",password="YEM Test Strong Password For Reports!")
        self.stranger=User.objects.create_user(username="stranger09",password="YEM Test Strong Password For Reports!")
        org=Organization.objects.create(name="Établissements 09")
        self.school=School.objects.create(organization=org,name="École de Libreville")
        self.other=School.objects.create(organization=org,name="École étrangère")
        for school in (self.school,self.other):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=permissions)
        for user,role in [(self.director,"direction"),(self.secretary,"secretariat")]:
            SchoolMember.objects.create(school=self.school,user=user,role=SchoolRole.objects.get(school=self.school,code=role))
        self.year=AcademicYear.objects.create(school=self.school,code="2026-2027",name="2026–2027",start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="primaire",name="Primaire")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="cm2",name="CM2")
        self.classroom=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="cm2a",name="CM2 A")
        self.period=AcademicPeriod.objects.create(school=self.school,year=self.year,code="t1",name="Premier trimestre",start_date="2026-09-01",end_date="2026-12-31")
        student=Student.objects.create(school=self.school,student_code="BG-100",first_name="Lina",last_name="Nkomo")
        self.enrollment=Enrollment.objects.create(school=self.school,student=student,year=self.year,classroom=self.classroom,enrolled_on="2026-09-16")
        math=Subject.objects.create(school=self.school,code="maths",name="Mathématiques")
        french=Subject.objects.create(school=self.school,code="francais",name="Français")
        self.math=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.classroom,subject=math,coefficient=Decimal("2"))
        self.french=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.classroom,subject=french,coefficient=Decimal("1"))
        self.grading=preset("numeric-20")
        self.config={"title":"Bulletin YEM", "precision":2,"show_score":True,"show_label":True,"show_rank":False,"missing_entry":"exclude"}
        self.configure(self.grading)
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base="/api/v1/schools/"+str(self.school.pk)+"/"

    def configure(self,policy,config=None):
        SchoolSetting.objects.update_or_create(school=self.school,scope_key=key_for_scope({}),
            defaults={"scope":{},"values":{"grading":policy,"bulletin":config or self.config}})

    def login(self,user):
        self.client.force_login(user)
        self.token=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self,path,data,method="post"):
        return getattr(self.client,method)(self.base+path,json.dumps(data),content_type="application/json",HTTP_X_CSRFTOKEN=self.token)

    def assessment(self,course,percent=None,published=True):
        a=Assessment.objects.create(school=self.school,course=course,period=self.period,
            name="Contrôle",assessment_date="2026-10-20",weight=Decimal("1"),
            policy_snapshot=self.grading,policy_layers=[],published=published)
        if percent is not None:
            AssessmentGrade.objects.create(school=self.school,assessment=a,enrollment=self.enrollment,
                author=self.director,score=percent/5,percent=Decimal(str(percent)),label="Bien",status="calculated")
        return a

    def create_report(self,period=True,revision=0):
        return self.write("reports",{
            "enrollment":str(self.enrollment.pk),
            "period":str(self.period.pk) if period else None,
            "revision":revision,
        })

    def test_weighted_report_pdf_publication_and_immutable_snapshot(self):
        self.assessment(self.math,80)
        self.assessment(self.french,90)
        created=self.create_report()
        self.assertEqual(created.status_code,201,created.content.decode())
        report=created.json()
        snapshot=report["snapshot"]
        self.assertEqual(len(snapshot["subjects"]),2)
        self.assertEqual(snapshot["overall"]["percent"],"83.33")
        self.assertEqual(snapshot["overall"]["score"],"16.67")
        self.assertEqual(snapshot["template"]["title"],"Bulletin YEM")
        pdf=self.client.get(self.base+"reports/"+report["id"]+"/pdf")
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(pdf["Cache-Control"],"private, no-store")
        issued=self.write("reports/"+report["id"]+"/publish",{"revision":1})
        self.assertEqual(issued.status_code,200,issued.content.decode())
        self.assertEqual(issued.json()["status"],"published")
        self.assertEqual(self.create_report(revision=2).status_code,409)
        grade=AssessmentGrade.objects.first()
        grade.percent=Decimal("0");grade.save(update_fields=["percent"])
        immutable=self.client.get(self.base+"reports/"+report["id"]).json()["snapshot"]
        self.assertEqual(immutable["overall"]["percent"],"83.33")

    def test_bulletins_by_class_keep_published_reports_in_the_original_class(self):
        self.assessment(self.math, 80)
        report = self.create_report().json()
        self.assertEqual(self.write("reports/" + report["id"] + "/publish", {"revision": 1}).status_code, 200)
        next_room = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.classroom.level, code="cm2b", name="CM2 B",
        )
        self.enrollment.classroom = next_room
        self.enrollment.save(update_fields=["classroom"])
        current = self.client.get(self.base + f"reports?classroom={next_room.pk}").json()
        self.assertEqual(current["reports"], [])
        self.assertTrue(current["pupils"][0]["can_prepare"])
        self.login(self.secretary)
        original = self.client.get(self.base + f"reports?classroom={self.classroom.pk}").json()
        self.assertEqual([item["id"] for item in original["reports"]], [report["id"]])
        self.assertEqual(original["pupils"][0]["name"], "Nkomo Lina · BG-100")
        self.assertFalse(original["pupils"][0]["can_prepare"])
        self.assertEqual(self.client.get(self.base + f"reports?classroom={next_room.pk}").json()["pupils"], [])

    def test_only_published_assessments_and_locked_grades(self):
        a=self.assessment(self.math,80,published=False)
        self.assessment(self.french,90)
        report=self.create_report()
        self.assertEqual(report.status_code,201,report.content.decode())
        self.assertEqual(report.json()["snapshot"]["overall"]["percent"],"90.00")
        published=self.write("assessments/"+str(a.pk)+"/publish",{"revision":1})
        self.assertEqual(published.status_code,200,published.content.decode())
        self.assertEqual(self.write("assessments/"+str(a.pk)+"/publish",{"revision":2}).status_code,409)
        grade=AssessmentGrade.objects.get(assessment=a)
        self.assertEqual(self.write("assessments/"+str(a.pk)+"/grades/"+str(grade.pk),{
            "revision":1,"score":20,
        },method="patch").status_code,409)
        refreshed=self.create_report(revision=1)
        self.assertEqual(refreshed.status_code,200,refreshed.content.decode())
        self.assertEqual(refreshed.json()["snapshot"]["overall"]["percent"],"83.33")

    def test_empty_report_does_not_publish_even_with_zero_fill(self):
        cfg={**self.config,"missing_entry":"zero"}
        self.configure(self.grading,cfg)
        self.assessment(self.math,None)
        report=self.create_report()
        self.assertEqual(report.status_code,201,report.content.decode())
        self.assertEqual(report.json()["snapshot"]["overall"]["percent"],"0.00")
        self.assertEqual(report.json()["snapshot"]["recorded_grade_count"],0)
        self.assertEqual(self.write("reports/"+report.json()["id"]+"/publish",{"revision":1}).status_code,422)

    def test_letter_scale_custom_template_and_validation(self):
        self.configure(preset("letters"),{**self.config,"show_score":False})
        self.assessment(self.french,90)
        result=self.create_report(period=False)
        self.assertEqual(result.status_code,201,result.content.decode())
        self.assertIsNone(result.json()["snapshot"]["overall"]["score"])
        self.assertTrue(result.json()["snapshot"]["overall"]["label"])
        self.assertFalse(result.json()["snapshot"]["template"]["show_score"])
        self.configure(preset("letters"),{**self.config,"show_rank":True})
        other=self.create_report(period=True)
        self.assertEqual(other.status_code,422,other.content.decode())

    def test_scope_csrf_and_secretary_permissions(self):
        self.assessment(self.math,75)
        r=self.create_report().json()
        self.login(self.secretary)
        self.assertEqual(self.client.get(self.base+"reports/"+r["id"]).status_code,200)
        self.assertEqual(self.client.get(self.base+"reports/"+r["id"]+"/pdf").status_code,200)
        self.assertEqual(self.write("reports/"+r["id"]+"/publish",{"revision":1}).status_code,403)
        self.assertEqual(self.create_report().status_code,403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+"reports/"+r["id"]).status_code,404)
        self.assertEqual(self.client.get(self.base+"reports/"+r["id"]+"/pdf").status_code,404)
        self.login(self.director)
        self.assertEqual(self.client.post(self.base+"reports",json.dumps({"enrollment":str(self.enrollment.id),"revision":1}),content_type="application/json").status_code,403)
        self.assertEqual(self.create_report(revision=0).status_code,409)
        self.assertEqual(SchoolReport.objects.count(),1)
