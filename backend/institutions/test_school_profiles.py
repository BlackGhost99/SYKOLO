"""Tests des catégories scolaires et des cycles : aucun effet sur les dossiers existants."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, School, PlatformAudit
from .school_functions import positions_for_school, validate_account_functions, validate_position


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

    def test_preschool_profile_groups_equivalent_positions_and_provisions_direction(self):
        result = self.post("/api/v1/platform/schools", {
            **self.payload, "school_type": "maternelle", "education_cycles": ["prescolaire"],
        })
        self.assertEqual(result.status_code, 201, result.content)
        school = School.objects.get(pk=result.json()["id"])
        detail = self.client.get(f"/api/v1/platform/schools/{school.pk}/detail").json()
        roles = {role["code"]: role for role in detail["roles"]}
        self.assertEqual(roles["direction"]["label"], "Direction de la maternelle")
        self.assertEqual(roles["enseignant"]["suggested_function"], "educateur_prescolaire")
        self.assertNotIn("eleve", roles)
        functions = {position["code"] for position in detail["functions"]}
        self.assertIn("educateur_prescolaire", functions)
        self.assertTrue({"enseignant", "instituteur", "proviseur"}.isdisjoint(functions))
        self.assertEqual(school.members.get().function_codes, ["directeur_maternelle"])
        school.enabled_functions = ["enseignant"]
        self.assertEqual(validate_account_functions(school, ["enseignant", "educateur_prescolaire"]),
                         ["educateur_prescolaire"])
        validate_position(school, "direction_etablissement", "")
        validate_position(school, "enseignant", "prescolaire")

        primary = School.objects.create(organization=school.organization, name="Primaire",
                                        school_type="primaire", education_cycles=["primaire"])
        self.assertNotIn("educateur_prescolaire", {position["code"] for position in positions_for_school(primary)})

    def test_primary_profile_provisions_accounts_and_groups_legacy_functions(self):
        result = self.post("/api/v1/platform/schools", {
            **self.payload, "school_type": "primaire", "education_cycles": ["primaire"],
        })
        self.assertEqual(result.status_code, 201, result.content)
        school = School.objects.get(pk=result.json()["id"])
        url = f"/api/v1/platform/schools/{school.pk}"
        detail = self.client.get(url + "/detail").json()
        roles = {role["code"]: role for role in detail["roles"]}
        self.assertEqual(roles["direction"]["label"], "Direction du primaire")
        self.assertEqual(roles["enseignant"]["label"], "Enseignant / Enseignante du primaire")
        self.assertEqual(roles["enseignant"]["suggested_function"], "instituteur")
        self.assertIn("eleve", roles)
        functions = {position["code"] for position in detail["functions"]}
        self.assertIn("surveillant", functions)
        self.assertTrue({"enseignant", "educateur_prescolaire", "proviseur"}.isdisjoint(functions))
        self.assertEqual(school.members.get().function_codes, ["directeur_primaire"])

        teacher = {
            "role": "enseignant", "username": "classe-primaire", "email": "classe@example.org",
            "first_name": "Alex", "last_name": "Test", "password": "Primary-profile-2026!",
        }
        rejected = self.post(url + "/users", {**teacher, "function_codes": ["educateur_prescolaire"]})
        self.assertEqual(rejected.status_code, 422, rejected.content)
        created = self.post(url + "/users", {**teacher, "function_codes": ["enseignant", "instituteur"]})
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(school.members.get(role__code="enseignant").function_codes, ["instituteur"])
        validate_position(school, "enseignant", "primaire")
        validate_position(school, "direction_etablissement", "")

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
