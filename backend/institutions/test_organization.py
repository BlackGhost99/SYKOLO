"""Recette des organigrammes : postes compatibles, multi-fonctions et isolation."""
import json
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .models import Organization, School, SchoolMember, SchoolRole, SchoolAppointment
from .services import ROLE_TEMPLATES, has_permission
from .staff_models import StaffRecord


class OrganisationSchoolTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="dir-postes", password="Safe-postes-2026!")
        self.secretary = User.objects.create_user(username="secretariat-postes", password="Safe-postes-2026!")
        self.teacher = User.objects.create_user(username="prof-postes", password="Safe-postes-2026!")
        self.stranger = User.objects.create_user(username="etranger-postes", password="Safe-postes-2026!")
        org = Organization.objects.create(name="Groupe postes")
        self.school = School.objects.create(
            organization=org, name="Lycée d'essai", school_type="lycee_general",
            education_cycles=["college", "lycee_general"],
        )
        self.other = School.objects.create(
            organization=org, name="Primaire d'essai", school_type="primaire",
            education_cycles=["primaire"],
        )
        for school in (self.school, self.other):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(
                    school=school, code=code, label=label, permissions=permissions,
                )
        for user, code in (
            (self.director, "direction"), (self.secretary, "secretariat"),
            (self.teacher, "enseignant"),
        ):
            SchoolMember.objects.create(
                school=self.school, user=user,
                role=SchoolRole.objects.get(school=self.school, code=code),
            )
        self.record = StaffRecord.objects.create(
            school=self.school, account=self.teacher, staff_code="PROF-1",
            first_name="Aline", last_name="Mba", position="Enseignante",
        )
        self.unlinked = StaffRecord.objects.create(
            school=self.school, staff_code="ADM-2",
            first_name="Thomas", last_name="Ondo", position="Administration",
        )
        self.foreign = StaffRecord.objects.create(
            school=self.other, staff_code="ECOLE-3",
            first_name="Fatou", last_name="Essono", position="Enseignante",
        )
        self.client = Client(enforce_csrf_checks=True)
        self.base = "/api/v1/schools/" + str(self.school.id) + "/organization/"
        self.login(self.director)

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, url, values, method="post", csrf=True):
        options = {"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}
        return getattr(self.client, method)(
            url, json.dumps(values), content_type="application/json", **options,
        )

    def nominee(self, code="censeur_pedagogique", cycle="lycee_general", staff=None):
        return {
            "staff": str(staff or self.record.pk),
            "function_code": code,
            "cycle_code": cycle,
        }

    def test_catalogue_depends_on_active_cycles_and_type(self):
        result = self.client.get(self.base + "positions")
        self.assertEqual(result.status_code, 200)
        rows = {p["code"]: p for p in result.json()["positions"]}
        self.assertIn("principal", rows)
        self.assertIn("proviseur", rows)
        self.assertIn("censeur_pedagogique", rows)
        self.assertEqual(rows["principal"]["allowed_cycles"], ["college"])
        self.assertEqual(rows["censeur_pedagogique"]["allowed_cycles"], ["lycee_general"])
        self.assertNotIn("directeur_primaire", rows)
        school = School.objects.get(pk=self.other.pk)
        from .school_functions import positions_for_school
        other = {p["code"] for p in positions_for_school(school)}
        self.assertIn("directeur_primaire", other)
        self.assertNotIn("censeur_pedagogique", other)
        self.assertNotIn("principal", other)
        self.assertNotIn("proviseur", other)

    def test_two_functions_for_same_staff_but_no_implicit_permissions(self):
        first = self.post(self.base+"appointments", self.nominee())
        self.assertEqual(first.status_code, 201, first.content)
        second = self.post(self.base+"appointments", self.nominee("professeur_principal", "college"))
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(SchoolAppointment.objects.filter(staff=self.record).count(), 2)
        self.assertFalse(has_permission(self.teacher, self.school, "school.organization.manage"))
        self.assertFalse(has_permission(self.teacher, self.school, "school.finance.read"))
        self.login(self.teacher)
        mine = self.client.get(self.base+"my-appointments")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(len(mine.json()["appointments"]), 2)
        self.assertEqual(self.client.get(self.base+"appointments").status_code, 403)
        self.assertEqual(self.post(self.base+"appointments", self.nominee()).status_code, 403)

    def test_nomination_requires_permission_and_same_school(self):
        self.login(self.secretary)
        self.assertEqual(self.client.get(self.base+"positions").status_code, 200)
        self.assertEqual(self.client.get(self.base+"appointments").status_code, 200)
        self.assertEqual(self.post(self.base+"appointments", self.nominee()).status_code, 403)
        self.login(self.director)
        self.assertEqual(self.post(self.base+"appointments", self.nominee(staff=self.foreign.pk)).status_code, 422)
        self.assertEqual(self.post(self.base+"appointments", self.nominee("principal", "lycee_general")).status_code, 422)
        self.assertEqual(self.post(self.base+"appointments", self.nominee("censeur_pedagogique", "primaire")).status_code, 422)
        self.assertEqual(self.post(self.base+"appointments", self.nominee("secretaire", "college")).status_code, 422)
        self.assertEqual(SchoolAppointment.objects.count(), 0)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+"appointments").status_code, 404)
        self.assertEqual(self.client.get(self.base+"my-appointments").status_code, 404)

    def test_double_creation_rejected_and_revision_used_for_revocation(self):
        first = self.post(self.base+"appointments", self.nominee())
        self.assertEqual(first.status_code, 201, first.content)
        uid = first.json()["id"]
        self.assertEqual(self.post(self.base+"appointments", self.nominee()).status_code, 409)
        patch = self.base+"appointments/"+uid
        self.assertEqual(self.post(patch, {"revision":100, "active":False}, "patch").status_code, 409)
        disabled = self.post(patch, {"revision":1, "active":False}, "patch")
        self.assertEqual(disabled.status_code, 200, disabled.content)
        self.assertFalse(disabled.json()["effective"])
        self.assertEqual(disabled.json()["revision"], 2)
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base+"my-appointments").json()["appointments"], [])
        self.login(self.director)
        enabled = self.post(patch, {"revision":2, "active":True}, "patch")
        self.assertEqual(enabled.status_code, 200, enabled.content)
        self.assertTrue(enabled.json()["effective"])

    def test_dates_and_unlinked_staff(self):
        future=(date.today()+timedelta(days=4)).isoformat()
        first = self.post(self.base+"appointments", {
            **self.nominee("secretaire", "", self.unlinked.pk),
            "starts_on":future, "ends_on":None,
        })
        self.assertEqual(first.status_code, 201, first.content)
        self.assertFalse(first.json()["effective"])
        self.assertFalse(first.json()["has_account"])
        self.assertEqual(self.post(self.base+"appointments", {
            **self.nominee(),
            "starts_on":"2027-09-01", "ends_on":"2027-01-01",
        }).status_code,422)
        self.assertEqual(self.post(self.base+"appointments", {
            **self.nominee(), "starts_on":"demain",
        }).status_code,422)

    def test_reclassification_keeps_nomination_but_makes_it_ineffective(self):
        created = self.post(self.base+"appointments", self.nominee())
        self.assertEqual(created.status_code, 201, created.content)
        self.school.school_type = "primaire"
        self.school.education_cycles = ["primaire"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        saved = SchoolAppointment.objects.get(pk=created.json()["id"])
        self.assertFalse(saved.is_effective)
        self.assertEqual(SchoolAppointment.objects.filter(staff=self.record).count(), 1)
        self.login(self.teacher)
        self.assertEqual(self.client.get(self.base+"my-appointments").json()["appointments"], [])

    def test_no_forced_classification_or_cross_role_access(self):
        self.school.school_type="non_classe"
        self.school.education_cycles=[]
        self.school.save(update_fields=["school_type", "education_cycles"])
        catalogue=self.client.get(self.base+"positions").json()["positions"]
        self.assertEqual(catalogue,[])
        self.assertEqual(self.post(self.base+"appointments",self.nominee()).status_code,422)
        self.assertEqual(SchoolAppointment.objects.count(),0)

    def test_link_account_to_staff_after_appointment(self):
        created = self.post(
            self.base+"appointments",
            self.nominee("secretaire", "", self.unlinked.pk)
        )
        self.assertEqual(created.status_code, 201, created.content)
        staff_url = "/api/v1/schools/"+str(self.school.pk)+"/staff/"+str(self.unlinked.pk)
        denied = self.post(staff_url, {
            "revision": 1, "username": "etranger-postes"
        }, "patch")
        self.assertEqual(denied.status_code, 422)
        linked = self.post(staff_url, {
            "revision": 1, "username": "secretariat-postes"
        }, "patch")
        self.assertEqual(linked.status_code, 200, linked.content)
        self.assertEqual(linked.json()["account_id"], str(self.secretary.pk))
        self.login(self.secretary)
        mine = self.client.get(self.base+"my-appointments")
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json()["appointments"][0]["function_code"], "secretaire")

    def test_csrf_protection_and_no_extra_json_fields(self):
        self.assertEqual(self.post(self.base+"appointments",self.nominee(),csrf=False).status_code,403)
        malicious={**self.nominee(),"permissions":["school.finance.receive"]}
        self.assertEqual(self.post(self.base+"appointments",malicious).status_code,422)
        self.client.logout()
        self.assertEqual(self.client.get(self.base+"appointments").status_code,401)
