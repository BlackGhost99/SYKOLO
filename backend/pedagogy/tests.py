import json
from copy import deepcopy
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase, Client, override_settings
from django.db import DatabaseError
from .domain import evaluate, validate_policy, ValidationError
from .views import PRESETS


def get(id="numeric-20"):
    return deepcopy(next(p["policy"] for p in PRESETS if p["id"] == id))


class PolicyTests(SimpleTestCase):
    def test_all_editable_presets(self):
        for p in PRESETS:
            with self.subTest(p=p["id"]):
                self.assertEqual(validate_policy(p["policy"]), p["policy"])

    def test_arbitrary_numeric_scales_and_weights(self):
        for maximum in [10, 15, 20, 100, 37]:
            p = get()
            p["scale"]["max"] = maximum
            with self.subTest(maximum=maximum):
                r = evaluate(
                    p,
                    [
                        {"score": maximum / 2, "weight": 1},
                        {"score": maximum, "weight": 3},
                    ],
                )
                self.assertEqual(r["percent"], 87.5)
                self.assertEqual(r["label"], "Très bien")

    def test_percentage(self):
        self.assertEqual(
            evaluate(get("percentage"), [{"score": 75, "weight": 1}])["score"], 75
        )

    def test_letter_equivalences_are_configurable(self):
        p = get("letters")
        es = [{"score": "A", "weight": 1}, {"score": "B", "weight": 1}]
        self.assertEqual(evaluate(p, es)["label"], "B")
        p["bands"][1]["value"] = 74
        self.assertEqual(evaluate(p, es)["label"], "A")

    def test_competency_and_appreciation(self):
        for id in ["competency", "appreciation"]:
            p = get(id)
            label = p["bands"][2]["label"]
            with self.subTest(id=id):
                self.assertEqual(
                    evaluate(p, [{"score": label, "weight": 1}])["label"], label
                )

    def test_absence_strategies(self):
        p = get()
        es = [{"score": None, "weight": 1}, {"score": 16, "weight": 1}]
        self.assertEqual(evaluate(p, es)["score"], 16)
        p["missing"] = "zero"
        self.assertEqual(evaluate(p, es)["score"], 8)

    def test_all_absent_is_empty(self):
        self.assertEqual(
            evaluate(get(), [{"score": None, "weight": 1}])["status"], "empty"
        )

    def test_boundary_and_unsorted_bands(self):
        p = get()
        p["bands"].reverse()
        for score, label in [(0, "À renforcer"), (14, "Bien"), (20, "Très bien")]:
            with self.subTest(score=score):
                self.assertEqual(
                    evaluate(p, [{"score": score, "weight": 1}])["label"], label
                )

    def test_decimal_rounding_does_not_affect_thresholds(self):
        p = get()
        p["precision"] = 0
        p["notification"]["enabled"] = True
        p["notification"]["below"] = 70
        result = evaluate(p, [{"score": 13.99, "weight": 1}])
        self.assertEqual(result["score"], 14)
        self.assertEqual(result["label"], "Satisfaisant")
        self.assertIsNotNone(result["notification"])
        self.assertIsNone(evaluate(p, [{"score": 14, "weight": 1}])["notification"])

    def test_json_roundtrip(self):
        p = get("letters")
        es = [{"score": "A+", "weight": 2}]
        self.assertEqual(evaluate(json.loads(json.dumps(p)), es), evaluate(p, es))

    def test_invalid_configurations(self):
        mutations = [
            lambda p: p.update(schemaVersion=2),
            lambda p: p["scale"].update(max=0),
            lambda p: p["bands"][0].update(min=1),
            lambda p: p["bands"][1].update(min=0),
            lambda p: p["bands"].__setitem__(0, None),
            lambda p: p["bands"][0].update(value=90),
            lambda p: p["bands"][1].update(label=p["bands"][0]["label"]),
            lambda p: p.update(report={"showScore": False, "showLabel": False}),
            lambda p: p.update(precision=1.5),
            lambda p: p["notification"].update(below=101),
        ]
        for i, mutate in enumerate(mutations):
            p = get()
            mutate(p)
            with self.subTest(i=i), self.assertRaises(ValidationError):
                validate_policy(p)

    def test_invalid_scores_and_weights(self):
        for score in [-1, 21, 10**1000, float("nan"), float("inf"), "12", True, {}]:
            with self.subTest(score=score), self.assertRaises(ValidationError):
                evaluate(get(), [{"score": score, "weight": 1}])
        for weight in [0, -1, True, None]:
            with self.subTest(weight=weight), self.assertRaises(ValidationError):
                evaluate(get(), [{"score": 10, "weight": weight}])
        with self.assertRaises(ValidationError):
            evaluate(get(), [])


class ApiTests(SimpleTestCase):
    def post(self, path, data):
        return self.client.post(
            path, data=json.dumps(data), content_type="application/json"
        )

    def test_api_calculation(self):
        response = self.post(
            "/api/v1/evaluate",
            {"policy": get(), "entries": [{"score": 15, "weight": 1}]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"], 15)

    def test_validation_contract(self):
        self.assertEqual(self.post("/api/v1/policies/validate", get()).status_code, 200)
        self.assertEqual(self.post("/api/v1/policies/validate", {}).status_code, 422)
        self.assertEqual(self.post("/api/v1/evaluate", []).status_code, 422)

    def test_json_and_size_rejections(self):
        self.assertEqual(
            self.client.post(
                "/api/v1/evaluate", data="{", content_type="application/json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/evaluate", data="NaN", content_type="application/json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/evaluate", data="{}", content_type="text/plain"
            ).status_code,
            415,
        )
        self.assertEqual(
            self.post("/api/v1/policies/validate", {"x": "x" * 70000}).status_code, 413
        )

    def test_schema_errors_never_leak_traceback(self):
        for data in [
            None,
            0,
            [],
            {"schemaVersion": 1, "name": "test", "scale": {"kind": [], "max": 20}},
            {
                "schemaVersion": 1,
                "name": "test",
                "scale": {"kind": "numeric", "max": 20},
                "precision": 2,
                "missing": [],
            },
        ]:
            with self.subTest(data=data):
                self.assertEqual(
                    self.post("/api/v1/policies/validate", data).status_code, 422
                )

    def test_presets_and_security_headers(self):
        response = self.client.get("/api/v1/presets")
        self.assertEqual(len(response.json()), 8)
        self.assertIn("csrftoken", response.cookies)
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(
                "/api/v1/policies/validate",
                data=json.dumps(get()),
                content_type="application/json",
            ).status_code,
            403,
        )
        token = client.get("/api/v1/presets").cookies["csrftoken"].value
        self.assertEqual(
            client.post(
                "/api/v1/policies/validate",
                data=json.dumps(get()),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            200,
        )

    def test_private_files_unreachable(self):
        for path in [
            "/.git/config",
            "/backend/config/settings.py",
            "/.env",
            "/unknown",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_method_allowlist(self):
        self.assertEqual(self.client.delete("/api/v1/presets").status_code, 405)
        self.assertEqual(self.client.get("/api/v1/evaluate").status_code, 405)

    def test_health_commit_and_environment(self):
        with patch.dict("os.environ", {"RENDER_GIT_COMMIT": "abc123"}):
            response = self.client.get("/healthz")
            self.assertEqual(response.json()["commit"], "abc123")
            self.assertEqual(response.json()["stack"]["api"], "django")

    def test_readiness_failure_is_unavailable(self):
        with patch("pedagogy.views.connection") as database:
            database.cursor.side_effect = DatabaseError
            self.assertEqual(self.client.get("/readyz").status_code, 503)

    @override_settings(ALLOWED_HOSTS=["sykolo.example.test"])
    def test_host_validation(self):
        self.assertEqual(
            self.client.get("/healthz", HTTP_HOST="evil.example").status_code, 400
        )


class DatabaseTests(TestCase):
    def test_database_readiness(self):
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    def test_custom_user_migration_and_password_hash(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="foundation-test", password="A-valid-test-password-932"
        )
        self.assertNotEqual(user.password, "A-valid-test-password-932")
        self.assertTrue(user.check_password("A-valid-test-password-932"))
