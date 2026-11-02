import json
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .academic_models import AcademicYear, AcademicPeriod
from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES


class AcademicStructureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.founder = User.objects.create_user(username="founder-04", password="A strong example password 2026")
        self.director = User.objects.create_user(username="director-04", password="A strong example password 2026")
        self.reader = User.objects.create_user(username="teacher-04", password="A strong example password 2026")
        self.stranger = User.objects.create_user(username="stranger-04", password="A strong example password 2026")
        org = Organization.objects.create(name="Groupe scolaire")
        OrganizationMember.objects.create(organization=org, user=self.founder, role="founder")
        self.school = School.objects.create(organization=org, name="École A")
        self.other_school = School.objects.create(organization=org, name="École B")
        for school in (self.school, self.other_school):
            for code, label, perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=perms)
        SchoolMember.objects.create(school=self.school, user=self.director, role=SchoolRole.objects.get(school=self.school, code="direction"))
        SchoolMember.objects.create(school=self.school, user=self.reader, role=SchoolRole.objects.get(school=self.school, code="enseignant"))
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.base = "/api/v1/schools/" + str(self.school.pk) + "/academic/"

    def login(self, user):
        self.client.force_login(user)
        self.token = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def write(self, resource, data, method="post", school=None, obj_id=None):
        path = ("/api/v1/schools/" + str(school.pk) + "/academic/" if school else self.base) + resource
        if obj_id:
            path += "/" + str(obj_id)
        return getattr(self.client, method)(path, json.dumps(data), content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

    def make(self, resource, data, school=None):
        response = self.write(resource, data, school=school)
        self.assertEqual(response.status_code, 201, response.content.decode())
        return response.json()

    def year(self):
        return self.make("years", {"code": "2026-2027", "name": "Année test", "start_date": "2026-09-01", "end_date": "2027-07-31"})

    def test_create_flexible_year_cycle_level_track_class_and_four_periods(self):
        year = self.year()
        cycle = self.make("cycles", {"code": "elementaire", "name": "Élémentaire"})
        level = self.make("levels", {"code": "cm2", "name": "CM2", "cycle": cycle["id"]})
        track = self.make("tracks", {"code": "bilingue", "name": "Bilingue", "level": level["id"]})
        classroom = self.make("classes", {"code": "cm2a", "name": "CM2 A", "year": year["id"], "level": level["id"], "track": track["id"], "capacity": 40})
        dates = [("2026-09-01", "2026-10-15"), ("2026-10-16", "2026-12-20"), ("2027-01-05", "2027-03-20"), ("2027-03-21", "2027-07-31")]
        for i, (start, end) in enumerate(dates):
            self.make("periods", {"code": "p" + str(i), "name": "Période " + str(i), "year": year["id"], "start_date": start, "end_date": end})
        self.assertEqual(len(self.client.get(self.base + "periods").json()["periods"]), 4)
        self.assertEqual(self.client.get(self.base + "classes/" + classroom["id"]).json()["track"], track["id"])
        self.assertEqual(AcademicYear.objects.filter(school=self.school).count(), 1)

    def test_no_cross_school_read_or_parent_assignment(self):
        year = self.year()
        self.login(self.reader)
        self.assertEqual(self.client.get(self.base + "years").status_code, 200)
        self.assertEqual(self.write("cycles", {"code": "no", "name": "Non"}).status_code, 403)
        self.login(self.founder)
        self.assertEqual(self.client.get(self.base + "years").status_code, 403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base + "years").status_code, 404)
        self.assertEqual(self.client.get(self.base + "years/" + year["id"]).status_code, 404)
        self.login(self.director)
        SchoolMember.objects.create(school=self.other_school, user=self.director, role=SchoolRole.objects.get(school=self.other_school, code="direction"))
        foreign_cycle = self.make("cycles", {"code": "foreign", "name": "Autre"}, school=self.other_school)
        self.assertEqual(self.write("levels", {"code": "bad", "name": "Niveau", "cycle": foreign_cycle["id"]}).status_code, 422)
        self.assertEqual(self.write("classes", {"code": "bad", "name": "Classe", "year": year["id"], "level": foreign_cycle["id"]}).status_code, 422)
        self.login(self.reader)
        self.assertEqual(self.client.get("/api/v1/schools/" + str(self.other_school.pk) + "/academic/cycles").status_code, 404)

    def test_period_overlap_bounds_year_updates_and_revisions(self):
        year = self.year()
        p = self.make("periods", {"code": "p1", "name": "Période 1", "year": year["id"], "start_date": "2026-09-01", "end_date": "2026-12-30"})
        self.assertEqual(self.write("periods", {"code": "overlap", "name": "Période 2", "year": year["id"], "start_date": "2026-12-30", "end_date": "2027-02-20"}).status_code, 422)
        self.assertEqual(self.write("periods", {"code": "outside", "name": "Période 3", "year": year["id"], "start_date": "2027-08-01", "end_date": "2027-08-10"}).status_code, 422)
        self.assertEqual(self.write("years", {"revision": 1, "end_date": "2026-11-01"}, method="patch", obj_id=year["id"]).status_code, 422)
        updated = self.write("periods", {"revision": 1, "end_date": "2026-12-29"}, method="patch", obj_id=p["id"])
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["revision"], 2)
        self.assertEqual(self.write("periods", {"revision": 1, "name": "Rétrograde"}, method="patch", obj_id=p["id"]).status_code, 409)
        self.assertEqual(AcademicPeriod.objects.count(), 1)

    def test_archival_and_invalid_data(self):
        year = self.year()
        self.assertEqual(self.write("years", {"code": "2026-2027", "name": "Doublon", "start_date": "2026-09-01", "end_date": "2027-07-31"}).status_code, 422)
        archived = self.write("years", {"revision": 1, "active": False}, method="patch", obj_id=year["id"])
        self.assertEqual(archived.status_code, 200)
        self.assertFalse(archived.json()["active"])
        self.assertEqual(self.write("years", {"revision": 2, "school": str(self.other_school.pk)}, method="patch", obj_id=year["id"]).status_code, 422)
        self.assertEqual(self.write("years", {}, method="delete", obj_id=year["id"]).status_code, 405)
        self.assertEqual(self.write("years", {"code": "reverse", "name": "Dates", "start_date": "2027-08-01", "end_date": "2026-09-01"}).status_code, 422)

    def test_reject_anonymous_and_csrf(self):
        self.assertEqual(self.client.post(self.base + "cycles", json.dumps({"code": "x"}), content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get(self.base + "unknown").status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "years").status_code, 401)
