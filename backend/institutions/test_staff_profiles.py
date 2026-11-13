"""Security, profile ownership, teacher/admin visibility and revision tests."""
import json
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .staff_models import StaffRecord


class StaffProfileTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create_user(username="prof-photo", password="Pass-for-prof-123!")
        self.director = User.objects.create_user(username="direction-photo", password="Pass-for-dir-123!")
        self.other = User.objects.create_user(username="unknown-photo", password="Pass-for-other-123!")
        org = Organization.objects.create(name="Groupe des établissements")
        self.school = School.objects.create(organization=org, name="Lycée principal")
        self.school_two = School.objects.create(organization=org, name="Lycée secondaire")
        for school in (self.school, self.school_two):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        for user, role in ((self.teacher, "enseignant"), (self.director, "direction")):
            SchoolMember.objects.create(school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code=role))
        self.staff = StaffRecord.objects.create(school=self.school, account=self.teacher,
            staff_code="PROF-014", first_name="Annie", last_name="Nze", position="Enseignante")
        self.base = f"/api/v1/schools/{self.school.pk}/"
        self.profile = self.base + "staff/me/profile"
        self.photo = self.base + f"staff/{self.staff.pk}/photo"
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.teacher)

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def patch(self, payload):
        return self.client.patch(self.profile, json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf)

    def upload(self, payload=b"\xff\xd8\xff" + b"private picture data",
               mime="image/jpeg"):
        return self.client.post(self.photo, {
            "photo": SimpleUploadedFile("photo.jpg", payload, content_type=mime),
        }, HTTP_X_CSRFTOKEN=self.csrf)

    def test_self_profile_uses_canonical_staff_record_and_restricts_fields(self):
        result = self.client.get(self.profile)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["staff_code"], "PROF-014")
        self.assertEqual(self.patch({"revision": 1, "position": "Directrice"}).status_code, 422)
        self.assertEqual(self.patch({"revision": 1, "presentation": "Cours de mathématiques"}).status_code, 200)
        self.assertEqual(self.patch({"revision": 1, "presentation": "Écrasement"}).status_code, 409)
        self.assertEqual(self.client.get(self.profile).json()["presentation"], "Cours de mathématiques")
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.position, "Enseignante")

    def test_photo_shared_with_authorized_personnel_view(self):
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.client.get(self.photo).content, b"\xff\xd8\xff" + b"private picture data")
        self.assertEqual(self.patch({"revision": 2, "presentation": "Cours de mathématiques"}).status_code, 200)
        self.login(self.director)
        team = self.client.get(self.base + "staff")
        self.assertEqual(team.status_code, 200)
        self.assertEqual(team.json()["staff"][0]["photo_url"], self.photo)
        self.assertEqual(team.json()["staff"][0]["presentation"], "Cours de mathématiques")
        response = self.client.get(self.photo)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.post(self.photo).status_code, 403)

    def test_revoked_access_foreign_school_and_invalid_photo(self):
        self.assertEqual(self.upload(b"not a photo").status_code, 422)
        self.assertEqual(self.upload(b"\xff\xd8\xff" + b"x" * 350_000).status_code, 422)
        self.login(self.other)
        self.assertEqual(self.client.get(self.photo).status_code, 404)
        self.assertEqual(self.client.get(self.profile).status_code, 404)
        self.assertEqual(self.client.get(self.base.replace(str(self.school.pk), str(self.school_two.pk)) + "staff/me/profile").status_code, 404)
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base.replace(str(self.school.pk), str(self.school_two.pk)) + f"staff/{self.staff.pk}/photo").status_code, 404)
        self.assertEqual(self.upload().status_code, 200)
        removed = self.client.delete(self.photo, HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(removed.status_code, 200)
        self.assertIsNone(removed.json()["photo_url"])
        SchoolMember.objects.filter(school=self.school, user=self.teacher).update(active=False)
        self.assertEqual(self.client.get(self.profile).status_code, 404)
        self.assertEqual(self.client.get(self.photo).status_code, 404)

    def test_missing_staff_link_and_csrf(self):
        self.login(self.director)
        self.assertEqual(self.client.get(self.profile).status_code, 404)
        self.assertEqual(self.client.post(self.photo, {}).status_code, 403)
        self.login(self.teacher)
        self.assertEqual(self.patch({"revision": 1, "presentation": "Visible"}).status_code, 200)
        # Anti-CSRF: logged-in users cannot mutate a profile without a token.
        self.assertEqual(self.client.patch(self.profile, json.dumps({"revision": 2, "presentation": "Invalid"}),
            content_type="application/json").status_code, 403)
