"""Synthetic diary tests: school/cycle boundary, family publication and concurrency."""
import json
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .curriculum_models import Subject, CourseOffering, CourseInstructor
from .models import Organization, School, SchoolRole, SchoolMember
from .parent_models import GuardianAccountLink
from .services import ROLE_TEMPLATES
from .staff_models import StaffRecord, StaffAssignment
from .student_models import Student, StudentGuardian, Enrollment
from .teaching_diary_models import TeachingDiaryEntry


class DiaryTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="TEST")
        self.school = School.objects.create(organization=org, name="TEST")
        self.other = School.objects.create(organization=org, name="Autre")
        self.users = {}
        for name, role in (("teacher","enseignant"),("director","direction"),("parent","parent"),("unassigned","enseignant")):
            user = get_user_model().objects.create_user(username="diary-"+name)
            perms = next(p for code,label,p in ROLE_TEMPLATES if code==role)
            school_role,_ = SchoolRole.objects.get_or_create(school=self.school,code=role,defaults={"label":role,"permissions":perms})
            SchoolMember.objects.create(school=self.school,user=user,role=school_role)
            self.users[name] = user
        self.year = AcademicYear.objects.create(school=self.school, code="2026",name="2026",start_date="2026-09-01",end_date="2027-07-31",status="current")
        self.courses=[]
        for name in ("primaire","college"):
            cycle=AcademicCycle.objects.create(school=self.school,code=name,name=name)
            level=AcademicLevel.objects.create(school=self.school,cycle=cycle,code="test",name="Niveau")
            room=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code=name,name=name)
            subject,_=Subject.objects.get_or_create(school=self.school,code="math",defaults={"name":"Mathématiques"})
            self.courses.append(CourseOffering.objects.create(school=self.school,year=self.year,classroom=room,subject=subject))
        self.course,self.other_course=self.courses
        staff=StaffRecord.objects.create(school=self.school,account=self.users["teacher"],staff_code="TEST",first_name="Test",last_name="Prof",position="Enseignant")
        assignment=StaffAssignment.objects.create(school=self.school,year=self.year,classroom=self.course.classroom,staff=staff,duty="enseignant")
        CourseInstructor.objects.create(school=self.school,course=self.course,staff_assignment=assignment)
        self.student=Student.objects.create(school=self.school,student_code="D1",first_name="Test",last_name="Élève")
        Enrollment.objects.create(school=self.school,student=self.student,year=self.year,classroom=self.course.classroom,enrolled_on="2026-09-10")
        guardian=StudentGuardian.objects.create(school=self.school,student=self.student,full_name="Test Parent")
        self.link=GuardianAccountLink.objects.create(school=self.school,guardian=guardian,user=self.users["parent"])
        self.path=f"/api/v1/schools/{self.school.pk}/diary/courses"
        self.family=f"/api/v1/parents/children/{self.student.pk}/diary?year={self.year.pk}"
        self.payload={"id":str(uuid.uuid4()),"day":"2026-11-17","title":"Fractions","lesson":"Comparer les fractions","homework":"Exercice 1","due_on":"2026-11-20","published":False}

    def login(self,name):
        self.client.force_login(self.users[name])

    def write(self, data, method="post", course=None):
        return getattr(self.client,method)(self.path+"/"+str((course or self.course).pk),
            json.dumps(data),content_type="application/json")

    def test_teacher_assigned_only_and_replay(self):
        self.login("teacher")
        self.assertEqual([r["id"] for r in self.client.get(self.path).json()["courses"]],[str(self.course.pk)])
        self.assertEqual(self.write(self.payload,course=self.other_course).status_code,404)
        self.assertEqual(self.write(self.payload).status_code,201)
        self.assertEqual(self.write(self.payload).status_code,200)
        self.assertEqual(TeachingDiaryEntry.objects.count(),1)
        self.assertEqual(self.write({**self.payload,"title":"Différent"}).status_code,409)
        self.login("unassigned")
        self.assertEqual(self.client.get(self.path).json()["courses"],[])
        self.assertEqual(self.write(self.payload).status_code,404)
        self.login("teacher")
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other.pk}/diary/courses").status_code,404)

    def test_publication_parent_and_revocation(self):
        self.login("teacher")
        self.assertEqual(self.write(self.payload).status_code,201)
        self.login("parent")
        self.assertEqual(self.client.get(self.family).json()["entries"],[])
        self.assertEqual(self.client.get(self.path).status_code,403)
        self.login("teacher")
        payload={**self.payload,"published":True,"revision":1}
        self.assertEqual(self.write(payload,"patch").status_code,200)
        self.assertEqual(self.write(payload,"patch").status_code,409)
        self.login("director")
        self.assertEqual(self.write({**self.payload,"id":str(uuid.uuid4()),"published":True},course=self.other_course).status_code,201)
        self.login("parent")
        entries=self.client.get(self.family).json()["entries"]
        self.assertEqual(len(entries),1)
        self.assertEqual(entries[0]["title"],"Fractions")
        self.assertNotIn("revision",entries[0])
        self.assertNotIn("author",entries[0])
        self.link.active=False;self.link.save()
        self.assertEqual(self.client.get(self.family).status_code,404)

    def test_scoped_director_and_dates(self):
        self.login("director")
        member=SchoolMember.objects.get(user=self.users["director"],school=self.school)
        member.access_cycle_ids=[str(self.course.classroom.level.cycle_id)];member.save()
        self.assertEqual([r["id"] for r in self.client.get(self.path).json()["courses"]],[str(self.course.pk)])
        self.assertEqual(self.write(self.payload,course=self.other_course).status_code,404)
        self.assertEqual(self.write({**self.payload,"due_on":"2026-09-01"}).status_code,422)
        self.assertEqual(self.write({**self.payload,"day":"2027-09-01"}).status_code,422)
        self.assertEqual(self.write(self.payload).status_code,201)
        self.year.status="closed";self.year.active=False;self.year.save()
        self.assertEqual(self.write({**self.payload,"revision":1},"patch").status_code,409)
        self.assertEqual(self.client.get(self.path+"/"+str(self.course.pk)).status_code,200)
