from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from .academic_models import AcademicClass, AcademicCycle, AcademicLevel, AcademicYear
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_models import GuardianAccountLink
from .staff_models import StaffAssignment, StaffRecord
from .student_models import Enrollment, Student, StudentGuardian


class PreschoolFollowupTests(TestCase):
    def setUp(self):
        org = Organization.objects.create(name="Recette")
        self.school = School.objects.create(organization=org, name="Groupe test")
        self.year = AcademicYear.objects.create(
            school=self.school, code="2026", name="2026–2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1),
        )
        self.cycle = AcademicCycle.objects.create(school=self.school, code="prescolaire", name="Maternelle")
        level = AcademicLevel.objects.create(school=self.school, cycle=self.cycle, code="creche", name="Crèche")
        self.rooms = [
            AcademicClass.objects.create(school=self.school, year=self.year, level=level, code=code, name=code)
            for code in ("creche-a", "creche-b")
        ]
        self.enrollments = []
        for i, room in enumerate(self.rooms):
            pupil = Student.objects.create(school=self.school, first_name="Enfant", last_name=str(i))
            self.enrollments.append(Enrollment.objects.create(
                school=self.school, student=pupil, year=self.year, classroom=room, enrolled_on=date(2026, 9, 1),
            ))
        role = SchoolRole.objects.create(
            school=self.school, code="enseignant", label="Éducateur", permissions=["school.academic.read"],
        )
        self.user = get_user_model().objects.create_user(username="educateur")
        SchoolMember.objects.create(
            school=self.school, role=role, user=self.user, access_cycle_ids=[str(self.cycle.pk)],
        )
        staff = StaffRecord.objects.create(
            school=self.school, account=self.user, staff_code="educateur", first_name="Test", last_name="Test",
        )
        self.assignment = StaffAssignment.objects.create(
            school=self.school, staff=staff, year=self.year, classroom=self.rooms[0],
        )
        self.client.force_login(self.user)
        self.url = f"/api/v1/schools/{self.school.pk}/academic/preschool-followup"
        self.day = "2026-10-01"
        self.payload = {"classroom": str(self.rooms[0].pk), "day": self.day,
                        "enrollment": str(self.enrollments[0].pk), "revision": 0,
                        "observation": "A participé à la lecture."}

    def save(self, **changes):
        return self.client.post(self.url, {**self.payload, **changes}, content_type="application/json")

    def test_scope_and_revision(self):
        rooms = self.client.get(self.url, {"year": self.year.pk}).json()["classrooms"]
        self.assertEqual([room["id"] for room in rooms], [str(self.rooms[0].pk)])
        self.assertEqual(self.client.get(self.url, {"classroom": self.rooms[1].pk, "day": self.day}).status_code, 404)
        self.assertEqual(self.save(enrollment=str(self.enrollments[1].pk)).status_code, 404)
        other = School.objects.create(organization=self.school.organization, name="Autre école")
        foreign_url = self.url.replace(str(self.school.pk), str(other.pk))
        self.assertEqual(self.client.get(foreign_url, {"year": self.year.pk}).status_code, 404)
        self.assertEqual(self.save(day="2025-10-01").status_code, 422)
        self.assertEqual(self.save().status_code, 201)
        self.assertEqual(self.save().status_code, 409)
        self.assertEqual(self.save(revision=1, observation="A choisi un livre.").status_code, 200)
        result = self.client.get(self.url, {"classroom": self.rooms[0].pk, "day": self.day}).json()
        self.assertEqual(result["students"][0]["observation"], "A choisi un livre.")
        self.assertEqual(result["students"][0]["revision"], 2)
        self.assignment.active = False
        self.assignment.save(update_fields=["active"])
        self.assertEqual(self.save(revision=2).status_code, 404)

    def test_closed_year_is_read_only(self):
        self.assertEqual(self.save().status_code, 201)
        self.year.status = AcademicYear.STATUS_CLOSED
        self.year.active = False
        self.year.save(update_fields=["status", "active"])
        result = self.client.get(self.url, {"classroom": self.rooms[0].pk, "day": self.day}).json()
        self.assertFalse(result["editable"])
        self.assertEqual(len(result["students"]), 1)
        self.assertEqual(self.save(revision=1).status_code, 409)


    def test_transfer_retains_previous_observation_as_read_only(self):
        self.assertEqual(self.save().status_code, 201)
        enrollment = self.enrollments[0]
        enrollment.classroom = self.rooms[1]
        enrollment.save(update_fields=["classroom"])
        result = self.client.get(self.url, {"classroom": self.rooms[0].pk, "day": self.day}).json()
        self.assertEqual(result["students"][0]["observation"], self.payload["observation"])
        self.assertFalse(result["students"][0]["current"])
        self.assertEqual(self.save(revision=1).status_code, 404)

    def action(self, action, **fields):
        return self.client.post(self.url, {
            "action": action, "classroom": str(self.rooms[0].pk), "day": self.day, **fields,
        }, content_type="application/json")

    def test_reference_is_level_scoped_and_marks_are_versioned(self):
        self.assertEqual(self.action("reference", label="Écouter une histoire").status_code, 403)
        director = get_user_model().objects.create_user(username="direction")
        role = SchoolRole.objects.create(
            school=self.school, code="direction", label="Direction",
            permissions=["school.academic.read", "school.academic.manage"],
        )
        SchoolMember.objects.create(school=self.school, role=role, user=director)
        self.client.force_login(director)
        reference = self.action("reference", label="Écouter une histoire")
        self.assertEqual(reference.status_code, 201, reference.content)
        self.client.force_login(self.user)
        fields = {"enrollment": str(self.enrollments[0].pk), "competency": reference.json()["id"],
                  "stage": "developing", "revision": 0}
        self.assertEqual(self.action("mark", **fields).status_code, 201)
        self.assertEqual(self.action("mark", **fields).status_code, 409)
        self.assertEqual(self.action("mark", **{**fields, "stage": "unknown"}).status_code, 422)
        result = self.client.get(self.url, {"classroom": self.rooms[0].pk, "day": self.day}).json()
        self.assertEqual(result["students"][0]["marks"][0]["stage"], "developing")
        self.assertEqual(result["competencies"][0]["label"], "Écouter une histoire")

    def test_liaison_only_shares_publications_with_verified_guardian(self):
        self.assertEqual(self.save(observation="Note interne").status_code, 201)
        entry = self.action("liaison", enrollment=str(self.enrollments[0].pk), message="Lecture vendredi.")
        self.assertEqual(entry.status_code, 201, entry.content)
        replay = self.action("liaison", enrollment=str(self.enrollments[0].pk), message="Lecture vendredi.")
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(replay.json()["id"], entry.json()["id"])
        parent = get_user_model().objects.create_user(username="parent")
        role = SchoolRole.objects.create(school=self.school, code="parent", label="Parent", permissions=["school.view"])
        SchoolMember.objects.create(school=self.school, role=role, user=parent)
        first_child, second_child = (row.student for row in self.enrollments)
        guardian = StudentGuardian.objects.create(school=self.school, student=first_child, full_name="Parent un")
        link = GuardianAccountLink.objects.create(school=self.school, guardian=guardian, user=parent)
        self.client.force_login(parent)
        def url(child):
            return f"/api/v1/parents/children/{child.pk}/liaison"
        response = self.client.get(url(first_child), {"year": self.year.pk})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item["message"] for item in response.json()["messages"]], ["Lecture vendredi."])
        self.assertNotContains(response, "Note interne")
        self.assertEqual(self.client.get(url(second_child)).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"year": self.year.pk}).status_code, 403)
        link.active = False
        link.save(update_fields=["active"])
        self.assertEqual(self.client.get(url(first_child)).status_code, 404)
