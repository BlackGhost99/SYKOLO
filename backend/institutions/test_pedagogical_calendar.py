"""Tests de correction des années et du Calendrier pédagogique YEM."""
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase

from .academic_models import (
    AcademicClass, AcademicCycle, AcademicLevel, AcademicPeriod, AcademicYear,
    PedagogicalCalendarEvent,
)
from .models import Organization, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES
from .student_models import Enrollment, Student


class PedagogicalCalendarTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(
            username="calendar-director", password="Strong calendar director pass 2026!"
        )
        self.teacher = User.objects.create_user(
            username="calendar-teacher", password="Strong calendar teacher pass 2026!"
        )
        self.other = User.objects.create_user(
            username="calendar-outsider", password="Strong calendar outsider pass 2026!"
        )
        organization = Organization.objects.create(name="Organisation pédagogique")
        self.school = School.objects.create(
            organization=organization, name="École de référence",
            school_type="groupe_scolaire", education_cycles=["primaire", "college"],
        )
        for code, name, permissions in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school, code=code, label=name, permissions=permissions)
        SchoolMember.objects.create(
            school=self.school, user=self.director,
            role=SchoolRole.objects.get(school=self.school, code="direction"),
        )
        SchoolMember.objects.create(
            school=self.school, user=self.teacher,
            role=SchoolRole.objects.get(school=self.school, code="enseignant"),
        )
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026-2027", name="Année 1",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
        )
        self.cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        self.level = AcademicLevel.objects.create(
            school=self.school, cycle=self.cycle, code="1re-annee", name="1re année",
        )
        self.classroom = AcademicClass.objects.create(
            school=self.school, year=self.year, level=self.level,
            code="1re-a", name="1re année A",
        )
        self.client = Client(enforce_csrf_checks=True)
        self.login(self.director)
        self.prefix = "/api/v1/schools/" + str(self.school.pk) + "/academic/"

    def login(self, user):
        self.client.force_login(user)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, path, body):
        return self.client.post(
            self.prefix + path, json.dumps(body), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def patch(self, path, body):
        return self.client.patch(
            self.prefix + path, json.dumps(body), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def event_data(self, **changes):
        body = {
            "year": str(self.year.pk), "title": "Rentrée des élèves",
            "kind": "rentree", "scope": "all",
            "start_date": "2026-09-07", "end_date": "2026-09-07",
            "description": "", "source": "official",
            "source_url": "https://www.gabonreview.com/gabon-la-rentree-des-classes-fixee-au-7-septembre-2026/",
        }
        body.update(changes)
        return body

    def test_current_year_named_annee_1_can_be_corrected_without_moving_dossiers(self):
        pupil = Student.objects.create(school=self.school, first_name="Aline", last_name="TEST")
        enrollment = Enrollment.objects.create(
            school=self.school, student=pupil, year=self.year,
            classroom=self.classroom, enrolled_on=date(2026, 9, 7),
        )
        self.year.status = AcademicYear.STATUS_CURRENT
        self.year.save(update_fields=["status"])
        response = self.patch("years/" + str(self.year.pk), {
            "revision": self.year.revision, "name": "2026-2027",
        })
        self.assertEqual(response.status_code, 200, response.content)
        self.year.refresh_from_db()
        self.assertEqual(self.year.name, "2026-2027")
        self.assertEqual(self.year.code, "2026-2027")
        self.assertEqual(self.year.status, AcademicYear.STATUS_CURRENT)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.year_id, self.year.pk)
        self.assertEqual(enrollment.classroom_id, self.classroom.pk)
        snapshot = self.client.get(self.prefix + "annual-snapshot")
        self.assertEqual(snapshot.status_code, 200, snapshot.content)
        self.assertTrue(snapshot.json()["can_edit_year"])
        self.assertEqual(snapshot.json()["year"]["name"], "2026-2027")

        denied_code = self.patch("years/" + str(self.year.pk), {
            "revision": self.year.revision, "code": "new-code",
        })
        self.assertEqual(denied_code.status_code, 409)
        denied_date = self.patch("years/" + str(self.year.pk), {
            "revision": self.year.revision, "start_date": "2026-08-30",
        })
        self.assertEqual(denied_date.status_code, 409)

    def test_year_renaming_checks_uniqueness_versions_permissions_and_closed_year(self):
        other = AcademicYear.objects.create(
            school=self.school, code="2027-2028", name="2027-2028",
            start_date=date(2027, 9, 1), end_date=date(2028, 7, 31),
        )
        self.assertEqual(self.patch("years/" + str(self.year.pk), {
            "revision": self.year.revision, "name": other.name,
        }).status_code, 409)
        self.assertEqual(self.patch("years/" + str(self.year.pk), {
            "revision": 999, "name": "Année corrigée",
        }).status_code, 409)
        self.login(self.teacher)
        self.assertEqual(self.patch("years/" + str(self.year.pk), {
            "revision": self.year.revision, "name": "Interdit",
        }).status_code, 403)
        self.login(self.director)
        self.year.status = AcademicYear.STATUS_CLOSED
        self.year.active = False
        self.year.save(update_fields=["status", "active"])
        self.assertEqual(self.patch("years/" + str(self.year.pk), {
            "revision": self.year.revision, "name": "Interdit en archive",
        }).status_code, 409)
        snapshot = self.client.get(self.prefix + "annual-snapshot?year=" + str(self.year.pk))
        self.assertFalse(snapshot.json()["can_edit_year"])

    def test_event_can_be_added_renamed_archived_and_reactivated(self):
        created = self.post("pedagogical-calendar", self.event_data(
            title="Rentrée administrative", start_date="2026-08-31", end_date="2026-08-31",
        ))
        self.assertEqual(created.status_code, 201, created.content)
        event_id = created.json()["id"]
        self.assertEqual(created.json()["source"], "official")
        query = self.client.get(self.prefix + "pedagogical-calendar?year=" + str(self.year.pk))
        self.assertEqual(query.status_code, 200)
        self.assertTrue(query.json()["can_manage"])
        self.assertEqual([item["title"] for item in query.json()["events"]], ["Rentrée administrative"])
        self.assertTrue(any(s["code"] == "primaire" for s in query.json()["scopes"]))
        self.assertFalse(any(s["code"] == "lycee_general" for s in query.json()["scopes"]))
        updated = self.patch("pedagogical-calendar/" + event_id, {
            "revision": created.json()["revision"], "title": "Rentrée du personnel",
            "scope": "primaire", "source": "school", "source_url": "",
        })
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["revision"], 2)
        self.assertEqual(updated.json()["title"], "Rentrée du personnel")
        self.assertEqual(self.patch("pedagogical-calendar/" + event_id, {
            "revision": 1, "title": "Conflit",
        }).status_code, 409)
        archived = self.patch("pedagogical-calendar/" + event_id, {
            "revision": 2, "active": False,
        })
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertFalse(archived.json()["active"])
        revived = self.patch("pedagogical-calendar/" + event_id, {
            "revision": 3, "active": True,
        })
        self.assertEqual(revived.status_code, 200, revived.content)
        self.assertTrue(revived.json()["active"])

    def test_events_support_overlapping_holidays_but_guard_dates_tenants_roles_and_closure(self):
        first = self.post("pedagogical-calendar", self.event_data())
        self.assertEqual(first.status_code, 201, first.content)
        second = self.post("pedagogical-calendar", self.event_data(title="Réunion de rentrée"))
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(PedagogicalCalendarEvent.objects.filter(school=self.school).count(), 2)
        outside = self.post("pedagogical-calendar", self.event_data(
            title="Hors année", start_date="2026-06-01", end_date="2026-06-01",
        ))
        self.assertEqual(outside.status_code, 422)
        wrong_cycle = self.post("pedagogical-calendar", self.event_data(scope="lycee_technique"))
        self.assertEqual(wrong_cycle.status_code, 422)
        self.login(self.teacher)
        self.assertEqual(self.post("pedagogical-calendar", self.event_data()).status_code, 403)
        self.login(self.other)
        self.assertEqual(self.client.get(
            self.prefix + "pedagogical-calendar?year=" + str(self.year.pk),
        ).status_code, 404)
        self.login(self.director)
        self.year.status = AcademicYear.STATUS_CLOSED
        self.year.active = False
        self.year.save(update_fields=["status", "active"])
        self.assertEqual(self.post("pedagogical-calendar", self.event_data()).status_code, 409)
        self.assertEqual(self.patch("pedagogical-calendar/" + first.json()["id"], {
            "revision": 1, "active": False,
        }).status_code, 409)
        if connection.vendor == "postgresql":
            with transaction.atomic():
                with self.assertRaises(IntegrityError):
                    PedagogicalCalendarEvent.objects.filter(pk=first.json()["id"]).update(
                        title="Modification SQL non autorisée",
                    )

    def test_periods_are_still_managed_without_duplicate_or_overlapping_interval(self):
        made = self.post("periods", {
            "code": "t1", "name": "Premier trimestre", "year": str(self.year.pk),
            "start_date": "2026-09-07", "end_date": "2026-11-28",
        })
        self.assertEqual(made.status_code, 201, made.content)
        snapshot = self.client.get(self.prefix + "annual-snapshot?year=" + str(self.year.pk))
        self.assertEqual(snapshot.status_code, 200)
        period = snapshot.json()["periods"][0]
        self.assertEqual(period["code"], "t1")
        self.assertEqual(period["revision"], 1)
        edited = self.patch("periods/" + period["id"], {
            "revision": period["revision"], "name": "Trimestre 1",
        })
        self.assertEqual(edited.status_code, 200, edited.content)
        overlap = self.post("periods", {
            "code": "t2", "name": "Trimestre en conflit", "year": str(self.year.pk),
            "start_date": "2026-11-20", "end_date": "2027-03-06",
        })
        self.assertEqual(overlap.status_code, 422)
        self.assertEqual(AcademicPeriod.objects.filter(school=self.school, year=self.year).count(), 1)
