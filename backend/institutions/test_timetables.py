"""Module 13: timetable collision and security integration tests."""
import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .models import Organization, School, SchoolRole, SchoolMember
from .services import ROLE_TEMPLATES
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .curriculum_models import Subject, CourseOffering, CourseInstructor
from .staff_models import StaffRecord, StaffAssignment
from .timetable_models import TimetableEntry, TimetableRoom


class TimetableTests(TestCase):
    def setUp(self):
        U=get_user_model()
        self.director=U.objects.create_user(username="timetable-admin",password="Strong timetable director 2026!")
        self.teacher=U.objects.create_user(username="timetable-teacher",password="Strong timetable teacher 2026!")
        self.outsider=U.objects.create_user(username="timetable-guest",password="Strong timetable guest 2026!")
        org=Organization.objects.create(name="Groupe YEM test")
        self.school=School.objects.create(organization=org,name="École A")
        self.other=School.objects.create(organization=org,name="École B")
        for school in (self.school,self.other):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=permissions)
        for user,role in ((self.director,"direction"),(self.teacher,"enseignant")):
            SchoolMember.objects.create(school=self.school,user=user,
                role=SchoolRole.objects.get(school=self.school,code=role))
        self.year=AcademicYear.objects.create(school=self.school,code="2026",name="2026-2027",
            start_date="2026-09-01",end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school,code="college",name="Collège")
        level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="six",name="Sixième")
        self.class_a=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="a",name="6A")
        self.class_b=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="b",name="6B")
        subject_a=Subject.objects.create(school=self.school,code="math",name="Mathématiques")
        subject_b=Subject.objects.create(school=self.school,code="fr",name="Français")
        self.course_a=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.class_a,subject=subject_a)
        self.course_b=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.class_b,subject=subject_a)
        self.course_a2=CourseOffering.objects.create(school=self.school,year=self.year,classroom=self.class_a,subject=subject_b)
        t1=StaffRecord.objects.create(school=self.school,staff_code="P1",first_name="Jean",last_name="A",position="Professeur",account=self.teacher)
        t2=StaffRecord.objects.create(school=self.school,staff_code="P2",first_name="Lina",last_name="B",position="Professeur")
        a1=StaffAssignment.objects.create(school=self.school,staff=t1,year=self.year,classroom=self.class_a)
        b1=StaffAssignment.objects.create(school=self.school,staff=t1,year=self.year,classroom=self.class_b)
        a2=StaffAssignment.objects.create(school=self.school,staff=t2,year=self.year,classroom=self.class_a)
        b2=StaffAssignment.objects.create(school=self.school,staff=t2,year=self.year,classroom=self.class_b)
        self.i_a=CourseInstructor.objects.create(school=self.school,course=self.course_a,staff_assignment=a1)
        self.i_b=CourseInstructor.objects.create(school=self.school,course=self.course_b,staff_assignment=b1)
        self.i_a2=CourseInstructor.objects.create(school=self.school,course=self.course_a2,staff_assignment=a2)
        self.i_b2=CourseInstructor.objects.create(school=self.school,course=self.course_b,staff_assignment=b2)
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base=f"/api/v1/schools/{self.school.pk}/timetable/"
        self.r1=self.create("rooms",{"code":"a","name":"Salle A","capacity":30})
        self.r2=self.create("rooms",{"code":"b","name":"Salle B"})
        self.s1=self.create("slots",{"year":str(self.year.pk),"code":"s1","label":"Début",
            "start_time":"08:00","end_time":"09:00"})
        self.s2=self.create("slots",{"year":str(self.year.pk),"code":"s2","label":"Suite",
            "start_time":"09:00","end_time":"10:00"})
        self.sx=self.create("slots",{"year":str(self.year.pk),"code":"sx","label":"Chevauchement",
            "start_time":"08:30","end_time":"09:30"})

    def login(self, user):
        self.client.force_login(user)
        self.token=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self,route,data,method="post"):
        return getattr(self.client,method)(self.base+route,json.dumps(data),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.token)

    def create(self,route,data):
        r=self.write(route,data)
        self.assertEqual(r.status_code,201,r.content.decode())
        return r.json()

    def entry(self,course=None,instructor=None,slot=None,room=None,weekday=0,
              start="2026-09-01",end="2027-07-31"):
        return {"course":str((course or self.course_a).pk),"instructor":str((instructor or self.i_a).pk),
            "slot":(slot or self.s1)["id"],"room":(room or self.r1)["id"],
            "weekday":weekday,"effective_from":start,"effective_to":end}

    def test_detects_collisions_and_allows_adjacent_slots(self):
        first=self.create("entries",self.entry())
        response=self.write("entries",self.entry(course=self.course_a2,instructor=self.i_a2,
            room=self.r2,slot=self.sx))
        self.assertEqual(response.status_code,409)
        self.assertIn("classe",response.json()["conflicts"][0]["resources"])
        response=self.write("entries",self.entry(course=self.course_b,instructor=self.i_b,
            room=self.r2,slot=self.sx))
        self.assertEqual(response.status_code,409)
        self.assertIn("enseignant",response.json()["conflicts"][0]["resources"])
        response=self.write("entries",self.entry(course=self.course_b,instructor=self.i_b2,
            room=self.r1,slot=self.sx))
        self.assertEqual(response.status_code,409)
        self.assertIn("salle",response.json()["conflicts"][0]["resources"])
        self.create("entries",self.entry(course=self.course_b,instructor=self.i_b2,room=self.r2,slot=self.s2))
        self.create("entries",self.entry(course=self.course_a2,instructor=self.i_a2,weekday=1))
        self.assertEqual(TimetableEntry.objects.count(),3)
        self.assertEqual(self.client.get(self.base+"entries/"+first["id"]).json()["teacher"],"Jean A")

    def test_date_windows_revisions_and_archiving(self):
        self.assertEqual(self.write("entries",self.entry(start="2026-09-01",end="2026-09-06")).status_code,422)
        monday=self.create("entries",self.entry(start="2026-09-07",end="2026-09-07"))
        self.create("entries",self.entry(start="2026-09-14",end="2026-09-14"))
        self.assertEqual(self.write("entries",self.entry(start="2026-09-07",end="2026-09-28")).status_code,409)
        self.assertEqual(self.write("entries/"+monday["id"],{"revision":0,"active":False},method="patch").status_code,409)
        disabled=self.write("entries/"+monday["id"],{"revision":1,"active":False},method="patch")
        self.assertEqual(disabled.status_code,200,disabled.content.decode())
        self.create("entries",self.entry(start="2026-09-07",end="2026-09-07"))
        self.assertEqual(self.write("entries/"+monday["id"],{"revision":1,"weekday":3},method="patch").status_code,409)

    def test_immutability_of_busy_resources_and_invalid_links(self):
        first=self.create("entries",self.entry())
        self.assertEqual(self.write("slots/"+self.s1["id"],{"revision":1,"start_time":"07:00"},method="patch").status_code,409)
        self.assertEqual(self.write("rooms/"+self.r1["id"],{"revision":1,"active":False},method="patch").status_code,409)
        self.assertEqual(self.write("entries",self.entry(instructor=self.i_b)).status_code,422)
        self.assertEqual(self.write("entries",self.entry(weekday=7)).status_code,422)
        self.assertEqual(self.write("slots",{"year":str(self.year.pk),"code":"bad","label":"Invalide",
            "start_time":"09:00","end_time":"09:00"}).status_code,422)
        foreign=TimetableRoom.objects.create(school=self.other,code="other",name="Étrangère")
        payload=self.entry()
        payload["room"]=str(foreign.pk)
        self.assertEqual(self.write("entries",payload).status_code,422)

    def test_read_scope_permissions_and_csrf(self):
        own=self.create("entries",self.entry())
        self.create("entries",self.entry(course=self.course_a2,instructor=self.i_a2,room=self.r2,weekday=2))
        self.login(self.teacher)
        rows=self.client.get(self.base+"entries").json()["entries"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["id"],own["id"])
        self.assertEqual(self.write("entries",self.entry(weekday=3)).status_code,403)
        self.login(self.outsider)
        self.assertEqual(self.client.get(self.base+"entries").status_code,404)
        self.login(self.director)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other.pk}/timetable/entries").status_code,404)
        self.assertEqual(self.client.post(self.base+"rooms",json.dumps({"code":"c","name":"C"}),
            content_type="application/json").status_code,403)
        self.assertEqual(self.client.delete(self.base+"rooms/"+self.r1["id"],
            HTTP_X_CSRFTOKEN=self.token).status_code,405)
