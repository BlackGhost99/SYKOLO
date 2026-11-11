"""Confidentialité des fiches élèves et séparation des accès dans YEM."""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .finance_models import FeeCharge, FeeSchedule
from .models import Organization, School, SchoolMember, SchoolRole
from .student_models import Enrollment, Student, StudentGuardian


class StudentRecordPermissionTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.org = Organization.objects.create(name="Groupe pour cloisonnement")
        self.school = School.objects.create(
            organization=self.org, name="Collège sécurité",
            school_type="college", education_cycles=["college"],
        )
        self.other = School.objects.create(
            organization=self.org, name="École voisine",
            school_type="college", education_cycles=["college"],
        )
        self.student = Student.objects.create(
            school=self.school, student_code="EL00011",
            first_name="Marie", last_name="Obame", date_of_birth=date(2012, 5, 8),
            gender="F", address="Quartier confidentiel",
            place_of_birth="Libreville", nationality="Gabonaise",
            previous_school="Établissement précédent privé",
            extra_fields={"sante":"Réponse confidentielle"},
            documents={"copie_acte":True},
        )
        self.guardian = StudentGuardian.objects.create(
            school=self.school, student=self.student, full_name="Parent Obame",
            phone="+241077998877", email="parent@example.test", is_primary=True,
            address="Adresse privée de famille",
        )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="2026–2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
        )
        self.cycle = AcademicCycle.objects.create(
            school=self.school, code="college", name="Collège",
        )
        self.level = AcademicLevel.objects.create(
            school=self.school, cycle=self.cycle, code="6e", name="Sixième",
        )
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level,
            code="6A", name="Sixième A",
        )
        self.enrollment = Enrollment.objects.create(
            school=self.school, student=self.student, year=self.year,
            classroom=self.classroom, enrolled_on=date(2026, 9, 3),
        )
        schedule = FeeSchedule.objects.create(
            school=self.school, year=self.year, code="ecolage",
            label="Écolage", amount=Decimal("40000"), currency="XAF",
            due_date=date(2026, 9, 10),
        )
        FeeCharge.objects.create(
            school=self.school, enrollment=self.enrollment, schedule=schedule,
            label="Écolage", amount=schedule.amount, currency="XAF",
            due_date=schedule.due_date,
        )
        self.people={}
        rights={
            "pedagogie":["school.view","school.students.profile.read"],
            "administration":["school.view","school.students.profile.read",
                              "school.students.admin.write"],
            "sensible":["school.view","school.students.profile.read",
                        "school.students.sensitive.read"],
            "comptabilite":["school.view","school.students.finance.read",
                            "school.finance.read"],
            "sans_finances":["school.view","school.students.finance.read"],
            "ancien":["school.view","school.students.read"],
            "ancienne_direction":["school.view","school.students.read",
                                  "school.students.manage"],
        }
        for code, perms in rights.items():
            user=U.objects.create_user(username="permissions-"+code,password="YEM-test-2026-Secure!")
            role=SchoolRole.objects.create(school=self.school,code=code,
                                           label=code,permissions=perms)
            SchoolMember.objects.create(school=self.school,user=user,role=role)
            self.people[code]=user
        self.base=f"/api/v1/schools/{self.school.pk}/"

    def login(self,code):
        self.client.force_login(self.people[code])

    def patch(self,path,data):
        return self.client.patch(self.base+path, data=json.dumps(data),
                                 content_type="application/json")

    def test_pedagogical_reader_sees_identity_and_schooling_only(self):
        self.login("pedagogie")
        students=self.client.get(self.base+"students")
        self.assertEqual(students.status_code,200,students.content)
        entry=students.json()["students"][0]
        self.assertEqual(entry["first_name"],"Marie")
        self.assertEqual(entry["student_code"],"EL00011")
        for field in ("date_of_birth","address","extra_fields","documents","nationality"):
            self.assertNotIn(field,entry)
        detail=self.client.get(self.base+f"students/{self.student.pk}")
        self.assertNotIn("date_of_birth",detail.json())
        dossier=self.client.get(self.base+f"students/{self.student.pk}/dossier")
        self.assertEqual(dossier.status_code,200,dossier.content)
        d=dossier.json()
        self.assertFalse(d["sensitive_visible"])
        self.assertEqual(d["guardians"],[])
        self.assertEqual(d["missing_documents"],[])
        self.assertFalse(d["finance_visible"])
        self.assertEqual(d["enrollments"][0]["classroom_name"],"Sixième A")
        self.assertEqual(self.client.get(self.base+f"students/{self.student.pk}/guardians").status_code,403)
        self.assertEqual(self.client.get(self.base+"overview/students").json()["students"][0]["guardian"],None)
        self.assertEqual(self.patch(f"students/{self.student.pk}",{"revision":1,"last_name":"Autre"}).status_code,403)

    def test_admin_write_does_not_grant_sensitive_read_or_export(self):
        self.login("administration")
        allowed=self.patch(f"students/{self.student.pk}",{"revision":1,"last_name":"Obame-Bis"})
        self.assertEqual(allowed.status_code,200,allowed.content)
        self.assertEqual(allowed.json()["last_name"],"Obame-Bis")
        self.assertNotIn("address",allowed.json())
        blocked=self.patch(f"students/{self.student.pk}",{
            "revision":2,"address":"Adresse forcée",
        })
        self.assertEqual(blocked.status_code,403)
        self.assertEqual(self.client.get(self.base+f"students/{self.student.pk}/guardians").status_code,403)
        self.assertEqual(self.client.post(self.base+"imports/students/export",
                                         data="{}", content_type="application/json").status_code,403)

    def test_sensitive_reader_sees_family_details_but_cannot_write(self):
        self.login("sensible")
        result=self.client.get(self.base+f"students/{self.student.pk}/dossier")
        self.assertEqual(result.status_code,200)
        d=result.json()
        self.assertEqual(d["student"]["address"],"Quartier confidentiel")
        self.assertEqual(d["guardians"][0]["phone"],"+241077998877")
        self.assertTrue(d["student"]["documents"]["copie_acte"])
        self.assertEqual(self.client.get(self.base+f"students/{self.student.pk}/guardians").status_code,200)
        self.assertEqual(self.patch(f"students/{self.student.pk}",{"revision":1,"last_name":"Autre"}).status_code,403)

    def test_finance_only_gets_name_class_balance_no_family_contacts(self):
        self.login("comptabilite")
        self.assertEqual(self.client.get(self.base+"students").status_code,403)
        self.assertEqual(self.client.get(self.base+f"students/{self.student.pk}/dossier").status_code,403)
        summary=self.client.get(self.base+"overview/students")
        self.assertEqual(summary.status_code,200,summary.content)
        payload=summary.json()
        self.assertTrue(payload["finance_visible"])
        self.assertFalse(payload["sensitive_visible"])
        row=payload["students"][0]
        self.assertEqual(row["first_name"],"Marie")
        self.assertIsNone(row["guardian"])
        self.assertIsNone(row["missing_documents"])
        self.assertEqual(row["enrollment"]["classroom"]["name"],"Sixième A")
        self.assertEqual(row["finance"]["billed"],"40000.00")
        self.assertNotIn("+241077998877",summary.content.decode())
        finance=self.client.get(self.base+"overview/finance")
        self.assertEqual(finance.status_code,200,finance.content)
        self.assertNotIn("+241077998877",finance.content.decode())
        self.assertNotIn("Parent Obame",finance.content.decode())

    def test_finance_requires_both_permissions(self):
        self.login("sans_finances")
        self.assertEqual(self.client.get(self.base+"overview/students").status_code,403)
        self.assertEqual(self.client.get(self.base+"students").status_code,403)

    def test_old_read_only_is_not_sensitive_anymore(self):
        self.login("ancien")
        result=self.client.get(self.base+f"students/{self.student.pk}")
        self.assertEqual(result.status_code,200)
        self.assertNotIn("documents",result.json())
        self.assertEqual(self.client.get(self.base+f"students/{self.student.pk}/guardians").status_code,403)

    def test_old_manage_cannot_leak_sensitive_without_new_permission(self):
        self.login("ancienne_direction")
        self.assertEqual(self.client.get(self.base+f"students/{self.student.pk}/guardians").status_code,403)
        self.assertEqual(self.patch(f"students/{self.student.pk}",{
            "revision":1,"documents":{"copie_acte":False},
        }).status_code,403)

    def test_school_isolation(self):
        self.login("sensible")
        response=self.client.get(f"/api/v1/schools/{self.other.pk}/students/{self.student.pk}")
        self.assertIn(response.status_code,(403,404))
