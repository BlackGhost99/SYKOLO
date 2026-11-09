"""Parcours simplifiés : fiche de renseignement, inscriptions par classe, classes rapides, facturation."""
import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .finance_models import FeeSchedule, FeeCharge, FeePayment
from .models import Organization, School, SchoolRole, SchoolMember, SchoolAdminPolicy
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian, Enrollment


class RegistrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username="dir-reg", password="Strong director password 2026!")
        self.secretary = User.objects.create_user(username="sec-reg", password="Strong secretary password 2026!")
        self.teacher = User.objects.create_user(username="tea-reg", password="Strong teacher password 2026!")
        self.biller = User.objects.create_user(username="billing-reg", password="Strong billing password 2026!")
        org = Organization.objects.create(name="Groupe inscriptions")
        self.school = School.objects.create(organization=org, name="École A")
        self.other = School.objects.create(organization=org, name="École B")
        for school in (self.school, self.other):
            for code, name, perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=name, permissions=perms)
        for user, role in ((self.director, "direction"), (self.secretary, "secretariat"), (self.teacher, "enseignant")):
            SchoolMember.objects.create(school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code=role))
        # Fee assessment is authorized for a tariff manager, not for direction by default.
        billing_member = SchoolMember.objects.create(
            school=self.school, user=self.biller,
            role=SchoolRole.objects.get(school=self.school, code="secretariat"),
        )
        billing_member.additional_roles.add(SchoolRole.objects.get(school=self.school, code="tarification"))
        today = timezone.localdate()
        self.year = AcademicYear.objects.create(school=self.school, code="y", name="2026-2027",
                                                start_date=today - timedelta(days=30), end_date=today + timedelta(days=300))
        cycle = AcademicCycle.objects.create(school=self.school, code="c", name="Collège")
        self.level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        self.c6a = AcademicClass.objects.create(school=self.school, year=self.year, level=self.level, code="6a", name="6e A", capacity=2)
        self.global_fee = FeeSchedule.objects.create(school=self.school, year=self.year, code="ins", label="Inscription",
                                                     amount=Decimal("50000"), currency="XAF")
        self.class_fee = FeeSchedule.objects.create(school=self.school, year=self.year, classroom=self.c6a, scope_key=str(self.c6a.pk),
                                                    code="scol", label="Scolarité 6e", amount=Decimal("150000"), currency="XAF")
        self.base = f"/api/v1/schools/{self.school.pk}/"

    def post(self, path, body):
        return self.client.post(self.base + path, json.dumps(body), content_type="application/json")

    def register_body(self, **extra):
        body = {
            "student": {"first_name": "Aaron", "last_name": "NZE", "date_of_birth": "2015-03-02", "gender": "M",
                        "place_of_birth": "Libreville", "nationality": "Gabonaise", "address": "Quartier Louis",
                        "previous_school": "École Montfort"},
            "guardians": [{"full_name": "NZE Sylvie", "relationship": "Mère", "phone": "+241 77 43 21 08",
                           "profession": "Infirmière", "address": "Quartier Louis"}],
            "enrollment": {"classroom": str(self.c6a.pk)},
        }
        body.update(extra)
        return body

    def test_manual_transfer_is_bound_to_destination_and_keeps_identity(self):
        from .models import SchoolMember, SchoolRole

        self.client.force_login(self.director)
        original = Student.objects.create(school=self.school, student_code="LOCAL-1",
            first_name="Aaron", last_name="NZE", date_of_birth="2015-03-02")
        SchoolMember.objects.create(school=self.other, user=self.director,
            role=SchoolRole.objects.get(school=self.other, code="direction"))
        source = f"/api/v1/schools/{self.school.pk}/students/{original.pk}/transfer"
        response = self.client.post(source, {"destination": str(self.other.pk)}, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        payload = self.register_body(enrollment=None, transfer_code=response.json()["transfer_code"])
        self.assertEqual(self.post("students/register", payload).status_code, 422)
        target = f"/api/v1/schools/{self.other.pk}/students/register"
        response = self.client.post(target, payload, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["student"]["matricule_yem"], original.matricule_yem)
        self.assertEqual(self.client.post(target, payload, content_type="application/json").status_code, 409)

    def test_full_registration_creates_student_guardian_enrollment_and_fees(self):
        self.client.force_login(self.biller)
        r = self.post("students/register", self.register_body())
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertRegex(d["student"]["matricule_yem"], r"^YEM-[0-9A-F]{32}$")
        self.assertEqual(d["student"]["place_of_birth"], "Libreville")
        self.assertTrue(d["guardians"][0]["is_primary"])
        self.assertEqual(d["guardians"][0]["profession"], "Infirmière")
        self.assertEqual(d["enrollment"]["classroom"], str(self.c6a.pk))
        self.assertEqual(d["charges_created"], 2)
        self.assertEqual(FeeCharge.objects.filter(enrollment_id=d["enrollment"]["id"]).count(), 2)
        # Matricules successifs uniques.
        r2 = self.post("students/register", self.register_body(student={"first_name": "Léa", "last_name": "NZE", "date_of_birth": "2016-01-01"}, enrollment=None))
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertNotEqual(r2.json()["student"]["student_code"], d["student"]["student_code"])

    def test_secretary_registers_without_fees_and_failure_rolls_back(self):
        self.client.force_login(self.secretary)
        r = self.post("students/register", self.register_body())
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()["fees_skipped"])
        self.assertEqual(FeeCharge.objects.count(), 0)
        # Mauvais email du responsable : rien n'est créé.
        before = Student.objects.count()
        bad = self.register_body(guardians=[{"full_name": "X", "phone": "1", "email": "pas-un-email"}])
        self.assertEqual(self.post("students/register", bad).status_code, 422)
        self.assertEqual(Student.objects.count(), before)

    def test_capacity_and_permissions(self):
        self.client.force_login(self.director)
        for name in ("A", "B"):
            self.assertEqual(self.post("students/register", self.register_body(student={"first_name": name, "last_name": "X", "date_of_birth": "2015-01-01"})).status_code, 201)
        full = self.post("students/register", self.register_body(student={"first_name": "C", "last_name": "X", "date_of_birth": "2015-01-01"}))
        self.assertEqual(full.status_code, 422)
        self.assertIn("Capacité", full.json()["error"])
        self.client.force_login(self.teacher)
        self.assertEqual(self.post("students/register", self.register_body()).status_code, 403)
        other = f"/api/v1/schools/{self.other.pk}/students/register"
        self.client.force_login(self.director)
        self.assertEqual(self.client.post(other, json.dumps(self.register_body()), content_type="application/json").status_code, 404)

    def test_registration_respects_platform_student_limit(self):
        SchoolAdminPolicy.objects.create(school=self.school, max_students=0)
        self.client.force_login(self.secretary)
        response = self.post("students/register", self.register_body())
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 0)
        self.assertEqual(StudentGuardian.objects.filter(school=self.school).count(), 0)

    def test_quick_classes_creates_level_and_codes(self):
        self.client.force_login(self.director)
        r = self.post("academic/quick-classes", {"year": str(self.year.pk), "level_name": "CM1", "cycle_name": "Primaire",
                                                  "names": "CM1 A, CM1 B", "capacity": 35})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual([c["name"] for c in r.json()["classes"]], ["CM1 A", "CM1 B"])
        self.assertEqual(AcademicClass.objects.filter(school=self.school, level__name="CM1", capacity=35).count(), 2)
        dup = self.post("academic/quick-classes", {"year": str(self.year.pk), "level": str(self.level.pk), "names": ["6e a"]})
        self.assertEqual(dup.status_code, 409)
        self.client.force_login(self.secretary)
        self.assertEqual(self.post("academic/quick-classes", {"year": str(self.year.pk), "level": str(self.level.pk), "names": ["6e C"]}).status_code, 403)

    def test_preschool_standard_classes_are_idempotent_and_preserve_renames(self):
        from .preschool_classes import PRESCHOOL_DEFAULTS

        self.school.school_type = "maternelle"
        self.school.education_cycles = ["prescolaire"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        self.client.force_login(self.director)
        path = "academic/preschool-standard-classes"
        first = self.post(path, {"year": str(self.year.pk)})
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["created"], 4)
        self.assertEqual(len(PRESCHOOL_DEFAULTS), 4)
        self.assertEqual([c["name"] for c in first.json()["classes"]],
                         ["Crèche A", "Petite section A", "Moyenne section A", "Grande section A"])
        second = self.post(path, {"year": str(self.year.pk)})
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json()["created"], 0)
        room = AcademicClass.objects.get(school=self.school, year=self.year, code="presc-ps-a")
        renamed = self.client.patch(
            self.base + f"academic/classes/{room.pk}",
            json.dumps({"revision": room.revision, "name": "Petite section Les Papillons"}),
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200, renamed.content)
        third = self.post(path, {"year": str(self.year.pk)})
        self.assertEqual(third.json()["created"], 0)
        room.refresh_from_db()
        self.assertEqual(room.name, "Petite section Les Papillons")
        self.client.force_login(self.secretary)
        self.assertEqual(self.post(path, {"year": str(self.year.pk)}).status_code, 403)
        self.client.force_login(self.director)
        self.assertEqual(self.post(path, {"year": str(uuid.uuid4())}).status_code, 404)

    def test_new_preschool_year_automatically_provisions_four_classes(self):
        self.school.school_type = "maternelle"
        self.school.education_cycles = ["prescolaire"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        self.client.force_login(self.director)
        today = timezone.localdate()
        start = self.year.end_date + timedelta(days=1)
        end = start + timedelta(days=300)
        created = self.post("academic/years", {
            "code": "prochaine", "name": "Nouvelle année maternelle",
            "start_date": start.isoformat(), "end_date": end.isoformat(),
        })
        self.assertEqual(created.status_code, 201, created.content)
        year = AcademicYear.objects.get(pk=created.json()["id"])
        classes = AcademicClass.objects.filter(school=self.school, year=year)
        self.assertEqual(classes.count(), 4)
        self.assertEqual(set(classes.values_list("level__code", flat=True)),
                         {"creche", "ps", "ms", "gs"})
        self.assertEqual(Enrollment.objects.filter(school=self.school, year=year).count(), 0)

    def test_standard_classes_complete_primary_college_and_lycee_idempotently(self):
        from .school_profiles import CLASS_LEVELS
        self.school.school_type = "groupe_scolaire"
        self.school.education_cycles = ["primaire", "college", "lycee_general"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        self.client.force_login(self.director)
        path = "academic/standard-classes"
        first = self.post(path, {"year": str(self.year.pk)})
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["created"], 5 + 4 + 3)
        self.assertEqual(first.json()["cycles"], ["primaire", "college", "lycee_general"])
        self.assertEqual(
            set(AcademicLevel.objects.filter(school=self.school, cycle__code="primaire")
                .values_list("code", flat=True)),
            {code for code, _ in CLASS_LEVELS["primaire"]},
        )
        self.assertEqual(
            set(AcademicLevel.objects.filter(school=self.school, cycle__code="college")
                .values_list("code", flat=True)),
            {"6e", "5e", "4e", "3e"},
        )
        self.assertEqual(
            set(AcademicLevel.objects.filter(school=self.school, cycle__code="lycee_general")
                .values_list("code", flat=True)),
            {"seconde", "premiere", "terminale"},
        )
        new_rooms = AcademicClass.objects.filter(
            school=self.school, year=self.year, code__startswith="std-",
        )
        self.assertEqual(new_rooms.count(), 12)
        self.assertEqual(len({room.name.casefold() for room in new_rooms}), 12)
        self.assertEqual(self.post(path, {"year": str(self.year.pk)}).json()["created"], 0)
        to_rename = new_rooms.get(level__cycle__code="primaire", level__code="1re-annee")
        renamed = self.client.patch(
            self.base + f"academic/classes/{to_rename.pk}",
            json.dumps({"revision": to_rename.revision, "name": "Première année Les Étoiles"}),
            content_type="application/json",
        )
        self.assertEqual(renamed.status_code, 200, renamed.content)
        self.assertEqual(self.post(path, {"year": str(self.year.pk)}).json()["created"], 0)
        to_rename.refresh_from_db()
        self.assertEqual(to_rename.name, "Première année Les Étoiles")

    def test_standard_classes_respect_delegate_cycle_and_read_only_year(self):
        self.school.school_type = "groupe_scolaire"
        self.school.education_cycles = ["primaire", "college", "lycee_general"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        self.client.force_login(self.director)
        grant = self.post("delegations", {
            "user_id": str(self.secretary.pk), "permissions": ["school.classes.manage"],
            "class_cycle": "college", "reason": "Gestion temporaire des classes du collège",
        })
        self.assertEqual(grant.status_code, 201, grant.content)
        self.client.force_login(self.secretary)
        overview = self.client.get(self.base + "overview/classes")
        self.assertEqual(overview.status_code, 200, overview.content)
        options = overview.json()["standard_cycles_available"]
        self.assertEqual([cycle["code"] for cycle in options], ["college"])
        response = self.post("academic/standard-classes", {"year": str(self.year.pk)})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["created"], 4)
        self.assertEqual(response.json()["cycles"], ["college"])
        self.assertFalse(AcademicLevel.objects.filter(school=self.school, cycle__code="primaire").exists())
        self.assertFalse(AcademicLevel.objects.filter(school=self.school, cycle__code="lycee_general").exists())
        self.client.force_login(self.teacher)
        self.assertEqual(self.post("academic/standard-classes", {"year": str(self.year.pk)}).status_code, 403)
        self.client.force_login(self.director)
        self.year.active = False
        self.year.status = "closed"
        self.year.save(update_fields=["active", "status"])
        self.assertEqual(self.post("academic/standard-classes", {"year": str(self.year.pk)}).status_code, 409)

    def test_mixed_preschool_and_technical_school_avoids_class_name_collision(self):
        from .standard_classes import ensure_standard_levels
        self.school.school_type = "groupe_scolaire"
        self.school.education_cycles = ["prescolaire", "primaire", "college", "lycee_general", "lycee_technique"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        self.client.force_login(self.director)
        result = self.post("academic/standard-classes", {"year": str(self.year.pk)})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["created"], 19)
        names = [classroom["name"] for classroom in result.json()["classes"]]
        self.assertIn("Seconde A", names)
        self.assertIn("Seconde technique A", names)
        self.assertIn("Crèche A", names)
        self.assertIn("5e année A", names)
        self.assertEqual(len({name.casefold() for name in names}), 19)
        self.assertEqual(self.post("academic/standard-classes", {"year": str(self.year.pk)}).json()["created"], 0)
        self.assertEqual(self.post("academic/preschool-standard-classes", {"year": str(self.year.pk)}).json()["created"], 0)

    def test_clone_class_duplicates_structure_only_without_data(self):
        self.client.force_login(self.director)
        source = self.c6a
        student = Student.objects.create(school=self.school, first_name="Exemple", last_name="TEST")
        Enrollment.objects.create(
            school=self.school, student=student, year=self.year,
            classroom=source, enrolled_on=self.year.start_date,
        )
        cloned = self.post(f"academic/classes/{source.pk}/clone", {})
        self.assertEqual(cloned.status_code, 201, cloned.content)
        self.assertEqual(cloned.json()["name"], "6e B")
        copy = AcademicClass.objects.get(pk=cloned.json()["id"])
        self.assertEqual(copy.level_id, source.level_id)
        self.assertEqual(copy.year_id, source.year_id)
        self.assertEqual(copy.capacity, source.capacity)
        self.assertEqual(Enrollment.objects.filter(classroom=copy).count(), 0)
        self.assertEqual(FeeSchedule.objects.filter(classroom=copy).count(), 0)
        named = self.post(f"academic/classes/{source.pk}/clone", {"name": "6e Les Étoiles"})
        self.assertEqual(named.status_code, 201, named.content)
        self.assertEqual(self.post(f"academic/classes/{source.pk}/clone", {"name": "6e b"}).status_code, 409)
        self.client.force_login(self.secretary)
        self.assertEqual(self.post(f"academic/classes/{source.pk}/clone", {}).status_code, 403)
        self.client.force_login(self.director)
        foreign = f"/api/v1/schools/{self.other.pk}/academic/classes/{source.pk}/clone"
        self.assertEqual(self.client.post(foreign, "{}", content_type="application/json").status_code, 404)
        self.year.active = False
        self.year.status = "closed"
        self.year.save(update_fields=["active", "status"])
        self.assertEqual(self.post(f"academic/classes/{source.pk}/clone", {}).status_code, 409)

    def test_class_students_returns_only_active_enrollments_for_the_requested_class(self):
        c6b = AcademicClass.objects.create(school=self.school, year=self.year, level=self.level, code="6b", name="6e B")
        for name, classroom, active in (("Ada", self.c6a, True), ("Camille", self.c6a, False), ("David", c6b, True)):
            student = Student.objects.create(school=self.school, first_name=name, last_name="TEST")
            Enrollment.objects.create(school=self.school, student=student, year=self.year, classroom=classroom,
                                      enrolled_on=self.year.start_date, active=active)
        self.client.force_login(self.secretary)
        path = self.base + f"classes/{self.c6a.pk}/students"
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        ada = Student.objects.get(school=self.school, first_name="Ada")
        self.assertEqual(response.json(), {"students": [{"id": str(ada.pk), "first_name": "Ada", "last_name": "TEST",
                                                         "student_code": ada.student_code}]})
        self.assertEqual(self.client.get(self.base + f"classes/{uuid.uuid4()}/students").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.other.pk}/classes/{self.c6a.pk}/students").status_code, 404)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(path).status_code, 403)
        SchoolMember.objects.filter(school=self.school, user=self.secretary).update(access_cycle_ids=[str(self.level.cycle_id)])
        self.client.force_login(self.secretary)
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_class_presets_are_atomic_and_delegation_is_limited_to_one_cycle(self):
        self.school.school_type = "groupe_scolaire"
        self.school.education_cycles = ["college", "lycee_general"]
        self.school.save(update_fields=["school_type", "education_cycles"])
        self.client.force_login(self.director)
        grant = self.post("delegations", {
            "user_id": str(self.secretary.pk), "permissions": ["school.classes.manage"],
            "class_cycle": "college", "reason": "Préparation de la rentrée du collège",
        })
        self.assertEqual(grant.status_code, 201, grant.content)
        self.client.force_login(self.secretary)
        overview = self.client.get(self.base + "overview/classes").json()
        self.assertEqual(overview["class_management_cycles"], ["college"])
        self.assertFalse(overview["can_manage_academic"])
        self.assertNotIn("primaire:1re-annee", overview["class_level_options"])

        path = "academic/quick-classes"
        batch = {"year": str(self.year.pk), "preset": "college:5e", "names": ["5e B", "5e 13"]}
        self.assertEqual(self.post(path, {**batch, "names": ["5e B", "5e b"]}).status_code, 422)
        self.assertEqual(self.post(path, {**batch, "names": ["5e B", "6e A"]}).status_code, 409)
        self.assertFalse(AcademicLevel.objects.filter(school=self.school, code="5e").exists())
        self.assertEqual(self.post(path, {**batch, "preset": "lycee_general:seconde"}).status_code, 403)
        self.assertFalse(AcademicCycle.objects.filter(school=self.school, code="lycee_general").exists())
        created = self.post(path, batch)
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(self.post(path, batch).status_code, 409)
        rows = created.json()["classes"]

        def rename(class_id, name):
            return self.client.patch(
                self.base + f"academic/classes/{class_id}", {"revision": 1, "name": name},
                content_type="application/json",
            )
        self.assertEqual(rename(rows[0]["id"], "5e 13").status_code, 409)
        self.assertEqual(rename(rows[0]["id"], "5e Horizon").status_code, 200)
        self.assertEqual(rename(self.c6a.pk, "Autre cycle technique").status_code, 403)
        self.assertEqual(self.post("academic/years", {}).status_code, 403)
        self.assertEqual(self.post("academic/classes", {
            "year": str(self.year.pk), "level": str(self.level.pk), "code": "6b", "name": "6e B",
        }).status_code, 403)

        self.client.force_login(self.director)
        revoked = self.client.delete(
            self.base + "delegations/" + grant.json()["id"], {"reason": "Fin de la mission"},
            content_type="application/json",
        )
        self.assertEqual(revoked.status_code, 200, revoked.content)
        self.client.force_login(self.secretary)
        self.assertEqual(self.post(path, {**batch, "names": ["5e C"]}).status_code, 403)

    def test_class_deletion_keeps_enrollment_history(self):
        self.client.force_login(self.biller)
        self.assertEqual(self.post("students/register", self.register_body()).status_code, 201)
        path = f"academic/classes/{self.c6a.pk}"
        self.client.force_login(self.director)
        response = self.client.delete(self.base + path, {"revision": 1}, content_type="application/json")
        self.assertEqual(response.status_code, 409, response.content)
        self.assertTrue(Enrollment.objects.filter(classroom=self.c6a).exists())
        batch = self.post("academic/quick-classes", {
            "year": str(self.year.pk), "level": str(self.level.pk), "names": ["6e B"],
        })
        unused_id = batch.json()["classes"][0]["id"]
        response = self.client.delete(
            self.base + f"academic/classes/{unused_id}", {"revision": 1}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(AcademicClass.objects.filter(pk=unused_id).exists())

    def test_class_enroll_and_apply_fees_and_overview(self):
        students = [Student.objects.create(school=self.school, student_code=f"S{i}", first_name="T", last_name=f"N{i}") for i in range(3)]
        self.client.force_login(self.secretary)
        r = self.post(f"classes/{self.c6a.pk}/enroll", {"students": [str(s.pk) for s in students]})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()["enrolled"]), 2)
        self.assertEqual(len(r.json()["failed"]), 1)
        self.assertEqual(self.post(f"classes/{self.c6a.pk}/apply-fees", {}).status_code, 403)
        self.client.force_login(self.biller)
        r = self.post(f"classes/{self.c6a.pk}/apply-fees", {})
        self.assertEqual(r.json()["charges_created"], 4)
        self.assertEqual(self.post(f"classes/{self.c6a.pk}/apply-fees", {}).json()["charges_created"], 0)
        charge = FeeCharge.objects.filter(enrollment__student=students[0]).first()
        FeePayment.objects.create(school=self.school, charge=charge, idempotency_key=uuid.uuid4(), amount=charge.amount,
                                  currency="XAF", method="moov_money", paid_on=timezone.localdate())
        o = self.client.get(self.base + "overview/classes").json()
        c = o["classes"][0]
        self.assertEqual((c["enrolled"], c["remaining"], c["fee_schedules"]), (2, 0, 2))
        self.assertEqual(c["finance"]["billed"], "400000.00")
        self.assertEqual(c["finance"]["partiel"], 1)
        self.assertEqual(o["unassigned_students"], 1)
        rows = {s["id"]: s for s in self.client.get(self.base + "overview/students").json()["students"]}
        self.assertEqual(rows[str(students[0].pk)]["finance"]["methods"], ["moov_money"])
        dossier = self.client.get(self.base + f"students/{students[0].pk}/dossier").json()
        self.assertEqual(dossier["enrollments"][0]["finance"]["payments"][0]["method"], "moov_money")
        self.assertEqual(dossier["enrollments"][0]["classroom_name"], "6e A")
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.base + f"students/{students[0].pk}/dossier").status_code, 403)

    def test_student_info_fields_editable(self):
        s = Student.objects.create(school=self.school, student_code="E1", first_name="A", last_name="B")
        self.client.force_login(self.secretary)
        r = self.client.patch(self.base + f"students/{s.pk}", json.dumps({"revision": 1, "nationality": "Gabonaise", "gender": "F"}),
                              content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["gender"], "F")
        bad = self.client.patch(self.base + f"students/{s.pk}", json.dumps({"revision": 2, "gender": "X"}), content_type="application/json")
        self.assertEqual(bad.status_code, 422)

    def test_school_form_is_configurable_by_secretariat(self):
        self.client.force_login(self.secretary)
        form = self.client.get(self.base + "enrollment-form").json()
        self.assertEqual(form["revision"], 0)
        config = form["config"]
        config["fields"]["place_of_birth"]["required"] = True
        config["fields"]["guardian_phone"] = {"visible": False, "required": False}
        config["custom_fields"] = [
            {"key": "religion", "label": "Confession", "type": "select", "options": ["Catholique", "Protestante", "Autre"], "required": True},
            {"key": "transport", "label": "Transport scolaire", "type": "yesno"},
        ]
        config["documents"].append({"key": "certificat_radiation", "label": "Certificat de radiation", "required": True})
        r = self.client.put(self.base + "enrollment-form", json.dumps({"config": config, "revision": 0}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        stale = self.client.put(self.base + "enrollment-form", json.dumps({"config": config, "revision": 0}), content_type="application/json")
        self.assertEqual(stale.status_code, 409)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.put(self.base + "enrollment-form", json.dumps({"config": config, "revision": 1}), content_type="application/json").status_code, 403)
        self.client.force_login(self.secretary)
        body = self.register_body(guardians=[{"full_name": "Parent"}])
        missing = self.post("students/register", body)
        self.assertEqual(missing.status_code, 422)
        self.assertIn("Confession", missing.json()["error"])
        body["student"].update(extra_fields={"religion": "Autre", "transport": True},
                               documents={"acte_naissance": True, "photos": True})
        ok = self.post("students/register", body)
        self.assertEqual(ok.status_code, 201, ok.content)
        sid = ok.json()["student"]["id"]
        dossier = self.client.get(self.base + f"students/{sid}/dossier").json()
        self.assertEqual(dossier["student"]["extra_fields"]["religion"], "Autre")
        self.assertEqual(dossier["missing_documents"], ["Certificat de radiation"])
        bad = dict(body); bad["student"] = dict(body["student"], extra_fields={"religion": "Inconnue"})
        self.assertEqual(self.post("students/register", bad).status_code, 422)
        r = self.client.patch(self.base + f"students/{sid}", json.dumps({"revision": 1, "documents": {"acte_naissance": True, "photos": True, "certificat_radiation": True}}),
                              content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.client.get(self.base + f"students/{sid}/dossier").json()["missing_documents"], [])
