"""API-level smoke test of YEM modules 02 through 10 as one school journey.

This scenario uses a test database and fake people; it does NOT verify Render
deployment, payment gateways, a real browser, external email or data backups.
"""
import json
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from pedagogy.views import PRESETS

from .council_models import CouncilDecision, ReportAmendment
from .report_models import SchoolReport


class CompleteSchoolJourneyTest(TestCase):
    """Create org/school -> setup -> admission -> class -> teacher -> grades -> reports -> council."""

    def setUp(self):
        user_model = get_user_model()
        self.founder = user_model.objects.create_user(
            username="journey-founder", password="Founder strong example passphrase 2026!",
        )
        self.director = user_model.objects.create_user(
            username="journey-director", password="Director strong example passphrase 2026!",
        )
        self.teacher = user_model.objects.create_user(
            username="journey-teacher", password="Teacher strong example passphrase 2026!",
        )
        self.stranger = user_model.objects.create_user(
            username="journey-stranger", password="Stranger strong example passphrase 2026!",
        )
        self.passwords = {
            "journey-founder": "Founder strong example passphrase 2026!",
            "journey-director": "Director strong example passphrase 2026!",
            "journey-teacher": "Teacher strong example passphrase 2026!",
            "journey-stranger": "Stranger strong example passphrase 2026!",
        }
        self.client = Client(enforce_csrf_checks=True)
        self.token = ""
        self.sign_in("journey-founder")

    def post(self, url, payload, expected=201):
        response = self.client.post(
            url, data=json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )
        self.assertEqual(
            response.status_code, expected,
            f"{url}: expected {expected}, got {response.status_code}: {response.content.decode()[:500]}",
        )
        return response.json() if response["Content-Type"].startswith("application/json") else response

    def sign_in(self, username):
        from .models import SchoolLogin
        identity = SchoolLogin.objects.filter(username=username).first()
        context = {"scope": "school", "school_code": str(identity.school_id)} if identity else {}
        self.client.get("/api/v1/auth/csrf")
        self.token = self.client.cookies["csrftoken"].value
        self.post("/api/v1/auth/login", {
            "username": username, "password": self.passwords[username], **context,
        }, expected=200)
        self.client.get("/api/v1/auth/csrf")
        self.token = self.client.cookies["csrftoken"].value

    def switch(self, username):
        self.post("/api/v1/auth/logout", {}, expected=200)
        self.sign_in(username)

    def test_full_api_lifecycle_with_isolation_and_immutable_original(self):
        organization = self.post("/api/v1/organizations", {
            "name": "Groupe scolaire test du parcours complet",
        })
        school = self.post(
            f"/api/v1/organizations/{organization['id']}/schools",
            {"name": "École pilote", "short_name": "YEM"},
        )
        other = self.post(
            f"/api/v1/organizations/{organization['id']}/schools",
            {"name": "École voisine", "short_name": "VOIS"},
        )
        base = f"/api/v1/schools/{school['id']}/"
        other_base = f"/api/v1/schools/{other['id']}/"

        # An organization founder is NOT implicitly authorized to access school records.
        self.assertEqual(self.client.get(base + "students").status_code, 403)
        self.post(base + "members", {"username": "journey-director", "role": "direction"})
        self.switch("journey-director")
        self.post(base + "members", {"username": "journey-teacher", "role": "enseignant"})
        self.assertEqual(self.client.get(other_base + "academic/years").status_code, 403)

        policy = deepcopy(next(x["policy"] for x in PRESETS if x["id"] == "numeric-20"))
        settings = self.post(base + "settings", {
            "scope": {}, "revision": 0,
            "values": {
                "grading": policy,
                "deliberation": {
                    "decisions": [
                        {"code": "admis", "label": "Passage validé"},
                        {"code": "maintien", "label": "Maintien décidé"},
                    ],
                },
            },
        }, expected=200)
        self.assertEqual(settings["revision"], 1)

        year = self.post(base + "academic/years", {
            "code": "2026-2027", "name": "Année 2026–2027",
            "start_date": "2026-09-01", "end_date": "2027-07-31",
        })
        cycle = self.post(base + "academic/cycles", {"code": "primaire", "name": "Primaire"})
        level = self.post(base + "academic/levels", {
            "code": "cm2", "name": "CM2", "cycle": cycle["id"],
        })
        classroom = self.post(base + "academic/classes", {
            "code": "cm2-a", "name": "CM2 A", "year": year["id"],
            "level": level["id"], "capacity": 35,
        })
        period = self.post(base + "academic/periods", {
            "code": "trimestre-1", "name": "Premier trimestre",
            "year": year["id"], "start_date": "2026-09-01", "end_date": "2026-12-31",
        })

        student = self.post(base + "students", {
            "student_code": "YEM-0001", "first_name": "Lina",
            "last_name": "Nkomo", "date_of_birth": "2016-06-15",
        })
        self.post(base + f"students/{student['id']}/guardians", {
            "full_name": "M. Nkomo", "relationship": "Père",
            "phone": "+24100000000", "is_primary": True,
        })
        enrollment = self.post(base + "enrollments", {
            "student": student["id"], "year": year["id"],
            "classroom": classroom["id"], "enrolled_on": "2026-09-15",
            "status": "inscrit",
        })
        staff = self.post(base + "staff", {
            "staff_code": "ENS-001", "first_name": "Marcel", "last_name": "T",
            "position": "enseignant", "username": "journey-teacher",
        })
        assignment = self.post(base + "staff-assignments", {
            "staff": staff["id"], "year": year["id"], "classroom": classroom["id"],
            "duty": "enseignant",
        })

        courses = []
        for code, name, coefficient in [
            ("maths", "Mathématiques", "2"),
            ("francais", "Français", "1"),
        ]:
            subject = self.post(base + "subjects", {"code": code, "name": name})
            course = self.post(base + "courses", {
                "year": year["id"], "classroom": classroom["id"],
                "subject": subject["id"], "coefficient": coefficient,
            })
            self.post(base + f"courses/{course['id']}/instructors", {
                "staff_assignment": assignment["id"],
            })
            courses.append(course)

        # Teacher has delegated write access only to assigned courses.
        self.switch("journey-teacher")
        for course, score in zip(courses, (16, 18)):
            assessment = self.post(base + f"courses/{course['id']}/assessments", {
                "name": "Contrôle continu", "kind": "devoir",
                "assessment_date": "2026-10-12",
                "period": period["id"], "weight": "1",
            })
            roster = self.client.get(base + f"assessments/{assessment['id']}/roster")
            self.assertEqual(roster.status_code, 200)
            self.assertRegex(roster.json()["students"][0]["student_code"], r"^YEM-[0-9A-F]{32}$")
            grade = self.post(base + f"assessments/{assessment['id']}/grades", {
                "enrollment": enrollment["id"], "score": score,
            })
            self.assertEqual(grade["percent"], f"{score * 5:.6f}")
            course["assessment_id"] = assessment["id"]

        self.assertEqual(self.client.get(base + "students").status_code, 403)
        self.switch("journey-director")
        for course in courses:
            self.post(base + f"assessments/{course['assessment_id']}/publish", {
                "revision": 1,
            }, expected=200)
            self.post(base + f"assessments/{course['assessment_id']}/grades", {
                "enrollment": enrollment["id"], "score": 2,
            }, expected=409)

        report = self.post(base + "reports", {
            "enrollment": enrollment["id"], "period": period["id"], "revision": 0,
        })
        self.assertEqual(report["snapshot"]["overall"]["percent"], "83.33")
        self.assertEqual(report["snapshot"]["overall"]["score"], "16.67")
        report_url = base + f"reports/{report['id']}"
        pdf = self.client.get(report_url + "/pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(pdf["Cache-Control"], "private, no-store")
        published = self.post(report_url + "/publish", {"revision": 1}, expected=200)
        self.assertEqual(published["status"], "published")
        original_snapshot = self.client.get(report_url).json()["snapshot"]

        council = self.post(base + "councils", {
            "classroom": classroom["id"], "period": period["id"],
            "title": "Conseil de fin de période",
            "meeting_date": "2026-12-18",
        })
        self.post(base + f"councils/{council['id']}/decisions", {
            "enrollment": enrollment["id"], "report": report["id"],
            "code": "admis", "rationale": "Résultats et délibération examinés.",
            "revision": 0,
        })
        closed = self.post(base + f"councils/{council['id']}/close", {
            "revision": 2,
        }, expected=200)
        self.assertEqual(closed["status"], "closed")
        self.assertEqual(self.client.get(base + f"councils/{council['id']}").json()["decisions"][0]["label"], "Passage validé")

        amended = self.post(report_url + "/amendments", {
            "course": courses[0]["id"], "percent": "100",
            "reason": "Erreur de saisie documentée et validée par la direction.",
            "revision": 0,
        })
        self.assertEqual(amended["snapshot"]["overall"]["percent"], "96.67")
        corrected_pdf = self.client.get(report_url + f"/amendments/{amended['id']}/pdf")
        self.assertEqual(corrected_pdf.status_code, 200)
        self.assertEqual(corrected_pdf["Cache-Control"], "private, no-store")
        self.assertTrue(corrected_pdf.content.startswith(b"%PDF-"))
        self.assertEqual(self.client.get(report_url).json()["snapshot"], original_snapshot)
        self.assertEqual(SchoolReport.objects.count(), 1)
        self.assertEqual(CouncilDecision.objects.count(), 1)
        self.assertEqual(ReportAmendment.objects.count(), 1)

        # Even a member of a different school cannot read sensitive data.
        self.switch("journey-stranger")
        for path in (
            base + f"students/{student['id']}",
            base + f"reports/{report['id']}",
            base + f"reports/{report['id']}/pdf",
            base + f"councils/{council['id']}",
            base + f"reports/{report['id']}/amendments/{amended['id']}/pdf",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404, f"{path} leaked: {response.status_code}")
