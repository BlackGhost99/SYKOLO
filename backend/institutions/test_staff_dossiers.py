"""Recette des dossiers professionnels du personnel sans divulgation des données RH."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .models import Organization, OrganizationMember, School, SchoolAudit, SchoolMember, SchoolRole
from .organization_models import SchoolAppointment
from .services import ROLE_TEMPLATES
from .staff_models import StaffAssignment, StaffProfessionalDossier, StaffRecord


class StaffProfessionalDossierTests(TestCase):
    password = "YEM-staff-dossier-2026-secure!"

    def setUp(self):
        User = get_user_model()
        self.org = Organization.objects.create(name="Groupe scolaire test dossiers")
        self.school = School.objects.create(
            organization=self.org, name="Collège test dossiers",
            school_type="college", education_cycles=["college"],
        )
        self.other = School.objects.create(
            organization=self.org, name="Collège étranger",
            school_type="college", education_cycles=["college"],
        )
        for school in (self.school, self.other):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(
                    school=school, code=code, label=label, permissions=permissions,
                )
        self.users = {}
        roles = {
            "direction": ("direction", None),
            "secretariat": ("secretariat", None),
            "enseignant": ("enseignant", None),
            "annuaire": ("annuaire", ["school.view", "school.staff.read"]),
            "rh_lecture": ("rh_lecture", ["school.view", "school.staff.dossier.read"]),
            "rh_edition": ("rh_edition", ["school.view", "school.staff.dossier.read",
                                          "school.staff.dossier.manage"]),
            "edit_sans_lecture": ("edit_sans_lecture", ["school.view", "school.staff.dossier.manage"]),
            "scoped": ("direction", None),
        }
        for key,(code,permissions) in roles.items():
            user = User.objects.create_user(
                username="staff-profile-"+key, password=self.password,
            )
            if permissions is None:
                role = self.school.roles.get(code=code)
            else:
                role = SchoolRole.objects.create(
                    school=self.school, code=code, label=key, permissions=permissions,
                )
            self.users[key] = user
            SchoolMember.objects.create(
                school=self.school, user=user, role=role,
            )
        self.founder = User.objects.create_user(
            username="staff-founder", password=self.password,
        )
        OrganizationMember.objects.create(
            organization=self.org, user=self.founder, role="founder",
        )
        self.stranger = User.objects.create_user(
            username="staff-outsider", password=self.password,
        )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026-2027",
            start_date=date(2026,9,1), end_date=date(2027,7,31),
        )
        self.cycle = AcademicCycle.objects.create(
            school=self.school, code="college", name="Collège",
        )
        self.level = AcademicLevel.objects.create(
            school=self.school, cycle=self.cycle, code="6e", name="Sixième",
        )
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level,
            code="6e-a", name="Sixième A",
        )
        self.record = StaffRecord.objects.create(
            school=self.school, account=self.users["enseignant"],
            staff_code="ENS-024", first_name="Alice", last_name="Essono",
            position="Professeure de mathématiques",
            hired_on=date(2025,9,1),
        )
        self.unlinked = StaffRecord.objects.create(
            school=self.school, staff_code="ADM-017",
            first_name="Jean", last_name="Obame", position="Secrétaire",
        )
        SchoolAppointment.objects.create(
            school=self.school, staff=self.record, function_code="enseignant",
            cycle_code="college", starts_on=date(2025,9,1),
        )
        StaffAssignment.objects.create(
            school=self.school, staff=self.record, year=self.year,
            classroom=self.classroom, duty="enseignant",
        )
        self.base = "/api/v1/schools/"+str(self.school.pk)+"/"
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.users["direction"])

    def login(self,user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def patch(self,route,data):
        return self.client.patch(
            self.base+route,json.dumps(data),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf,
        )

    @property
    def route(self):
        return "staff/"+str(self.record.pk)+"/dossier"

    def test_direction_can_read_and_update_existing_professional_dossier(self):
        response = self.client.get(self.base+self.route)
        self.assertEqual(response.status_code, 200, response.content)
        dossier = response.json()
        self.assertEqual(dossier["staff"]["staff_code"],"ENS-024")
        self.assertTrue(dossier["staff"]["has_account"])
        self.assertTrue(dossier["can_edit"])
        self.assertEqual(dossier["professional"]["revision"],1)
        self.assertEqual(dossier["functions"][0]["label"],"Enseignant")
        self.assertEqual(dossier["class_assignments"][0]["classroom"],"Sixième A")
        self.assertNotIn("password",str(dossier).lower())
        self.assertNotIn("salary",str(dossier).lower())
        update = self.patch(self.route,{
            "revision":1, "qualification":"Licence professionnelle",
            "specialty":"Mathématiques", "employment_status":"Vacataire",
            "workload":"12 h/semaine", "professional_email":"pro@example.test",
            "professional_phone":"+241 077 88 99 00",
        })
        self.assertEqual(update.status_code,200,update.content)
        self.assertEqual(update.json()["professional"]["revision"],2)
        self.assertEqual(update.json()["professional"]["qualification"],"Licence professionnelle")
        self.assertEqual(StaffProfessionalDossier.objects.count(),1)
        audit = SchoolAudit.objects.get(event="staff_dossier_updated")
        self.assertEqual(audit.details["fields"],[
            "employment_status","professional_email","professional_phone",
            "qualification","specialty","workload",
        ])
        self.assertNotIn("Licence professionnelle",str(audit.details))
        wrong=self.patch(self.route,{"revision":1,"specialty":"Histoire"})
        self.assertEqual(wrong.status_code,409)
        self.assertEqual(StaffProfessionalDossier.objects.get(staff=self.record).specialty,"Mathématiques")

    def test_secretariat_can_read_but_not_modify(self):
        self.login(self.users["secretariat"])
        result=self.client.get(self.base+self.route)
        self.assertEqual(result.status_code,200,result.content)
        self.assertFalse(result.json()["can_edit"])
        self.assertEqual(self.patch(self.route,{"revision":1,"specialty":"Français"}).status_code,403)

    def test_only_explicit_dossier_right_and_separation_of_read_write(self):
        self.login(self.users["annuaire"])
        self.assertEqual(self.client.get(self.base+"staff").status_code,200)
        self.assertEqual(self.client.get(self.base+self.route).status_code,403)
        self.login(self.users["edit_sans_lecture"])
        self.assertEqual(self.client.get(self.base+self.route).status_code,403)
        self.assertEqual(self.patch(self.route,{"revision":1,"specialty":"Sciences"}).status_code,403)
        self.login(self.users["rh_lecture"])
        self.assertEqual(self.client.get(self.base+"staff").status_code,200)
        self.assertEqual(self.client.get(self.base+self.route).status_code,200)
        self.assertEqual(self.patch(self.route,{"revision":1,"specialty":"Français"}).status_code,403)
        self.login(self.users["rh_edition"])
        self.assertEqual(self.patch(self.route,{"revision":1,"specialty":"Histoire"}).status_code,200)

    def test_employee_sees_only_own_file_even_without_read_permission(self):
        self.login(self.users["enseignant"])
        self.assertEqual(self.client.get(self.base+"staff").status_code,403)
        self.assertEqual(self.client.get(self.base+self.route).status_code,403)
        own=self.client.get(self.base+"staff/me/dossier")
        self.assertEqual(own.status_code,200,own.content)
        self.assertTrue(own.json()["is_own_dossier"])
        self.assertFalse(own.json()["can_edit"])
        self.assertEqual(own.json()["staff"]["staff_code"],"ENS-024")
        self.assertEqual(self.patch("staff/me/dossier",{}).status_code,405)
        self.assertEqual(self.client.get(
            "/api/v1/schools/"+str(self.other.pk)+"/staff/me/dossier",
        ).status_code,404)

    def test_staff_without_login_is_readable_to_authorized_manager(self):
        result=self.client.get(
            self.base+"staff/"+str(self.unlinked.pk)+"/dossier",
        )
        self.assertEqual(result.status_code,200)
        self.assertFalse(result.json()["staff"]["has_account"])
        self.assertEqual(result.json()["functions"],[])
        self.assertEqual(result.json()["class_assignments"],[])

    def test_denied_fields_school_isolation_and_revocation(self):
        self.assertEqual(self.patch(self.route,{
            "revision":1, "salary":"1000000",
        }).status_code,422)
        self.assertEqual(self.patch(self.route,{
            "revision":1, "professional_email":"not-an-email",
        }).status_code,422)
        self.assertEqual(self.patch(self.route,{
            "revision":1, "professional_phone":"a bad number",
        }).status_code,422)
        self.assertEqual(StaffProfessionalDossier.objects.count(),0)
        self.assertEqual(self.client.get(
            "/api/v1/schools/"+str(self.other.pk)+"/staff/"+str(self.record.pk)+"/dossier",
        ).status_code,404)
        self.login(self.founder)
        self.assertEqual(self.client.get(self.base+self.route).status_code,403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base+self.route).status_code,404)
        self.login(self.users["direction"])
        SchoolMember.objects.filter(
            school=self.school,user=self.users["direction"],
        ).update(active=False)
        self.assertEqual(self.client.get(self.base+self.route).status_code,404)

    def test_restricted_cycle_account_cannot_browse_colleagues_but_can_self_read(self):
        self.record.account=None
        self.record.save(update_fields=["account"])
        other_record=StaffRecord.objects.create(
            school=self.school,account=self.users["scoped"],
            staff_code="SCOPED", first_name="Test",last_name="Scope",
            position="Enseignant",
        )
        member=SchoolMember.objects.get(
            school=self.school,user=self.users["scoped"],
        )
        member.access_cycle_ids=[str(self.cycle.pk)]
        member.save(update_fields=["access_cycle_ids"])
        StaffAssignment.objects.create(
            school=self.school, staff=other_record, year=self.year,
            classroom=self.classroom, duty="enseignant",
        )
        self.login(self.users["scoped"])
        self.assertEqual(self.client.get(self.base+self.route).status_code,403)
        own=self.client.get(self.base+"staff/me/dossier")
        self.assertEqual(own.status_code,200,own.content)
        self.assertEqual(own.json()["class_assignments"][0]["classroom"],"Sixième A")
