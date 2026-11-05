"""No import may silently change finances, leak tenants or duplicate learners."""
import io
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .import_models import StudentImportBatch, StudentImportProfile
from .models import Organization, School, SchoolRole, SchoolMember, SchoolAdminPolicy
from .services import ROLE_TEMPLATES
from .student_models import Student, Enrollment, StudentGuardian, EnrollmentFormConfig
from .finance_models import FeeCharge
from .enrollment_form import default_config


class StudentImportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.secretary = User.objects.create_user(username="secretary-import", password="Complex passphrase 2026")
        self.teacher = User.objects.create_user(username="teacher-import", password="Complex passphrase 2026")
        org = Organization.objects.create(name="Import tests")
        self.school = School.objects.create(organization=org, name="École Horizon")
        self.foreign_school = School.objects.create(organization=org, name="Autre école")
        for school in (self.school, self.foreign_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        SchoolMember.objects.create(school=self.school, user=self.secretary,
            role=SchoolRole.objects.get(school=self.school, code="secretariat"))
        SchoolMember.objects.create(school=self.school, user=self.teacher,
            role=SchoolRole.objects.get(school=self.school, code="enseignant"))
        today = timezone.localdate()
        self.year = AcademicYear.objects.create(school=self.school, code="y", name="2026–2027",
            start_date=today - timedelta(days=10), end_date=today + timedelta(days=300))
        cycle = AcademicCycle.objects.create(school=self.school, code="c", name="Collège")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="6e", name="Sixième")
        self.klass = AcademicClass.objects.create(school=self.school, year=self.year, level=level,
            code="6a", name="6e A", capacity=10)
        self.mapping = {"0": "last_name", "1": "first_name", "2": "date_of_birth",
                        "3": "classroom", "4": "guardian_name", "5": "guardian_phone"}

    def file(self, duplicate=False):
        rows = ["Nom;Prénoms;DDN;Classe;Nom parent;Téléphone parent",
                "NZE;Aaron;02/03/2015;6e A;NZE Sylvie;077432108"]
        if duplicate:
            rows.append("NZE;Aaron;02/03/2015;6e A;NZE Sylvie;077432108")
        return SimpleUploadedFile("eleves.csv", ("\n".join(rows)).encode("utf-8"), content_type="text/csv")

    def request(self, action, *, file=None, mapping=None, year=True, token=None, extra=None, school=None):
        data = {"file": file or self.file(), "mapping": json.dumps(mapping if mapping is not None else self.mapping),
                "header_row": "1", "year": str(self.year.pk) if year else ""}
        if token:
            data["token"] = token
        if extra:
            data.update(extra)
        url = "/api/v1/schools/%s/imports/students/%s" % (school or self.school.pk, action)
        return self.client.post(url, data)

    def test_inspect_preview_commit_idempotence_and_no_finance(self):
        self.client.force_login(self.secretary)
        info = self.request("inspect").json()
        self.assertEqual(info["row_count"], 1)
        self.assertEqual(info["suggested_mapping"]["0"], "last_name")
        self.assertEqual(info["suggested_mapping"]["1"], "first_name")
        self.assertEqual(info["suggested_mapping"]["2"], "date_of_birth")
        preview = self.request("preview")
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["errors"], 0, preview.content)
        self.assertEqual(Student.objects.count(), 0)
        result = self.request("commit", token=preview.json()["token"], extra={"template_name": "Modèle A"})
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.json()["imported"], 1)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 1)
        self.assertEqual(StudentGuardian.objects.filter(school=self.school).count(), 1)
        self.assertEqual(Enrollment.objects.filter(school=self.school).count(), 1)
        self.assertEqual(FeeCharge.objects.count(), 0)
        self.assertEqual(StudentImportProfile.objects.filter(school=self.school).count(), 1)
        self.assertEqual(StudentImportBatch.objects.filter(school=self.school).count(), 1)
        repeated = self.request("commit", token=preview.json()["token"])
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertTrue(repeated.json()["already_imported"])
        self.assertEqual(Student.objects.count(), 1)

    def test_duplicate_in_file_and_existing_duplicate_blocked(self):
        self.client.force_login(self.secretary)
        preview = self.request("preview", file=self.file(duplicate=True))
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["errors"], 1)
        confirm = self.request("commit", file=self.file(duplicate=True), token=preview.json()["token"])
        self.assertEqual(confirm.status_code, 409)
        self.assertEqual(Student.objects.count(), 0)
        Student.objects.create(school=self.school, student_code="existing", first_name="Aaron",
                               last_name="NZE", date_of_birth="2015-03-02")
        self.assertEqual(self.request("preview").json()["errors"], 1)

    def test_access_control_and_cross_school_isolation(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.request("inspect").status_code, 403)
        self.client.force_login(self.secretary)
        self.assertEqual(self.request("inspect", school=self.foreign_school.pk).status_code, 404)
        p = self.request("preview").json()
        self.assertEqual(self.request("commit", token=p["token"], school=self.foreign_school.pk).status_code, 404)
        self.assertEqual(Student.objects.count(), 0)

    def test_changed_mapping_or_forged_token_blocked(self):
        self.client.force_login(self.secretary)
        preview = self.request("preview").json()
        tampered = self.request("commit", token=preview["token"],
                                mapping={**self.mapping, "5": "guardian_email"})
        self.assertEqual(tampered.status_code, 409)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(self.request("commit", token="forged-signature").status_code, 409)

    def test_quota_and_capacity_are_enforced_before_writing(self):
        self.client.force_login(self.secretary)
        SchoolAdminPolicy.objects.create(school=self.school, max_students=0)
        preview = self.request("preview").json()
        self.assertTrue(preview["errors"])
        self.assertEqual(self.request("commit", token=preview["token"]).status_code, 409)
        self.assertEqual(Student.objects.count(), 0)

    def test_custom_field_mapping_and_form_rules(self):
        self.client.force_login(self.secretary)
        config = default_config()
        config["custom_fields"] = [{"key": "transport", "label": "Transport scolaire",
                                    "type": "yesno", "options": [], "required": False, "section": "eleve"}]
        EnrollmentFormConfig.objects.create(school=self.school, config=config)
        payload = "Nom;Prénoms;DDN;Classe;Nom parent;Téléphone parent;Transport scolaire\nNZE;Aaron;02/03/2015;6e A;NZE Sylvie;077432108;Oui"
        mapping = {**self.mapping, "6": "extra.transport"}
        p = self.request("preview", file=SimpleUploadedFile("custom.csv", payload.encode()), mapping=mapping)
        self.assertEqual(p.status_code, 200, p.content)
        self.assertEqual(p.json()["errors"], 0, p.content)
        r = self.request("commit", file=SimpleUploadedFile("custom.csv", payload.encode()),
                         mapping=mapping, token=p.json()["token"])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIs(Student.objects.get().extra_fields["transport"], True)

    def test_xlsx_import_and_macro_rejection(self):
        self.client.force_login(self.secretary)
        workbook = Workbook()
        ws = workbook.active
        ws.title = "2026"
        ws.append(["Nom", "Prénoms", "DDN", "Classe", "Nom parent", "Téléphone parent"])
        ws.append(["NZE", "Aaron", "2015-03-02", "6e A", "NZE Sylvie", "077432108"])
        output = io.BytesIO()
        workbook.save(output)
        f = SimpleUploadedFile("eleves.xlsx", output.getvalue())
        response = self.request("inspect", file=f)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["sheets"], ["2026"])
        self.assertEqual(response.json()["row_count"], 1)
        self.assertEqual(self.request("inspect", file=SimpleUploadedFile("eleves.xlsm", output.getvalue())).status_code, 422)

    def test_student_only_register_is_imported_without_fake_guardian(self):
        self.client.force_login(self.secretary)
        payload = "Nom;Prénoms;DDN;Classe\nNZE;Aaron;02/03/2015;6e A"
        mapping = {"0": "last_name", "1": "first_name", "2": "date_of_birth", "3": "classroom"}
        p = self.request("preview", file=SimpleUploadedFile("simple.csv", payload.encode()), mapping=mapping)
        self.assertEqual(p.status_code, 200, p.content)
        self.assertEqual(p.json()["errors"], 0, p.content)
        self.assertEqual(p.json()["warnings"], 1, p.content)
        self.assertEqual(Student.objects.count(), 0)
        r = self.request("commit", file=SimpleUploadedFile("simple.csv", payload.encode()),
                         mapping=mapping, token=p.json()["token"])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 1)
        self.assertEqual(StudentGuardian.objects.count(), 0)
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_pilot_two_distinct_school_registers_ten_students_each(self):
        """Pilot using variable headers, separate schools, and 10 learners per register."""
        self.client.force_login(self.secretary)
        names = [("NZE", "Aaron"), ("OBAME", "Inès"), ("MBOUMBA", "Kevin"),
                 ("NDONG", "Clara"), ("ESSONO", "Jules"), ("MOUSSAVOU", "Léa"),
                 ("NKOULOU", "Nathan"), ("MBADINGA", "Amina"),
                 ("NZAMBA", "Dylan"), ("OYONO", "Mélissa")]
        first = ["Nom;Prénoms;DDN;Classe;Nom parent;Téléphone parent"]
        first += [f"{last};{first_name};02/03/2015;6e A;Responsable fictif;077432108"
                  for last, first_name in names]
        original = "\n".join(first).encode()
        file1 = lambda: SimpleUploadedFile("college-pilote.csv", original)
        info = self.request("inspect", file=file1()).json()
        self.assertEqual(info["row_count"], 10)
        self.assertEqual(info["suggested_mapping"]["0"], "last_name")
        self.assertEqual(info["suggested_mapping"]["1"], "first_name")
        p = self.request("preview", file=file1()).json()
        self.assertEqual(p["valid"], 10, p)
        r = self.request("commit", file=file1(), token=p["token"])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Student.objects.filter(school=self.school).count(), 10)
        self.assertEqual(Enrollment.objects.filter(school=self.school).count(), 10)
        self.assertEqual(self.request("commit", file=file1(), token=p["token"]).json()["already_imported"], True)

        SchoolMember.objects.create(school=self.foreign_school, user=self.secretary,
                                    role=SchoolRole.objects.get(school=self.foreign_school, code="secretariat"))
        second = ["Classe actuelle;Patronyme;First name;Birth date;Tuteur;Téléphone responsable"]
        second += [f"CM1 A;{last};{first_name};02/03/2015;Parent fictif;077432108"
                   for last, first_name in names]
        file2_data = "\n".join(second).encode()
        file2 = lambda: SimpleUploadedFile("primaire-pilote.csv", file2_data)
        mapping2 = {"1": "last_name", "2": "first_name", "3": "date_of_birth", "4": "guardian_name", "5": "guardian_phone"}
        preview2 = self.request("preview", file=file2(), mapping=mapping2, year=False, school=self.foreign_school.pk)
        self.assertEqual(preview2.status_code, 200, preview2.content)
        self.assertEqual(preview2.json()["valid"], 10, preview2.content)
        result2 = self.request("commit", file=file2(), mapping=mapping2, year=False,
                               school=self.foreign_school.pk, token=preview2.json()["token"])
        self.assertEqual(result2.status_code, 201, result2.content)
        self.assertEqual(Student.objects.filter(school=self.foreign_school).count(), 10)
        self.assertEqual(Student.objects.count(), 20)
        self.assertEqual(StudentGuardian.objects.count(), 20)
        self.assertEqual(FeeCharge.objects.count(), 0)
        self.assertEqual(StudentImportBatch.objects.count(), 2)
