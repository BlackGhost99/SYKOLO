"""Tests des catégories scolaires et des cycles : aucun effet sur les dossiers existants."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, School, PlatformAudit


class SchoolProfilesTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="plateforme-profils", email="profils@example.org",
            password="Password-for-tests-2026!"
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session["mfa_verified"] = True
        session.save()
        self.payload = {
            "organization_name": "Fondation des établissements",
            "school_name": "École du test",
            "school_type": "lycee_general",
            "education_cycles": ["college", "lycee_general"],
            "username": "proviseur-test",
            "email": "proviseur@example.org",
            "first_name": "Aline",
            "last_name": "Test",
            "password": "Responsable-test-2026!",
            "role": "direction",
        }

    def post(self, path, payload):
        return self.client.post(
            path, json.dumps(payload), content_type="application/json"
        )

    def test_profile_catalog_lists_mixed_secondary_cycles(self):
        response = self.client.get("/api/v1/platform/schools")
        self.assertEqual(response.status_code, 200)
        options = {p["code"]: p for p in response.json()["school_profiles"]}
        self.assertIn("college", options["lycee_general"]["allowed_cycles"])
        self.assertIn("prescolaire", options["groupe_scolaire"]["allowed_cycles"])

    def test_new_school_requires_type_and_compatible_cycles(self):
        path = "/api/v1/platform/schools"
        missing = self.post(path, {**self.payload, "school_type": None})
        self.assertEqual(missing.status_code, 422)
        incompatible = self.post(path, {**self.payload, "education_cycles": ["primaire"]})
        self.assertEqual(incompatible.status_code, 422)
        duplicate = self.post(path, {**self.payload, "education_cycles": ["college", "college"]})
        self.assertEqual(duplicate.status_code, 422)
        self.assertEqual(School.objects.count(), 0)

    def test_creation_preserves_selected_type_and_cycles(self):
        result = self.post("/api/v1/platform/schools", self.payload)
        self.assertEqual(result.status_code, 201, result.content)
        school = School.objects.get()
        self.assertEqual(school.school_type, "lycee_general")
        self.assertEqual(school.education_cycles, ["college", "lycee_general"])
        detail = self.client.get(
            "/api/v1/platform/schools/" + str(school.pk) + "/detail"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["school"]["school_type"], "lycee_general")
        self.assertEqual(detail.json()["school"]["education_cycles"], ["college", "lycee_general"])

    def test_legacy_school_can_be_classified_with_audit(self):
        org = Organization.objects.create(name="Groupe existant")
        school = School.objects.create(organization=org, name="Lycée existant")
        self.assertEqual(school.school_type, "non_classe")
        url = "/api/v1/platform/schools/" + str(school.pk) + "/action"
        no_reason = self.post(url, {
            "action": "profile", "school_type": "lycee_general",
            "education_cycles": ["college", "lycee_general"],
        })
        self.assertEqual(no_reason.status_code, 422)
        saved = self.post(url, {
            "action": "profile", "school_type": "lycee_general",
            "education_cycles": ["college", "lycee_general"],
            "reason": "Classification de l'établissement existant",
        })
        self.assertEqual(saved.status_code, 200, saved.content)
        school.refresh_from_db()
        self.assertEqual(school.school_type, "lycee_general")
        self.assertEqual(school.education_cycles, ["college", "lycee_general"])
        self.assertTrue(PlatformAudit.objects.filter(
            school=school, event="school_profile_updated"
        ).exists())

    def test_school_director_cannot_reclassify_his_school(self):
        created = self.post("/api/v1/platform/schools", self.payload)
        self.assertEqual(created.status_code, 201)
        user = get_user_model().objects.get(username="proviseur-test")
        self.client.force_login(user)
        forbidden = self.post(
            "/api/v1/platform/schools/" + created.json()["id"] + "/action",
            {"action": "profile", "school_type": "college",
             "education_cycles": ["college"], "reason": "Tentative"},
        )
        self.assertEqual(forbidden.status_code, 403)
