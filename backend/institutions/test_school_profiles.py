"""Tests des catégories scolaires et des cycles : aucun effet sur les dossiers existants."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, School, SchoolRole, PlatformAudit
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

    def test_primary_level_catalog_has_five_configurable_years(self):
        from .school_profiles import CLASS_LEVELS, class_level_options
        expected = ["1re-annee", "2e-annee", "3e-annee", "4e-annee", "5e-annee"]
        self.assertEqual([code for code, _ in CLASS_LEVELS["primaire"]], expected)
        org = Organization.objects.create(name="École de démonstration")
        school = School.objects.create(
            organization=org, name="Complexe scolaire",
            school_type="groupe_scolaire", education_cycles=["prescolaire", "primaire"],
        )
        options = class_level_options(school)
        self.assertEqual(
            [options[f"primaire:{code}"]["name"] for code in expected],
            ["1re année", "2e année", "3e année", "4e année", "5e année"],
        )
        self.assertFalse(any(code in options for code in
            ["primaire:cp1", "primaire:cp2", "primaire:ce1",
             "primaire:ce2", "primaire:cm1", "primaire:cm2"]))
        self.assertIn("prescolaire:ps", options)

    def test_platform_provisions_primary_levels_without_inventing_school_year(self):
        from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass

        created = self.post("/api/v1/platform/schools", {
            **self.payload,
            "school_type": "primaire", "education_cycles": ["primaire"],
            "role": "direction",
        })
        self.assertEqual(created.status_code, 201, created.content)
        school = School.objects.get(pk=created.json()["id"])
        self.assertEqual(AcademicCycle.objects.filter(school=school, code="primaire").count(), 1)
        self.assertEqual(list(AcademicLevel.objects.filter(
            school=school, cycle__code="primaire").order_by("order").values_list("code", flat=True)),
            ["1re-annee", "2e-annee", "3e-annee", "4e-annee", "5e-annee"])
        self.assertFalse(AcademicYear.objects.filter(school=school).exists())
        self.assertFalse(AcademicClass.objects.filter(school=school).exists())
        director = get_user_model().objects.get(username=self.payload["username"])
        self.client.force_login(director)
        response = self.post(f"/api/v1/schools/{school.pk}/academic/years", {
            "name": "2026-2027", "code": "2026-2027",
            "start_date": "2026-09-01", "end_date": "2027-07-31",
        })
        self.assertEqual(response.status_code, 201, response.content)
        year = AcademicYear.objects.get(pk=response.json()["id"])
        self.assertEqual(AcademicClass.objects.filter(school=school, year=year).count(), 5)
        self.assertEqual(list(AcademicClass.objects.filter(
            school=school, year=year).order_by("level__order").values_list("name", flat=True)),
            ["1re année A", "2e année A", "3e année A", "4e année A", "5e année A"])

    def test_secondary_new_schools_get_appropriate_preset_levels(self):
        from .academic_models import AcademicLevel, AcademicClass

        for kind, cycles, codes in (
            ("college", ["college"], {"6e", "5e", "4e", "3e"}),
            ("lycee_general", ["college", "lycee_general"],
             {"6e", "5e", "4e", "3e", "seconde", "premiere", "terminale"}),
            ("lycee_technique", ["lycee_technique"],
             {"seconde", "premiere", "terminale"}),
        ):
            with self.subTest(kind=kind):
                response = self.post("/api/v1/platform/schools", {
                    **self.payload, "school_type": kind, "education_cycles": cycles,
                    "role": "principal" if kind == "college" else "proviseur",
                    "username": "provision-" + kind,
                })
                self.assertEqual(response.status_code, 201, response.content)
                school = School.objects.get(pk=response.json()["id"])
                self.assertEqual(set(AcademicLevel.objects.filter(
                    school=school).values_list("code", flat=True)), codes)
                self.assertEqual(AcademicClass.objects.filter(school=school).count(), 0)

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

    def test_first_account_roles_follow_the_selected_profile_and_cycles(self):
        path = "/api/v1/platform/schools"
        for kind, cycles, head, absent in (
            ("college", ["college"], "principal", "proviseur"),
            ("lycee_general", ["lycee_general"], "proviseur", "principal"),
            ("lycee_technique", ["lycee_technique"], "proviseur", "principal"),
        ):
            with self.subTest(kind=kind):
                options = self.client.get(path, {"school_type": kind, "cycle": cycles}).json()
                codes = {r["code"] for r in options["roles"]}
                self.assertEqual(options["default_role"], head)
                self.assertTrue({head, "proprietaire", "vie_scolaire", "etudes", "secretariat_pedagogique"} <= codes)
                self.assertNotIn(absent, codes)
                payload = {**self.payload, "school_type": kind, "education_cycles": cycles, "username": "chef-" + kind}
                self.assertEqual(self.post(path, {**payload, "role": absent}).status_code, 422)
                created = self.post(path, {**payload, "role": head})
                self.assertEqual(created.status_code, 201, created.content)
                school = School.objects.get(pk=created.json()["id"])
                self.assertEqual(school.members.get().function_codes, [head])
        mixed = self.client.get(path, {"school_type": "lycee_general", "cycle": ["college", "lycee_general"]}).json()
        self.assertTrue({"principal", "proviseur"} <= {r["code"] for r in mixed["roles"]})

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
        from .academic_models import AcademicCycle, AcademicLevel, AcademicClass
        cycle = AcademicCycle.objects.get(school=school, code="prescolaire")
        self.assertEqual(list(AcademicLevel.objects.filter(cycle=cycle).order_by("order")
                              .values_list("code", flat=True)), ["creche", "ps", "ms", "gs"])
        self.assertFalse(AcademicClass.objects.filter(school=school).exists())

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

    def test_secondary_profiles_provision_distinct_roles_and_functions(self):
        cases = (
            ("college", ["college"], "principal", "directeur_etudes", "surveillant_general"),
            ("lycee_general", ["college", "lycee_general"], "proviseur", "censeur_pedagogique", "censeur_vie_scolaire"),
            ("lycee_technique", ["lycee_technique"], "proviseur", "directeur_etudes", "censeur_vie_scolaire"),
        )
        for kind, cycles, direction, studies, life in cases:
            with self.subTest(profile=kind):
                result = self.post("/api/v1/platform/schools", {
                    **self.payload, "school_type": kind, "education_cycles": cycles,
                    "username": f"direction-{kind}",
                })
                self.assertEqual(result.status_code, 201, result.content)
                school = School.objects.get(pk=result.json()["id"])
                self.assertEqual(school.members.get().function_codes, [direction])
                detail = self.client.get(f"/api/v1/platform/schools/{school.pk}/detail").json()
                roles = {role["code"]: role for role in detail["roles"]}
                functions = {position["code"]: position for position in detail["functions"]}
                self.assertEqual(roles["etudes"]["suggested_function"], studies)
                self.assertEqual(roles["vie_scolaire"]["suggested_function"], life)
                self.assertEqual("chef_travaux" in roles, kind == "lycee_technique")
                self.assertEqual("chef_travaux" in functions, kind == "lycee_technique")
                self.assertEqual("censeur_principal" in roles, kind != "college")
                self.assertIn("surveillant_general_adjoint", functions)
                self.assertNotIn("instituteur", functions)
                if kind == "lycee_general":
                    self.assertEqual(functions["principal"]["allowed_cycles"], ["college"])
                    self.assertEqual(functions["censeur_vie_scolaire"]["allowed_cycles"], ["lycee_general"])
                for code in {"etudes", "vie_scolaire", "surveillance"}:
                    self.assertTrue(all(not perm.startswith("school.finance.")
                                        for perm in school.roles.get(code=code).permissions))
                self.assertNotIn("school.attendance.read", school.roles.get(code="surveillance").permissions)

    def test_legacy_school_can_be_classified_with_audit(self):
        org = Organization.objects.create(name="Groupe existant")
        school = School.objects.create(organization=org, name="Lycée existant")
        self.assertEqual(school.school_type, "non_classe")
        custom = SchoolRole.objects.create(school=school, code="etudes", label="Coordination", permissions=["school.view"])
        SchoolRole.objects.create(school=school, code="direction", label="Direction du primaire", permissions=["school.view"])
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
        self.assertTrue(school.roles.filter(code="vie_scolaire").exists())
        roles = {r["code"]: r["label"] for r in saved.json()["roles"]}
        self.assertEqual(roles["direction"], "Proviseur / Proviseure du lycée")
        self.assertIn("proprietaire", roles)
        custom.refresh_from_db()
        self.assertEqual((custom.label, custom.permissions), ("Coordination", ["school.view"]))
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
