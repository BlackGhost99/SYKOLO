"""Parents ayant deja des enfants dans une ecole : aucune nouvelle admission."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole
from .parent_existing_models import ExistingStudentLinkRequest
from .parent_models import GuardianAccountLink
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment


class ExistingParentLinkTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.admin = U.objects.create_user(username="existing-admin", password="P@rentsTest2026-admin!")
        self.parent = U.objects.create_user(username="existing-parent", password="P@rentsTest2026-parent!")
        self.stranger = U.objects.create_user(username="existing-other", password="P@rentsTest2026-other!")
        self.org = Organization.objects.create(name="YEM existing parent test")
        self.school = School.objects.create(organization=self.org, name="Lycée AWASSI")
        self.other_school = School.objects.create(organization=self.org, name="Lycée sans catalogue")
        self.inactive = School.objects.create(organization=self.org, name="École fermée", is_active=False)
        for school in (self.school, self.other_school):
            for code,label,perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=perms)
        SchoolMember.objects.create(school=self.school, user=self.admin,
                                    role=SchoolRole.objects.get(school=self.school, code="direction"))
        year=AcademicYear.objects.create(school=self.school, code="2026", name="2026–2027",
            start_date="2026-09-01", end_date="2027-07-31")
        cycle=AcademicCycle.objects.create(school=self.school, code="college", name="Collège")
        level=AcademicLevel.objects.create(school=self.school, cycle=cycle, code="sixieme", name="Sixième")
        klass=AcademicClass.objects.create(school=self.school, year=year, level=level, code="6a", name="Sixième A")
        self.student=Student.objects.create(school=self.school, first_name="Malia",
                                            last_name="Ondo", student_code="AWA-0001")
        self.wrong_student=Student.objects.create(school=self.school, first_name="Aly",
                                                  last_name="Ondo", student_code="AWA-0002")
        self.guardian=StudentGuardian.objects.create(school=self.school, student=self.student,
                                                      full_name="Marie Ondo", relationship="Mère")
        self.wrong_guardian=StudentGuardian.objects.create(school=self.school, student=self.wrong_student,
                                                            full_name="Marie Ondo", relationship="Mère")
        Enrollment.objects.create(school=self.school, student=self.student, year=year,
                                  classroom=klass, enrolled_on="2026-09-14")
        self.client=Client(enforce_csrf_checks=True)
        self.login(self.parent)
        self.url="/api/v1/parents/existing-requests"
        self.school_url=f"/api/v1/schools/{self.school.pk}/parent-existing-requests"
        self.link_url=f"/api/v1/schools/{self.school.pk}/parent-links"

    def login(self, user):
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self, path, data, method="post"):
        return getattr(self.client,method)(path, data=json.dumps(data),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def payload(self, school=None):
        return {"school":str(school or self.school.pk), "first_name":"Malia", "last_name":"Ondo",
                "student_code":"AWA-0001", "guardian_name":"Marie Ondo", "contact_phone":"+24106000000"}

    def request_link(self):
        response=self.write(self.url,self.payload())
        self.assertEqual(response.status_code,201,response.content)
        return response.json()["id"]

    def test_unpublished_school_is_discoverable_without_student_information(self):
        response=self.client.get("/api/v1/parents/existing-schools?q=lyc")
        self.assertEqual(response.status_code,200)
        data=response.json()["schools"]
        self.assertEqual({row["name"] for row in data}, {"Lycée AWASSI","Lycée sans catalogue"})
        self.assertNotIn("students",str(data))
        self.assertNotIn("guardian",str(data))
        self.assertNotIn("École fermée",str(data))

    def test_pending_is_private_deduplicated_and_does_not_enroll_or_grant_access(self):
        initial=Enrollment.objects.count()
        id=self.request_link()
        same=self.write(self.url,self.payload())
        self.assertEqual(same.status_code,200)
        self.assertEqual(same.json()["id"],id)
        self.assertEqual(ExistingStudentLinkRequest.objects.count(),1)
        self.assertEqual(Enrollment.objects.count(),initial)
        self.assertEqual(GuardianAccountLink.objects.count(),0)
        self.assertEqual(self.client.get("/api/v1/parents/children").json()["children"],[])
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.url).json()["requests"],[])
        self.assertEqual(self.write(self.url+"/"+id,{"status":"cancelled"},"patch").status_code,404)
        self.assertEqual(self.client.get(self.school_url).status_code,404)
        self.login(self.parent)
        self.assertEqual(self.write(self.url+"/"+id,{"status":"cancelled"},"patch").status_code,200)
        self.assertEqual(ExistingStudentLinkRequest.objects.get().status,"cancelled")

    def test_human_verification_and_parent_role_required_before_access(self):
        id=self.request_link()
        self.login(self.admin)
        queue=self.client.get(self.school_url)
        self.assertEqual(queue.status_code,200)
        self.assertEqual(len(queue.json()["requests"]),1)
        request_payload={"guardian":str(self.guardian.pk),"username":self.parent.username,
                         "identity_verified":True,"request_id":id}
        self.assertEqual(self.write(self.link_url,request_payload).status_code,422)
        SchoolMember.objects.create(school=self.school,user=self.parent,
            role=SchoolRole.objects.get(school=self.school,code="parent"))
        self.assertEqual(self.write(self.link_url,{**request_payload,"identity_verified":False}).status_code,422)
        wrong=self.write(self.link_url,{**request_payload,"guardian":str(self.wrong_guardian.pk)})
        self.assertEqual(wrong.status_code,422,wrong.content)
        self.assertEqual(GuardianAccountLink.objects.count(),0)
        successful=self.write(self.link_url,request_payload)
        self.assertEqual(successful.status_code,201,successful.content)
        row=ExistingStudentLinkRequest.objects.get(pk=id)
        self.assertEqual(row.status,"approved")
        self.assertEqual(row.linked_guardian,self.guardian)
        self.assertEqual(row.reviewed_by,self.admin)
        self.assertTrue(SchoolAudit.objects.filter(event="parent_request_approved",subject=id).exists())
        self.assertEqual(self.client.get(self.school_url).json()["requests"],[])
        self.login(self.parent)
        self.assertEqual(self.client.get(self.url).json()["requests"][0]["status"],"approved")
        children=self.client.get("/api/v1/parents/children").json()["children"]
        self.assertEqual([row["student"] for row in children],[str(self.student.pk)])
        self.assertEqual(Enrollment.objects.count(),1)
        self.assertTrue(self.client.get(self.url).json()["requests"][0]["access_active"])
        self.login(self.admin)
        revoked=self.write(self.link_url+"/"+successful.json()["id"],
            {"revision":1,"active":False},"patch")
        self.assertEqual(revoked.status_code,200,revoked.content)
        self.login(self.parent)
        self.assertFalse(self.client.get(self.url).json()["requests"][0]["access_active"])
        self.assertEqual(self.client.get("/api/v1/parents/children").json()["children"],[])

    def test_request_cannot_be_approved_for_other_account_or_without_matching_code(self):
        id=self.request_link()
        self.login(self.admin)
        SchoolMember.objects.create(school=self.school,user=self.stranger,
            role=SchoolRole.objects.get(school=self.school,code="parent"))
        wrong_owner=self.write(self.link_url,{"guardian":str(self.guardian.pk),
            "username":self.stranger.username,"identity_verified":True,"request_id":id})
        self.assertEqual(wrong_owner.status_code,404)
        self.assertFalse(GuardianAccountLink.objects.exists())
        self.login(self.parent)
        self.assertEqual(self.write(self.url,{"school":str(self.school.pk)},).status_code,422)
        self.login(self.admin)
        refused=self.write(self.school_url+"/"+id,{"status":"rejected"},"patch")
        self.assertEqual(refused.status_code,200)
        self.assertEqual(ExistingStudentLinkRequest.objects.get(pk=id).status,"rejected")
        self.assertEqual(self.write(self.school_url+"/"+id,{"status":"rejected"},"patch").status_code,409)
        self.login(self.parent)
        self.assertEqual(self.client.get("/api/v1/parents/children").json()["children"],[])

    def test_school_isolation_and_plain_request_never_look_up_student(self):
        self.login(self.parent)
        id=self.request_link()
        self.assertEqual(self.write(self.url,{
            **self.payload(school=self.other_school.pk),"first_name":"Inconnue",
            "last_name":"Personne","student_code":"AUCUN",
        }).status_code,201)
        self.assertEqual(ExistingStudentLinkRequest.objects.count(),2)
        self.login(self.admin)
        queue=self.client.get(self.school_url).json()["requests"]
        self.assertEqual([item["id"] for item in queue],[id])
        self.assertFalse(GuardianAccountLink.objects.exists())
