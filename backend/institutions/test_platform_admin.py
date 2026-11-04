import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Organization, PlatformAudit, School, SchoolAdminPolicy, SchoolMember, SchoolRole, Student


class PlatformAdminConsoleTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="chief", email="chief@example.org", password="Valid-platform-2026!"
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        self.payload = {
            "organization_name": "Groupe A", "school_name": "Lycée Arc",
            "username": "direction_arc", "email": "arc@example.org",
            "first_name": "Aya", "last_name": "Test",
            "password": "Secure-Director-2026!", "role": "direction",
        }
        created = self.post("/api/v1/platform/schools", self.payload)
        self.assertEqual(created.status_code, 201, created.content)
        self.school = School.objects.get(pk=created.json()["id"])
        self.director = get_user_model().objects.get(username="direction_arc")

    def post(self, path, payload):
        return self.client.post(path, json.dumps(payload), content_type="application/json")

    def test_dashboard_contains_real_counts_and_paginated_directory(self):
        self.assertEqual(Organization.objects.count(), 1)
        r = self.client.get("/api/v1/platform/dashboard?page=1&per_page=5")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["schools_total"], 1)
        self.assertEqual(data["organizations"], 1)
        self.assertEqual(data["users_active"], 1)
        self.assertEqual(data["filtered_total"], 1)
        self.assertEqual(data["schools"][0]["name"], "Lycée Arc")
        self.assertEqual(len(data["recent_events"]), 1)
        filtered = self.client.get("/api/v1/platform/dashboard?q=inexistant")
        self.assertEqual(filtered.json()["filtered_total"], 0)

    def test_admin_details_roles_are_school_scoped(self):
        r = self.client.get(f"/api/v1/platform/schools/{self.school.pk}/detail")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["school"]["name"], "Lycée Arc")
        self.assertEqual(data["members_count"], 1)
        self.assertTrue(any(m["username"] == "direction_arc" for m in data["members"]))
        self.assertTrue(any(role["code"] == "enseignant" for role in data["roles"]))
        self.assertIsNone(data["policy"]["max_users"])

    def test_another_school_member_cannot_read_platform(self):
        self.client.force_login(self.director)
        paths = [
            "/api/v1/platform/dashboard",
            "/api/v1/platform/organizations",
            "/api/v1/platform/audit",
            f"/api/v1/platform/schools/{self.school.pk}/detail",
        ]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403, path)

    def test_requires_mfa_even_for_superuser(self):
        session = self.client.session
        session["mfa_verified"] = False
        session.save()
        self.assertEqual(self.client.get("/api/v1/platform/dashboard").status_code, 403)
        self.assertEqual(self.post("/api/v1/platform/organizations", {"name": "Autre"}).status_code, 403)

    def test_organization_creation_and_audit(self):
        r = self.post("/api/v1/platform/organizations", {"name": "Groupe B"})
        self.assertEqual(r.status_code, 201, r.content)
        duplicate = self.post("/api/v1/platform/organizations", {"name": "groupe b"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertTrue(PlatformAudit.objects.filter(event="organization_created", subject="Groupe B").exists())

    def test_school_suspend_reactivate_must_be_reasoned_and_audited(self):
        endpoint = f"/api/v1/platform/schools/{self.school.pk}/action"
        self.assertEqual(self.post(endpoint, {"action":"status", "active":False}).status_code, 422)
        disabled = self.post(endpoint, {"action":"status", "active":False, "reason":"Fin du contrat"})
        self.assertEqual(disabled.status_code, 200, disabled.content)
        self.school.refresh_from_db()
        self.assertFalse(self.school.is_active)
        self.assertTrue(PlatformAudit.objects.filter(event="school_suspended", school=self.school).exists())
        enabled = self.post(endpoint, {"action":"status", "active":True, "reason":"Reprise"})
        self.assertEqual(enabled.status_code, 200)
        self.school.refresh_from_db()
        self.assertTrue(self.school.is_active)

    def test_role_assignment_does_not_cross_establishments(self):
        role = SchoolRole.objects.get(school=self.school, code="enseignant")
        member = SchoolMember.objects.get(school=self.school, user=self.director)
        endpoint = f"/api/v1/platform/schools/{self.school.pk}/members/{member.pk}/action"
        result = self.post(endpoint, {"action":"role","role_id":str(role.pk),"reason":"Nouvelle fonction"})
        self.assertEqual(result.status_code, 200, result.content)
        member.refresh_from_db()
        self.assertEqual(member.role_id, role.pk)
        self.assertTrue(PlatformAudit.objects.filter(event="member_role_changed").exists())
        school_b = School.objects.create(organization=self.school.organization, name="École B")
        bad_role = SchoolRole.objects.create(school=school_b, code="test", label="Test", permissions=[])
        failed = self.post(endpoint, {"action":"role","role_id":str(bad_role.pk),"reason":"Essai"})
        self.assertEqual(failed.status_code, 422)
        member.refresh_from_db()
        self.assertEqual(member.role_id, role.pk)

    def test_member_suspension_only_affects_selected_school(self):
        other = School.objects.create(organization=self.school.organization, name="École B")
        other_role = SchoolRole.objects.create(school=other, code="direction", label="Direction", permissions=["school.view"])
        SchoolMember.objects.create(school=other, user=self.director, role=other_role)
        member = SchoolMember.objects.get(school=self.school, user=self.director)
        endpoint = f"/api/v1/platform/schools/{self.school.pk}/members/{member.pk}/action"
        result = self.post(endpoint, {"action":"status","active":False,"reason":"Réaffectation"})
        self.assertEqual(result.status_code, 200, result.content)
        member.refresh_from_db()
        self.assertFalse(member.active)
        self.assertTrue(SchoolMember.objects.get(school=other, user=self.director).active)
        self.assertTrue(self.director.is_active)

    def test_limits_block_account_and_student_creation(self):
        endpoint = f"/api/v1/platform/schools/{self.school.pk}/action"
        r = self.post(endpoint, {
            "action":"plan","plan_name":"Essai","max_users":1,"max_students":1,
            "revision":0,"reason":"Plafond contractuel"
        })
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(SchoolAdminPolicy.objects.get(school=self.school).max_users, 1)
        teacher = {
            "username":"prof_nouveau","email":"prof@example.org",
            "first_name":"Test","last_name":"Prof",
            "password":"Secure-Teacher-2026!","role":"enseignant",
        }
        too_many = self.post(f"/api/v1/platform/schools/{self.school.pk}/users",teacher)
        self.assertEqual(too_many.status_code, 409)
        self.client.force_login(self.director)
        a = self.post(f"/api/v1/schools/{self.school.pk}/students", {
            "student_code":"ARC1","first_name":"Tom","last_name":"Test"
        })
        self.assertEqual(a.status_code, 201, a.content)
        b = self.post(f"/api/v1/schools/{self.school.pk}/students", {
            "student_code":"ARC2","first_name":"Alex","last_name":"Test"
        })
        self.assertEqual(b.status_code, 409, b.content)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 1)

    def test_plan_revision_prevents_lost_updates(self):
        endpoint = f"/api/v1/platform/schools/{self.school.pk}/action"
        body = {"action":"plan","plan_name":"Standard","max_users":10,
                "max_students":100,"revision":0,"reason":"Convention"}
        self.assertEqual(self.post(endpoint, body).status_code, 200)
        self.assertEqual(self.post(endpoint, body).status_code, 409)
        self.assertEqual(SchoolAdminPolicy.objects.get(school=self.school).revision, 2)

    def test_member_directory_search_pagination_and_isolation(self):
        role = SchoolRole.objects.get(school=self.school, code="enseignant")
        User = get_user_model()
        for n in range(24):
            user = User.objects.create_user(
                username=f"prof_{n:02d}", email=f"prof_{n:02d}@example.org",
                password="ValidTeacherPassword2026!"
            )
            SchoolMember.objects.create(school=self.school, user=user, role=role)
        endpoint = f"/api/v1/platform/schools/{self.school.pk}/members"
        first = self.client.get(endpoint + "?page=1&per_page=10")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["total"], 25)
        self.assertEqual(first.json()["pages"], 3)
        self.assertEqual(len(first.json()["members"]), 10)
        last = self.client.get(endpoint + "?page=3&per_page=10")
        self.assertEqual(len(last.json()["members"]), 5)
        match = self.client.get(endpoint + "?q=prof_01&per_page=5")
        self.assertEqual(match.json()["total"], 1)
        self.assertEqual(match.json()["members"][0]["username"], "prof_01")
        self.client.force_login(self.director)
        self.assertEqual(self.client.get(endpoint).status_code, 403)

    def test_audit_returns_school_interventions_without_private_documents(self):
        data = self.client.get("/api/v1/platform/audit?limit=30").json()
        self.assertTrue(data["events"])
        self.assertEqual(data["events"][0]["actor"], "chief")
        self.assertNotIn("password", json.dumps(data).lower())
