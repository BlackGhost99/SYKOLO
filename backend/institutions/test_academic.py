import json
from django.contrib.auth import get_user_model
from django.db import connection, IntegrityError, transaction
from django.test import Client, TestCase, override_settings
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

    def test_used_primary_level_can_be_renamed_without_changing_its_code(self):
        year = self.year()
        cycle = self.make("cycles", {"code": "primaire", "name": "Primaire"})
        level = self.make("levels", {
            "code": "3e-annee", "name": "Troisième année",
            "cycle": cycle["id"], "order": 3,
        })
        self.make("classes", {
            "code": "3e-a", "name": "3e année A",
            "year": year["id"], "level": level["id"],
        })
        denied = self.write("levels", {
            "revision": level["revision"], "code": "ce1",
        }, method="patch", obj_id=level["id"])
        self.assertEqual(denied.status_code, 409)
        renamed = self.write("levels", {
            "revision": level["revision"],
            "name": "3e année fondamentale", "order": 3,
        }, method="patch", obj_id=level["id"])
        self.assertEqual(renamed.status_code, 200, renamed.content)
        self.assertEqual(renamed.json()["code"], "3e-annee")
        self.assertEqual(renamed.json()["name"], "3e année fondamentale")
        self.assertEqual(renamed.json()["revision"], level["revision"] + 1)

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
        # Legacy direct toggling is denied: year status transitions are audited.
        denied = self.write("years", {"revision": 1, "active": False}, method="patch", obj_id=year["id"])
        self.assertEqual(denied.status_code, 422)
        archived = AcademicYear.objects.get(pk=year["id"])
        archived.status = AcademicYear.STATUS_CLOSED
        archived.active = False
        archived.save(update_fields=["status", "active"])
        self.assertEqual(self.client.get(self.base + "years/" + year["id"]).json()["status"], "closed")
        self.assertEqual(self.write("years", {"revision": 1, "name": "Nouveau nom"}, method="patch", obj_id=year["id"]).status_code, 409)
        self.assertEqual(self.write("years", {"revision": 2, "school": str(self.other_school.pk)}, method="patch", obj_id=year["id"]).status_code, 422)
        self.assertEqual(self.write("years", {}, method="delete", obj_id=year["id"]).status_code, 405)
        self.assertEqual(self.write("years", {"code": "reverse", "name": "Dates", "start_date": "2027-08-01", "end_date": "2026-09-01"}).status_code, 422)

    def test_reject_anonymous_and_csrf(self):
        self.assertEqual(self.client.post(self.base + "cycles", json.dumps({"code": "x"}), content_type="application/json").status_code, 403)
        self.assertEqual(self.client.get(self.base + "unknown").status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "years").status_code, 401)

    def test_prepare_year_copies_only_class_structure_and_preserves_history(self):
        from .academic_models import AcademicClass
        from .student_models import Student, Enrollment
        previous=self.year()
        cycle=self.make("cycles",{"code":"col","name":"Collège"})
        level=self.make("levels",{"code":"six","name":"Sixième","cycle":cycle["id"]})
        existing=self.make("classes",{"code":"six-a","name":"6e A","year":previous["id"],
                                     "level":level["id"],"capacity":35})
        student=Student.objects.create(school=self.school,student_code="A-11",
                                       first_name="Maïa",last_name="NZÉ")
        Enrollment.objects.create(school=self.school,student=student,year_id=previous["id"],
                                  classroom_id=existing["id"],enrolled_on="2026-09-07")
        payload={"code":"2027-2028","name":"Année 2027-2028",
                 "start_date":"2027-09-01","end_date":"2028-07-31",
                 "source_year":previous["id"],"copy_classes":True}
        created=self.write("prepare-year",payload)
        self.assertEqual(created.status_code,201,created.content)
        year=created.json()["year"]
        self.assertEqual(created.json()["classes_copied"],1)
        rooms=AcademicClass.objects.filter(school=self.school,year_id=year["id"])
        self.assertEqual(rooms.count(),1)
        self.assertEqual(rooms.first().name,"6e A")
        self.assertNotEqual(str(rooms.first().pk),existing["id"])
        self.assertEqual(Enrollment.objects.filter(school=self.school,year_id=year["id"]).count(),0)
        self.assertEqual(Enrollment.objects.filter(school=self.school,year_id=previous["id"]).count(),1)
        past=self.client.get(self.base+"annual-snapshot?year="+previous["id"])
        future=self.client.get(self.base+"annual-snapshot?year="+year["id"])
        self.assertEqual(past.status_code,200)
        self.assertEqual(future.status_code,200)
        self.assertEqual(past.json()["stats"]["enrollments"],1)
        self.assertEqual(future.json()["stats"]["enrollments"],0)
        self.assertEqual(future.json()["stats"]["classes"],1)
        self.assertEqual(future.json()["periods"],[])
        self.assertEqual(self.write("prepare-year",payload).status_code,409)


    def test_activate_year_is_audited_and_unique_per_school(self):
        from .models import SchoolAudit
        first = self.year()
        snapshot = self.client.get(self.base + "annual-snapshot").json()
        self.assertEqual(snapshot["year"]["status"], "preparation")
        self.assertTrue(snapshot["can_activate_year"])
        denied = self.write("years/" + first["id"] + "/activate", {
            "revision": 1, "reason": "court"
        })
        self.assertEqual(denied.status_code, 422)
        activated = self.write("years/" + first["id"] + "/activate", {
            "revision": 1, "reason": "Ouverture officielle de la rentrée"
        })
        self.assertEqual(activated.status_code, 200, activated.content)
        self.assertEqual(activated.json()["year"]["status"], "current")
        self.assertEqual(activated.json()["year"]["revision"], 2)
        self.assertEqual(SchoolAudit.objects.filter(
            school=self.school, event="academic_year_activated"
        ).count(), 1)
        self.assertEqual(self.client.get(self.base + "annual-snapshot").json()["year"]["id"], first["id"])
        another = self.make("years", {"code": "2027-2028", "name": "2027-2028",
                                      "start_date": "2027-09-01", "end_date": "2028-07-31"})
        self.assertEqual(another["status"], "preparation")
        self.assertEqual(self.client.get(self.base + "annual-snapshot?year=" +
                         another["id"]).json()["can_activate_year"], False)
        blocked = self.write("years/" + another["id"] + "/activate", {
            "revision": 1, "reason": "Nouvelle rentrée prévue"
        })
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(AcademicYear.objects.filter(school=self.school,
                                                     status="current").count(), 1)

    def test_activation_rejects_foreign_school_restricted_access_and_revision(self):
        first = self.year()
        self.assertEqual(self.write("years/" + first["id"] + "/activate", {
            "revision": 4, "reason": "Ouverture administrative"
        }).status_code, 409)
        self.login(self.reader)
        self.assertEqual(self.write("years/" + first["id"] + "/activate", {
            "revision": 1, "reason": "Pas autorisé à activer"
        }).status_code, 403)
        self.login(self.stranger)
        self.assertEqual(self.write("years/" + first["id"] + "/activate", {
            "revision": 1, "reason": "Année établissement tiers"
        }).status_code, 404)

    def test_current_year_takes_precedence_over_future_prepared_year(self):
        from .overview_views import current_year
        first = self.year()
        response = self.write("years/" + first["id"] + "/activate", {
            "revision": 1, "reason": "Année de référence officielle"
        })
        self.assertEqual(response.status_code, 200)
        later = self.make("years", {"code": "2027-2028", "name": "2027-2028",
                                    "start_date": "2027-09-01", "end_date": "2028-07-31"})
        self.assertEqual(str(current_year(self.school).pk), first["id"])
        self.assertNotEqual(first["id"], later["id"])


    def test_closure_preflight_and_disabled_by_default(self):
        from .academic_models import AcademicYearClosure
        year = self.year()
        active = self.write("years/" + year["id"] + "/activate", {
            "revision": 1, "reason": "Ouverture officielle de l'année"
        })
        self.assertEqual(active.status_code, 200, active.content)
        preview = self.client.get(self.base + "years/" + year["id"] + "/closure-review")
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertFalse(preview.json()["can_close"])
        self.assertTrue(any(item["code"] == "year_not_finished"
                            for item in preview.json()["checks"]["blockers"]))
        self.assertEqual(preview.json()["snapshot"]["counts"]["enrollments"], 0)
        rejected = self.write("years/" + year["id"] + "/close", {
            "revision": 2, "confirmation": "2026-2027",
            "reason": "Clôture officielle demandée par la direction"
        })
        self.assertEqual(rejected.status_code, 503)
        self.assertEqual(AcademicYearClosure.objects.count(), 0)
        self.assertEqual(AcademicYear.objects.get(pk=year["id"]).status, "current")
        self.login(self.reader)
        self.assertEqual(self.client.get(self.base + "years/" + year["id"] + "/closure-review").status_code, 403)

    def test_closure_review_detects_unpublished_report(self):
        from .academic_models import AcademicClass
        from .report_models import SchoolReport
        from .student_models import Student, Enrollment
        year = self.make("years", {
            "code": "2023-2024", "name": "2023-2024",
            "start_date": "2023-09-01", "end_date": "2024-07-31",
        })
        cycle = self.make("cycles", {"code": "pr", "name": "Primaire"})
        level = self.make("levels", {"code": "cm1", "name": "CM1", "cycle": cycle["id"]})
        room = self.make("classes", {
            "code": "cm1a", "name": "CM1 A", "year": year["id"], "level": level["id"]
        })
        student = Student.objects.create(school=self.school, student_code="Z-01",
                                         first_name="Lea", last_name="NZE")
        enrollment = Enrollment.objects.create(
            school=self.school, student=student, year_id=year["id"],
            classroom_id=room["id"], enrolled_on="2023-09-07",
        )
        SchoolReport.objects.create(
            school=self.school, enrollment=enrollment, year_id=year["id"],
            period_key="", status="draft", snapshot={},
        )
        self.assertEqual(self.write("years/" + year["id"] + "/activate", {
            "revision": 1, "reason": "Ouverture de l'année historique",
        }).status_code, 200)
        preview = self.client.get(self.base + "years/" + year["id"] + "/closure-review")
        self.assertEqual(preview.status_code, 200)
        self.assertIn("draft_reports", [x["code"] for x in preview.json()["checks"]["blockers"]])

    def test_closed_year_writes_are_denied_by_postgresql(self):
        from .academic_models import AcademicClass
        if connection.vendor != "postgresql":
            self.skipTest("DB triggers are a PostgreSQL production safeguard")
        year = self.make("years", {
            "code": "2023-2024", "name": "2023-2024",
            "start_date": "2023-09-01", "end_date": "2024-07-31"
        })
        cycle = self.make("cycles", {"code": "pr", "name": "Primaire"})
        level = self.make("levels", {"code": "cm1", "name": "CM1", "cycle": cycle["id"]})
        klass = self.make("classes", {
            "code": "cm1a", "name": "CM1 A", "year": year["id"], "level": level["id"]
        })
        from .student_models import Student, Enrollment
        from .finance_models import FeeSchedule, FeeCharge, CashClosing
        from .report_models import SchoolReport
        from .attendance_models import AttendanceSession
        student = Student.objects.create(school=self.school, student_code="Z-02",
                                         first_name="Jon", last_name="NZE")
        enrollment = Enrollment.objects.create(
            school=self.school, student=student, year_id=year["id"],
            classroom_id=klass["id"], enrolled_on="2023-09-07",
        )
        schedule = FeeSchedule.objects.create(
            school=self.school, year_id=year["id"], code="annuelle",
            label="Frais annuels", amount="1000", currency="XAF", scope_key="",
        )
        charge = FeeCharge.objects.create(
            school=self.school, enrollment=enrollment, schedule=schedule,
            label="Frais annuels", amount="1000", currency="XAF",
        )
        report = SchoolReport.objects.create(
            school=self.school, enrollment=enrollment, year_id=year["id"],
            period_key="", status="published", snapshot={"mentions":"intact"},
        )
        session = AttendanceSession.objects.create(
            school=self.school, classroom_id=klass["id"], attendance_date="2023-09-11",
            slot="matin", label="Matin", created_by=self.director,
        )
        AcademicYear.objects.filter(pk=year["id"]).update(status="closed", active=False)
        for qs, update in (
            (Enrollment.objects.filter(pk=enrollment.pk), {"status": "radié"}),
            (FeeCharge.objects.filter(pk=charge.pk), {"label": "Frais altérés"}),
            (SchoolReport.objects.filter(pk=report.pk), {"snapshot": {"mentions": "modifié"}}),
            (AttendanceSession.objects.filter(pk=session.pk), {"label": "Modifié"}),
        ):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    qs.update(**update)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CashClosing.objects.create(
                    school=self.school, day="2023-09-12", currency="XAF",
                    expected="0", counted="0", difference="0",
                    submitted_by=self.director,
                )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AcademicClass.objects.filter(pk=klass["id"]).update(name="CM1 historique altéré")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AcademicClass.objects.create(
                    school=self.school, year_id=year["id"], level_id=level["id"],
                    code="cm1b", name="CM1 B",
                )
        self.assertEqual(AcademicClass.objects.get(pk=klass["id"]).name, "CM1 A")

    @override_settings(YEM_YEAR_CLOSURE_ENABLED=True)
    def test_close_year_generates_snapshot_audit_and_immutable_history(self):
        from .academic_models import AcademicYearClosure, AcademicClass
        from .models import SchoolAudit
        if connection.vendor != "postgresql":
            self.skipTest("Final closure is enabled only with PostgreSQL guards")
        year = self.make("years", {
            "code": "2023-2024", "name": "Année 2023-2024",
            "start_date": "2023-09-01", "end_date": "2024-07-31"
        })
        cycle = self.make("cycles", {"code": "pr", "name": "Primaire"})
        level = self.make("levels", {"code": "cm2", "name": "CM2", "cycle": cycle["id"]})
        self.make("classes", {"code": "cm2a", "name": "CM2 A", "year": year["id"], "level": level["id"]})
        active = self.write("years/" + year["id"] + "/activate", {
            "revision": 1, "reason": "Ouverture administrative de l'année historique"
        })
        self.assertEqual(active.status_code, 200, active.content)
        payload = {"revision": 2, "confirmation": "2023-2024",
                   "reason": "Toutes les opérations sont terminées et vérifiées"}
        preview = self.client.get(self.base + "years/" + year["id"] + "/closure-review")
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertTrue(preview.json()["checks"]["ready"])
        wrong = self.write("years/" + year["id"] + "/close",
                           {**payload, "confirmation": "2024-2025"})
        self.assertEqual(wrong.status_code, 422)
        response = self.write("years/" + year["id"] + "/close", payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["year"]["status"], "closed")
        self.assertFalse(response.json()["year"]["active"])
        evidence = AcademicYearClosure.objects.get(year_id=year["id"])
        self.assertEqual(evidence.snapshot["counts"]["classes"], 1)
        self.assertEqual(len(evidence.digest_sha256), 64)
        self.assertEqual(SchoolAudit.objects.filter(
            school=self.school, event="academic_year_closed").count(), 1)
        finished = self.client.get(self.base + "years/" + year["id"] + "/closure-review").json()
        self.assertTrue(finished["evidence"]["integrity_ok"])
        self.assertEqual(self.write("years/" + year["id"] + "/close", payload).status_code, 409)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AcademicClass.objects.filter(year_id=year["id"]).update(name="Modification interdite")

    def test_year_preparation_rejects_overlap_and_cross_school_source(self):
        existing=self.year()
        overlapping={"code":"overlap","name":"Année chevauchante",
                     "start_date":"2027-05-01","end_date":"2028-07-31",
                     "source_year":None,"copy_classes":False}
        self.assertEqual(self.write("prepare-year",overlapping).status_code,409)
        future={**overlapping,"code":"2027-2028","name":"2027-2028",
                "start_date":"2027-09-01"}
        future["source_year"]=str(self.other_school.pk)
        future["copy_classes"]=True
        self.assertEqual(self.write("prepare-year",future).status_code,422)
        self.assertEqual(AcademicYear.objects.filter(school=self.school).count(),1)

    def test_annual_summary_requires_permission_and_rejects_foreign_year(self):
        year=self.year()
        self.login(self.reader)
        response=self.client.get(self.base+"annual-snapshot?year="+year["id"])
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()["can_prepare_year"])
        self.assertEqual(self.write("prepare-year",{
            "code":"2027-2028","name":"Année","start_date":"2027-09-01",
            "end_date":"2028-07-31","source_year":None,"copy_classes":False,
        }).status_code,403)
        self.assertEqual(self.client.get(self.base+"annual-snapshot?year="+str(self.other_school.pk)).status_code,422)
