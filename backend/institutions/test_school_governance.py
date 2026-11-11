"""Régression gouvernance public / privé gabonaise sans escalade de permissions."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole, PlatformAudit
from .school_functions import positions_for_school, validate_position
from .school_governance import governance_profile, validate_governance_mode
from .services import role_templates_for, OWNER_ROLE_CODE, FINANCE_MUTATION_PERMISSIONS


class GovernanceProfilesTests(TestCase):
    password = "Governance-YEM-2026-Test!92"

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="admin-governance", email="admin-governance@example.test",
            password=self.password
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session["mfa_verified"] = True
        session.save()

    def post(self, payload, path="/api/v1/platform/schools"):
        return self.client.post(path, json.dumps(payload), content_type="application/json")

    def payload(self, mode, role="principal"):
        return {
            "organization_name": "Organisation " + mode,
            "school_name": "Collège " + mode,
            "school_type": "college", "education_cycles": ["college"],
            "governance_mode": mode,
            "username": "chef-" + mode, "email": "chef-"+mode+"@example.test",
            "first_name": "Jeanne", "last_name": "Test",
            "password": self.password, "role": role,
        }

    def test_default_preserves_legacy_private_laique(self):
        school = School.objects.create(organization=Organization.objects.create(name="Ancienne école"),
                                       name="Établissement ancien")
        self.assertEqual(school.governance_mode, "prive_laique")
        self.assertEqual(governance_profile(school)["sector"], "prive")
        self.assertIn(OWNER_ROLE_CODE, {code for code, *_ in role_templates_for(school)})

    def test_creation_public_excludes_owner_and_sensitive_finance(self):
        options = self.client.get("/api/v1/platform/schools",{
            "school_type":"college", "cycle":["college"], "governance_mode":"public"
        })
        self.assertEqual(options.status_code, 200, options.content)
        choices={r["code"] for r in options.json()["roles"]}
        self.assertNotIn("proprietaire",choices)
        self.assertNotIn("tarification",choices)
        self.assertIn("tutelle_consultation",choices)
        self.assertIn("principal",choices)
        self.assertEqual(options.json()["default_role"],"principal")
        invalid=self.post(self.payload("public","proprietaire"))
        self.assertEqual(invalid.status_code,422)
        response=self.post(self.payload("public"))
        self.assertEqual(response.status_code,201,response.content)
        school=School.objects.get(pk=response.json()["id"])
        self.assertEqual(school.governance_mode,"public")
        self.assertFalse(school.roles.filter(code="proprietaire").exists())
        self.assertFalse(OrganizationMember.objects.filter(organization=school.organization,role="founder").exists())
        self.assertTrue(school.roles.filter(code="tutelle_consultation").exists())
        principal=school.roles.get(code="principal")
        self.assertFalse(set(principal.permissions) & FINANCE_MUTATION_PERMISSIONS)
        for role in school.roles.all():
            self.assertFalse(set(role.permissions) & FINANCE_MUTATION_PERMISSIONS)
        detail=self.client.get(f"/api/v1/platform/schools/{school.pk}/detail")
        self.assertEqual(detail.json()["school"]["governance_mode"],"public")
        self.assertEqual(detail.json()["school"]["governance"]["sector"],"public")

    def test_public_cannot_reuse_private_founder_organization(self):
        founder=get_user_model().objects.create_user("fondateur-existant",password=self.password)
        org=Organization.objects.create(name="Groupe privé existant")
        OrganizationMember.objects.create(organization=org,user=founder,role="founder")
        result=self.post({
            **self.payload("public"),"organization_id":str(org.pk),"organization_name":""
        })
        self.assertEqual(result.status_code,422)
        self.assertFalse(School.objects.exists())

    def test_private_laique_and_confessionnel_are_distinct(self):
        secular=self.post(self.payload("prive_laique"))
        self.assertEqual(secular.status_code,201,secular.content)
        secular_school=School.objects.get(pk=secular.json()["id"])
        self.assertIn("responsable_administratif_prive",{
            p["code"] for p in positions_for_school(secular_school)
        })
        self.assertNotIn("responsable_pastorale",{
            p["code"] for p in positions_for_school(secular_school)
        })
        conf=self.post(self.payload("prive_confessionnel"))
        self.assertEqual(conf.status_code,201,conf.content)
        school=School.objects.get(pk=conf.json()["id"])
        self.assertIn("proprietaire",{r.code for r in school.roles.all()})
        self.assertTrue(school.roles.filter(code="referent_confessionnel").exists())
        functions={p["code"] for p in positions_for_school(school)}
        self.assertIn("responsable_pastorale",functions)
        self.assertNotIn("referent_relation_tutelle",functions)
        self.assertEqual(school.governance_mode,"prive_confessionnel")
        self.assertEqual(school.roles.get(code="referent_confessionnel").permissions,["school.view"])

    def test_technical_functions_and_concertation(self):
        school=School.objects.create(organization=Organization.objects.create(name="Lycée technique"),
            name="Technique",school_type="lycee_technique",
            education_cycles=["lycee_technique"],governance_mode="public")
        codes={p["code"] for p in positions_for_school(school)}
        self.assertTrue({
            "directeur_etudes_formation_initiale","directeur_etudes_vie_scolaire",
            "chef_departement","responsable_stages","chef_travaux",
        } <= codes)
        org=governance_profile(school)["organs"]
        self.assertIn("Conseil de perfectionnement",org)
        ordinary=School.objects.create(organization=school.organization,name="Collège",
            school_type="college",education_cycles=["college"],governance_mode="public")
        self.assertNotIn("chef_travaux",{p["code"] for p in positions_for_school(ordinary)})
        self.assertNotIn("responsable_pastorale",{p["code"] for p in positions_for_school(ordinary)})

    def test_private_subtype_change_is_audited_not_overwriting_roles(self):
        created=self.post(self.payload("prive_laique"))
        school=School.objects.get(pk=created.json()["id"])
        role=SchoolRole.objects.create(school=school,code="custom_role",
            label="Coordination personnalisée",permissions=["school.view"])
        before=(role.label,role.permissions)
        url=f"/api/v1/platform/schools/{school.pk}/action"
        changed=self.post({"action":"profile","school_type":"college",
            "education_cycles":["college"],"governance_mode":"prive_confessionnel",
            "reason":"Changement officiel vers gestion confessionnelle"},url)
        self.assertEqual(changed.status_code,200,changed.content)
        school.refresh_from_db()
        self.assertEqual(school.governance_mode,"prive_confessionnel")
        self.assertTrue(school.roles.filter(code="referent_confessionnel").exists())
        role.refresh_from_db()
        self.assertEqual((role.label,role.permissions),before)
        self.assertTrue(PlatformAudit.objects.filter(school=school,
            event="school_profile_updated").exists())
        forbidden=self.post({"action":"profile","school_type":"college",
            "education_cycles":["college"],"governance_mode":"public",
            "reason":"Tentative de conversion inappropriée"},url)
        self.assertEqual(forbidden.status_code,422)

    def test_invalid_mode_rejected(self):
        self.assertEqual(self.post(self.payload("public-inconnu")).status_code,422)
        with self.assertRaises(ValueError):
            validate_governance_mode("public-inconnu")
