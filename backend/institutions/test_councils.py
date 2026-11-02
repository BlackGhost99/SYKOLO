"""Module 10: configurable deliberations, amendments and isolation."""
import json
from django.test import TestCase
from .test_reports import SchoolReportTests
from .council_models import CouncilDecision, ReportAmendment
from .models import SchoolSetting
from .services import key_for_scope


class CouncilTests(TestCase):
    configure = SchoolReportTests.configure
    login = SchoolReportTests.login
    write = SchoolReportTests.write
    assessment = SchoolReportTests.assessment
    create_report = SchoolReportTests.create_report

    def setUp(self):
        SchoolReportTests.setUp(self)
        self.assessment(self.math, 75)
        created = self.create_report()
        self.assertEqual(created.status_code, 201, created.content.decode())
        self.report = created.json()
        published = self.write("reports/" + self.report["id"] + "/publish", {"revision": 1})
        self.assertEqual(published.status_code, 200, published.content.decode())
        config = {"grading": self.grading, "deliberation": {"decisions": [
            {"code": "admis", "label": "Admis au niveau supérieur"},
            {"code": "maintien", "label": "Maintien dans le niveau"},
        ]}}
        SchoolSetting.objects.filter(school=self.school, scope_key=key_for_scope({})).update(values=config)

    def council(self):
        response = self.write("councils", {
            "classroom": str(self.classroom.pk), "period": str(self.period.pk),
            "title": "Conseil du trimestre", "meeting_date": "2026-12-20",
        })
        self.assertEqual(response.status_code, 201, response.content.decode())
        return response.json()

    def decision(self, council, revision=0, code="admis"):
        return self.write("councils/" + council["id"] + "/decisions", {
            "enrollment": str(self.enrollment.pk), "report": self.report["id"],
            "code": code, "rationale": "Décision étudiée en conseil scolaire.",
            "revision": revision,
        })

    def test_decisions_follow_config_and_council_closure(self):
        council = self.council()
        path = "councils/" + council["id"]
        options = self.client.get(self.base + "council-choices?classroom=" + str(self.classroom.pk))
        self.assertEqual([x["code"] for x in options.json()["decisions"]], ["admis", "maintien"])
        self.assertEqual(self.write(path + "/close", {"revision": 1}).status_code, 422)
        first = self.decision(council)
        self.assertEqual(first.status_code, 201, first.content.decode())
        self.assertEqual(first.json()["label"], "Admis au niveau supérieur")
        self.assertEqual(self.decision(council, revision=0).status_code, 409)
        amended = self.decision(council, revision=1, code="maintien")
        self.assertEqual(amended.status_code, 200, amended.content.decode())
        closed = self.write(path + "/close", {"revision": 3})
        self.assertEqual(closed.status_code, 200, closed.content.decode())
        self.assertEqual(closed.json()["status"], "closed")
        self.assertEqual(self.decision(council, revision=2).status_code, 409)
        self.assertEqual(CouncilDecision.objects.count(), 1)

    def test_school_permissions_and_no_hardcoded_outcome(self):
        council = self.council()
        self.assertEqual(self.decision(council, code="inventee").status_code, 422)
        SchoolSetting.objects.filter(school=self.school, scope_key=key_for_scope({})).update(values={"grading": self.grading})
        self.assertEqual(self.decision(council).status_code, 422)
        self.login(self.secretary)
        self.assertEqual(self.client.get(self.base + "councils").status_code, 200)
        self.assertEqual(self.decision(council).status_code, 403)
        self.assertEqual(self.write("councils/" + council["id"] + "/close", {"revision": 1}).status_code, 403)
        self.login(self.stranger)
        self.assertEqual(self.client.get(self.base + "councils").status_code, 404)
        self.assertEqual(self.client.get(self.base + "councils/" + council["id"]).status_code, 404)
        self.assertEqual(self.client.get(self.base + "reports/" + self.report["id"] + "/amendments").status_code, 404)

    def test_report_amendments_are_append_only_and_pdf_private(self):
        endpoint = "reports/" + self.report["id"] + "/amendments"
        original = self.client.get(self.base + "reports/" + self.report["id"]).json()["snapshot"]
        self.assertEqual(original["overall"]["percent"], "75.00")
        first = self.write(endpoint, {
            "course": str(self.math.pk), "percent": "90",
            "reason": "Erreur de transcription établie par une pièce justificative.",
            "revision": 0,
        })
        self.assertEqual(first.status_code, 201, first.content.decode())
        self.assertEqual(first.json()["snapshot"]["overall"]["percent"], "90.00")
        self.assertEqual(self.write(endpoint, {
            "course": str(self.math.pk), "percent": "91",
            "reason": "Autre rectification justifiée par le dossier.", "revision": 0,
        }).status_code, 409)
        doc = self.client.get(self.base + endpoint + "/" + first.json()["id"] + "/pdf")
        self.assertEqual(doc.status_code, 200)
        self.assertTrue(doc.content.startswith(b"%PDF-"))
        self.assertEqual(doc["Cache-Control"], "private, no-store")
        self.assertEqual(self.client.get(self.base + "reports/" + self.report["id"]).json()["snapshot"], original)
        self.assertEqual(ReportAmendment.objects.count(), 1)
        self.assertEqual(ReportAmendment.objects.first().prior_snapshot["overall"]["percent"], "75.00")
        self.login(self.secretary)
        self.assertEqual(self.write(endpoint, {
            "course": str(self.math.pk), "percent": "80",
            "reason": "Rectification non autorisée.", "revision": 1,
        }).status_code, 403)

    def test_invalid_percent_csrf_and_unauthenticated_access(self):
        path = "reports/" + self.report["id"] + "/amendments"
        for value in ("NaN", "-1", "101", True):
            self.assertEqual(self.write(path, {
                "course": str(self.math.pk), "percent": value,
                "reason": "Erreur de saisie dans le dossier.", "revision": 0,
            }).status_code, 422)
        self.assertEqual(self.client.post(self.base + "councils", json.dumps({
            "classroom": str(self.classroom.pk), "period": None,
            "meeting_date": "2026-12-20", "title": "Conseil",
        }), content_type="application/json").status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.base + "councils").status_code, 401)
