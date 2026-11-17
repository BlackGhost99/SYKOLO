"""F7 adversarial acceptance: write attempts hidden inside nominal GETs.

Synthetic test endpoints only; no production URL or data change.
"""
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.test import TestCase, override_settings
from django.urls import path
from django.db import connection
from .models import Organization, School, SchoolMember, SchoolRole
from .subscription_models import PlatformCommercialAccessDecision


def synthetic_read(request, school_id):
    return JsonResponse({"name": School.objects.get(pk=school_id).name})


def synthetic_mutating_read(request, school_id):
    School.objects.filter(pk=school_id).update(name="Mutated by GET")
    return JsonResponse({"unexpected": True})


def synthetic_cte_write(request, school_id):
    # WITH is not necessarily read-only: deny the ambiguous statement.
    table = connection.ops.quote_name(School._meta.db_table)
    id_column = connection.ops.quote_name(School._meta.pk.column)
    with connection.cursor() as cur:
        cur.execute(f"WITH marker AS (SELECT 1) UPDATE {table} SET name=%s WHERE {id_column}=%s",
                    ["CTE mutation", School._meta.pk.get_db_prep_value(school_id, connection)])
    return JsonResponse({"unexpected": True})


urlpatterns = [
    path("api/v1/schools/<uuid:school_id>/f7-read", synthetic_read),
    path("api/v1/schools/<uuid:school_id>/f7-unsafe-get", synthetic_mutating_read),
    path("api/v1/schools/<uuid:school_id>/f7-unsafe-cte", synthetic_cte_write),
]


@override_settings(ROOT_URLCONF=__name__)
class CommercialReadOnlyAcceptance(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="F7 synthetic")
        self.school = School.objects.create(organization=org, name="F7 restricted")
        self.other = School.objects.create(organization=org, name="F7 normal")
        user = get_user_model().objects.create_user(username="f7-staff", password="Test-f7-only-2026!")
        for school in (self.school, self.other):
            role = SchoolRole.objects.create(school=school, code="direction", label="Direction", permissions=["school.view"])
            SchoolMember.objects.create(school=school, user=user, role=role)
        self.client.force_login(user)
        PlatformCommercialAccessDecision.objects.create(school=self.school, revision=1, restricted=True, reason="F7 synthetic")

    def url(self, school, action):
        return f"/api/v1/schools/{school.pk}/{action}"

    def test_ordinary_read_and_hidden_write(self):
        response = self.client.get(self.url(self.school, "f7-read"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "F7 restricted")
        response = self.client.get(self.url(self.school, "f7-unsafe-get"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "commercial_workspace_read_only")
        self.school.refresh_from_db()
        self.assertEqual(self.school.name, "F7 restricted")

    def test_cte_cannot_persist_hidden_write(self):
        # The boundary must reject this even inside a Django TestCase transaction.
        response = self.client.get(self.url(self.school, "f7-unsafe-cte"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "commercial_workspace_read_only")
        self.school.refresh_from_db()
        self.assertEqual(self.school.name, "F7 restricted")

    def test_restriction_is_per_school_and_reactivation_is_effective(self):
        response = self.client.post(self.url(self.school, "f7-read"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["school_id"], str(self.school.pk))
        self.assertEqual(self.client.post(self.url(self.other, "f7-read")).status_code, 200)
        PlatformCommercialAccessDecision.objects.create(school=self.school, revision=2, restricted=False, reason="F7 restored")
        self.assertEqual(self.client.post(self.url(self.school, "f7-read")).status_code, 200)
