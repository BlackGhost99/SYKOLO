"""Notifications YEM : école <-> parent, avec validation d'identité indépendante."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Organization, School, SchoolMember, SchoolRole
from .family_notification_models import SchoolFamilyNotification
from .parent_existing_models import ExistingStudentLinkRequest
from .parent_models import GuardianAccountLink
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian


class FamilyInboxTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.admin = U.objects.create_user(username="notif-direction", password="Notifs-Test-School2026!")
        self.parent = U.objects.create_user(username="notif-parent", first_name="Sylvie", last_name="NDONG",
                                            password="Notifs-Test-Parent2026!")
        self.stranger = U.objects.create_user(username="notif-stranger", password="Notifs-Test-Stranger2026!")
        org = Organization.objects.create(name="YEM inbox tests")
        self.school = School.objects.create(organization=org, name="Lycée AWASSI")
        self.other_school = School.objects.create(organization=org, name="Autre lycée")
        for school in (self.school, self.other_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        SchoolMember.objects.create(school=self.school, user=self.admin,
                                    role=SchoolRole.objects.get(school=self.school, code="direction"))
        self.student = Student.objects.create(
            school=self.school, first_name="Amadou", last_name="NDONG", student_code="AWA-26-0046")
        Student.objects.create(
            school=self.school, first_name="Amadou", last_name="NDONG", student_code="AWA-26-0047")
        self.guardian = StudentGuardian.objects.create(
            school=self.school, student=self.student, full_name="Sylvie NDONG", relationship="Mère")
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.parent)
        self.parent_path = "/api/v1/parents"
        self.base = f"/api/v1/schools/{self.school.pk}"

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, url, data, method="post"):
        return getattr(self.client, method)(
            url, data=json.dumps(data), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def request_link(self):
        res = self.post(self.parent_path+"/existing-requests", {
            "school": str(self.school.pk), "first_name": "Amadou", "last_name": "NDONG",
            "student_code": "AWA-26-0046", "guardian_name": "Sylvie NDONG",
            "contact_phone": "+241062308363", "whatsapp_opt_in": True,
        })
        self.assertEqual(res.status_code, 201, res.content)
        return res.json()["id"]

    def test_inbox_notifies_school_and_parent_without_auto_grant(self):
        request_id = self.request_link()
        alerts = self.client.get(self.parent_path+"/notifications").json()["notifications"]
        self.assertTrue(any(n["kind"]=="family_message" and n["origin"]=="system" for n in alerts))
        self.assertFalse(GuardianAccountLink.objects.exists())
        self.assertFalse(SchoolMember.objects.filter(school=self.school, user=self.parent).exists())

        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+"/notification-inbox").status_code, 404)
        self.login(self.admin)
        inbox = self.client.get(self.base+"/notification-inbox")
        self.assertEqual(inbox.status_code, 200, inbox.content)
        self.assertEqual([n["id"] for n in inbox.json()["requests"]], [request_id])
        self.assertGreaterEqual(inbox.json()["unread"], 1)
        candidates = self.client.get(self.base+"/notification-inbox/requests/"+request_id+"/candidates")
        self.assertEqual(candidates.status_code, 200)
        self.assertEqual([s["student_code"] for s in candidates.json()["candidates"]], ["AWA-26-0046"])
        self.assertEqual(candidates.json()["candidates"][0]["guardians"][0]["id"], str(self.guardian.pk))

        payload = {"guardian":str(self.guardian.pk), "username":self.parent.username,
                   "identity_verified":True, "request_id":request_id}
        self.assertEqual(self.post(self.base+"/parent-links",{**payload,"identity_verified":False}).status_code,422)
        approved = self.post(self.base+"/parent-links", payload)
        self.assertEqual(approved.status_code, 201, approved.content)
        self.assertEqual(self.client.get(self.base+"/notification-inbox").json()["requests"],[])
        self.assertEqual(ExistingStudentLinkRequest.objects.get(pk=request_id).status, "approved")
        self.login(self.parent)
        alerts = self.client.get(self.parent_path+"/notifications").json()["notifications"]
        self.assertTrue(any(n["kind"]=="family_message" and "accès" in n["message"] for n in alerts))
        self.assertTrue(GuardianAccountLink.objects.filter(user=self.parent, guardian=self.guardian, active=True).exists())

    def test_message_exchange_read_receipts_and_school_isolation(self):
        request_id = self.request_link()
        sent = self.post(self.parent_path+"/notification-messages", {
            "school": str(self.school.pk), "request_id": request_id,
            "message": "Bonjour, est-ce que mon dossier est complet ?",
        })
        self.assertEqual(sent.status_code, 201, sent.content)
        self.assertEqual(sent.json()["destination"], "school")
        self.assertEqual(self.post(self.parent_path+"/notification-messages", {
            "school": str(self.other_school.pk), "message": "Message non autorisé"
        }).status_code, 404)
        self.login(self.admin)
        staff = self.client.get(self.base+"/notification-inbox").json()
        self.assertEqual(len(staff["messages"]), 1)
        self.assertEqual(staff["messages"][0]["id"],sent.json()["id"])
        self.assertEqual(self.post(self.base+"/notification-inbox/"+sent.json()["id"],{
            "read":True},"patch").status_code,200)
        reply = self.post(self.base+"/notification-inbox",{
            "username":self.parent.username, "request_id":request_id,
            "message":"Votre dossier est en cours de vérification."
        })
        self.assertEqual(reply.status_code, 201, reply.content)
        self.assertEqual(reply.json()["destination"], "parent")
        self.login(self.parent)
        feed = self.client.get(self.parent_path+"/notifications").json()["notifications"]
        self.assertTrue(any(n["id"]==reply.json()["id"] and n["school"]=="Lycée AWASSI" for n in feed))
        self.assertEqual(self.post(self.parent_path+"/notification-messages/"+reply.json()["id"],{
            "read":True},"patch").status_code,200)
        self.assertTrue(SchoolFamilyNotification.objects.get(pk=reply.json()["id"]).read_at)

    def test_parent_cannot_impersonate_school_or_access_other_recipient(self):
        request_id = self.request_link()
        self.login(self.admin)
        reply = self.post(self.base+"/notification-inbox",{
            "username":self.parent.username, "request_id":request_id, "message":"Réponse privée."
        })
        self.assertEqual(reply.status_code,201)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.parent_path+"/notifications").json()["notifications"],[])
        self.assertEqual(self.post(self.parent_path+"/notification-messages/"+reply.json()["id"],
                                   {"read":True},"patch").status_code,404)
        self.assertEqual(self.post(self.parent_path+"/notification-messages",{
            "school":str(self.school.pk), "request_id":request_id,"message":"Usurpation"
        }).status_code,404)
        self.assertEqual(self.post(self.base+"/notification-inbox",{
            "username":self.parent.username,"message":"Usurpation de direction"
        }).status_code,404)
