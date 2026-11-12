"""Regression and authorization coverage for YEM parent self-service admissions."""
import base64
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .admission_models import AdmissionApplication
from .models import Organization, School, SchoolMember, SchoolRole
from .parent_admission_models import FamilyChild, ParentAdmissionRequest, SchoolPublicListing
from .parent_models import GuardianAccountLink
from .services import ROLE_TEMPLATES
from .student_models import Student, StudentGuardian


class FamilyDiscoveryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user("discovery-director", password="test-Strong-director-2026!")
        self.parent = User.objects.create_user("discovery-parent", password="test-Strong-parent-2026!", first_name="Eliane", last_name="N.")
        self.other_parent = User.objects.create_user("discovery-other", password="test-Strong-other-2026!")
        org = Organization.objects.create(name="Organisation tests YEM")
        self.school = School.objects.create(organization=org, name="École du quartier", school_type="primaire", education_cycles=["primaire"])
        self.other_school = School.objects.create(organization=org, name="École non publiée")
        for school in (self.school, self.other_school):
            for code, label, permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school, code=code, label=label, permissions=permissions)
        SchoolMember.objects.create(school=self.school, user=self.director,
            role=SchoolRole.objects.get(school=self.school, code="direction"))
        self.year = AcademicYear.objects.create(school=self.school, code="2026-27", name="2026/2027",
            start_date="2026-09-01", end_date="2027-07-31")
        cycle = AcademicCycle.objects.create(school=self.school, code="primaire", name="Primaire")
        level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="ce1", name="CE1")
        self.classroom = AcademicClass.objects.create(school=self.school, year=self.year,
            level=level, code="ce1a", name="CE1 A", capacity=1)
        self.client = Client(enforce_csrf_checks=True)

    def login(self, who):
        self.client.force_login(who)
        self.csrf = self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self, path, data):
        return self.client.post("/api/v1/" + path, data=json.dumps(data),
                                content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def setup_listing(self):
        self.login(self.director)
        response = self.post(f"schools/{self.school.pk}/parent-listing", {
            "revision": 0, "published": True, "city": "Libreville", "district": "Nombakélé",
            "description": "École avec admission configurable", "contact_phone": "+241 00 00 00 00",
            "cash_at_school": True,
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def create_child(self):
        response = self.post("parents/family-children", {
            "first_name": "Aïcha", "last_name": "Mavoungou", "date_of_birth": "2018-01-17",
        })
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["id"]

    def application(self, child_id, **changes):
        body = {
            "child": child_id, "classroom": str(self.classroom.pk),
            "route": "direct", "payment_choice": "cash",
            "guardian_relationship": "Mère", "guardian_phone": "+241 0600",
            "origin_school": "", "route_reference": "",
        }
        body.update(changes)
        return self.post("parents/applications", body)

    def test_parent_profile_photo_is_private_and_editable(self):
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        path = "/api/v1/parents/family-children/" + child_id
        payload = {
            "revision": 1, "first_name": "Aïcha", "last_name": "Mavoungou",
            "date_of_birth": "2018-01-17",
            "profile": {"gender": "F", "nationality": "Gabonaise",
                        "address": "Libreville, Nombakélé"},
        }
        changed = self.client.put(path, data=json.dumps(payload), content_type="application/json",
                                  HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()["revision"], 2)
        self.assertEqual(changed.json()["profile"]["gender"], "F")
        # Deliberately tiny JPEG-like fixture: upload route verifies content and MIME, no public URL.
        encoded = base64.b64encode(b"\\xff\\xd8\\xff" + b"YEM JPG fixture").decode()
        photo = self.post("parents/family-children/" + child_id + "/photo",
                          {"photo": "data:image/jpeg;base64," + encoded})
        self.assertEqual(photo.status_code, 200, photo.content)
        uri = photo.json()["photo_url"]
        response = self.client.get(uri)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertTrue(response.content.startswith(b"\\xff\\xd8\\xff"))
        self.login(self.other_parent)
        self.assertEqual(self.client.get(uri).status_code, 404)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.put(path, data=json.dumps(payload),
                    content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf).status_code, 404)

    def test_school_defined_questions_and_document_upload_need_staff_verification(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .enrollment_form import default_config
        from .student_models import EnrollmentFormConfig
        from .admission_models import AdmissionDocument

        self.setup_listing()
        config = default_config()
        config["custom_fields"] = [{"key": "transport", "label": "Transport scolaire",
            "type": "select", "options": ["Oui", "Non"], "required": True, "section": "eleve"}]
        config["documents"] = [
            {"key": "acte_naissance", "label": "Acte de naissance", "required": True},
            {"key": "photo_identite", "label": "Photo d'identité", "required": False},
        ]
        EnrollmentFormConfig.objects.create(school=self.school, config=config)
        self.login(self.parent)
        child_id = self.create_child()
        path = f"/api/v1/parents/admission-form?classroom={self.classroom.pk}&route=direct"
        result = self.client.get(path)
        self.assertEqual(result.status_code, 200, result.content)
        form = result.json()
        self.assertTrue(form["configured"])
        self.assertIn("acte_naissance", [d["key"] for d in form["documents"] if d["required"]])
        self.assertEqual(form["custom_fields"][0]["label"], "Transport scolaire")
        missing = self.application(child_id, form_revision=form["revision"])
        self.assertEqual(missing.status_code, 422, missing.content)
        request = self.application(child_id, form_revision=form["revision"],
                                   custom_answers={"transport": "Oui"},
                                   form_fields={"nationality": "Gabonaise"})
        self.assertEqual(request.status_code, 201, request.content)
        item_id = request.json()["id"]
        saved = ParentAdmissionRequest.objects.get(pk=item_id)
        self.assertEqual(saved.form_data["custom_fields"]["transport"], "Oui")
        self.assertIn("acte_naissance", saved.application.required_documents)
        doc_list_url = f"/api/v1/parents/applications/{item_id}/documents"
        self.assertEqual(self.client.get(doc_list_url).json()["documents"][0]["status"], "missing")
        file = SimpleUploadedFile("acte.pdf", b"%PDF-1.7\\nYEM test PDF", content_type="application/pdf")
        upload = self.client.post(doc_list_url+"/acte_naissance", {"file":file},
                                  HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(upload.status_code, 200, upload.content)
        document = AdmissionDocument.objects.get(application=saved.application, code="acte_naissance")
        self.assertEqual(document.status, "pending")
        self.assertTrue(self.client.get(doc_list_url+"/acte_naissance/file").content.startswith(b"%PDF-"))
        self.assertEqual(self.client.get(doc_list_url).json()["documents"][0]["status"], "pending")
        self.login(self.other_parent)
        self.assertEqual(self.client.get(doc_list_url).status_code, 404)
        self.assertEqual(self.client.get(doc_list_url+"/acte_naissance/file").status_code, 404)
        self.login(self.director)
        school_doc_url = f"/api/v1/schools/{self.school.pk}/admissions/{saved.application_id}/documents/acte_naissance/file"
        self.assertEqual(self.client.get(school_doc_url).status_code, 200)
        detail = self.client.get(f"/api/v1/schools/{self.school.pk}/admissions/{saved.application_id}")
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()["parent_submission"]["form_data"]["custom_fields"]["transport"], "Oui")

    def test_school_form_revision_stale_submission_is_rejected(self):
        from .student_models import EnrollmentFormConfig
        from .enrollment_form import default_config
        self.setup_listing()
        EnrollmentFormConfig.objects.create(school=self.school, config=default_config(), revision=2)
        self.login(self.parent)
        child_id = self.create_child()
        old = self.application(child_id, form_revision=1)
        self.assertEqual(old.status_code, 409, old.content)
        self.assertFalse(ParentAdmissionRequest.objects.exists())

    def test_directory_is_opt_in_and_public_only(self):
        anon = Client()
        self.assertEqual(anon.get("/api/v1/parents/catalog").json()["schools"], [])
        self.setup_listing()
        response = anon.get("/api/v1/parents/catalog")
        self.assertEqual(response.status_code, 200)
        school = response.json()["schools"][0]
        self.assertEqual(school["name"], self.school.name)
        self.assertEqual(school["city"], "Libreville")
        self.assertEqual(school["school_type"], "primaire")
        self.assertEqual(school["education_cycles"], ["primaire"])
        self.assertEqual(school["classes"][0]["remaining"], 1)
        self.assertFalse(school["online_payment_available"])
        self.assertEqual(len(response.json()["schools"]), 1)

    def test_archived_class_or_track_cannot_be_selected_by_parent(self):
        from .academic_models import AcademicTrack
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        anon = Client()
        catalog = anon.get("/api/v1/parents/catalog").json()
        self.assertEqual(len(catalog["schools"][0]["classes"]), 1)

        self.login(self.director)
        response = self.client.patch(
            f"/api/v1/schools/{self.school.pk}/academic/classes/{self.classroom.pk}",
            data=json.dumps({"revision": self.classroom.revision, "active": False}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(anon.get("/api/v1/parents/catalog").json()["schools"][0]["classes"], [])
        self.login(self.parent)
        self.assertEqual(self.application(child_id).status_code, 404)

        self.login(self.director)
        response = self.client.patch(
            f"/api/v1/schools/{self.school.pk}/academic/classes/{self.classroom.pk}",
            data=json.dumps({"revision": response.json()["revision"], "active": True}),
            content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(anon.get("/api/v1/parents/catalog").json()["schools"][0]["classes"]), 1)

        track = AcademicTrack.objects.create(
            school=self.school, level=self.classroom.level,
            code="option-a", name="Option expérimentale", active=False,
        )
        self.classroom.track = track
        self.classroom.save(update_fields=["track"])
        self.assertEqual(anon.get("/api/v1/parents/catalog").json()["schools"][0]["classes"], [])
        self.login(self.parent)
        self.assertEqual(self.application(child_id).status_code, 404)

    def test_family_submission_uses_existing_private_admissions(self):
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        response = self.application(child_id)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["child_name"], "Aïcha Mavoungou")
        self.assertEqual(response.json()["payment_status"], "a_regler_sur_place")
        self.assertEqual(AdmissionApplication.objects.count(), 1)
        app = AdmissionApplication.objects.first()
        self.assertEqual(app.source, "parent_mobile")
        self.assertEqual(app.submitted_by, self.parent)
        self.assertEqual(app.status, "submitted")
        self.assertEqual(ParentAdmissionRequest.objects.first().child_id.hex,
                         child_id.replace("-", ""))
        self.assertEqual(GuardianAccountLink.objects.count(), 0)
        self.assertEqual(self.application(child_id).status_code, 409)
        result = self.client.get("/api/v1/parents/applications").json()
        self.assertEqual(len(result["applications"]), 1)
        self.assertEqual(result["applications"][0]["school_name"], self.school.name)
        self.assertEqual(result["applications"][0]["child_name"], "Aïcha Mavoungou")
        self.login(self.director)
        staff = self.client.get(f"/api/v1/schools/{self.school.pk}/admissions")
        self.assertEqual(len(staff.json()["applications"]), 1)

    def test_verified_transfer_keeps_matricule_without_granting_school_access(self):
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        self.assertEqual(self.application(child_id).status_code, 201)
        source = AdmissionApplication.objects.get(school=self.school)
        source.status = "accepted"
        source.save(update_fields=["status"])
        self.login(self.director)
        # Test historical school-transfer logic with an independently approved
        # admission-fee waiver. No cash payment or receipt is manufactured.
        grant = self.post(f"schools/{self.school.pk}/admissions/{source.pk}/scholarship", {
            "action": "approve", "coverage": "all", "revision": 0,
            "reference": "ETAT-RECETTE-TRANSFERT-2026",
        })
        self.assertEqual(grant.status_code, 201, grant.content)
        payload = {"revision": 1, "enrolled_on": "2026-10-03"}
        response = self.post(f"schools/{self.school.pk}/admissions/{source.pk}/convert", payload)
        self.assertEqual(response.status_code, 201, response.content)
        original = Student.objects.get(school=self.school)

        year = AcademicYear.objects.create(school=self.other_school, code="2026", name="2026",
            start_date=self.year.start_date, end_date=self.year.end_date)
        cycle = AcademicCycle.objects.create(school=self.other_school, code="primaire", name="Primaire")
        level = AcademicLevel.objects.create(school=self.other_school, cycle=cycle, code="ce1", name="CE1")
        classroom = AcademicClass.objects.create(school=self.other_school, year=year, level=level,
            code="ce1a", name="CE1 A")
        SchoolPublicListing.objects.create(school=self.other_school, published=True, cash_at_school=True)
        self.login(self.parent)
        result = self.application(child_id, classroom=str(classroom.pk))
        self.assertEqual(result.status_code, 201, result.content)
        target = AdmissionApplication.objects.get(school=self.other_school)
        target.status = "accepted"
        target.save(update_fields=["status"])
        SchoolMember.objects.create(school=self.other_school, user=self.director,
            role=SchoolRole.objects.get(school=self.other_school, code="direction"))
        self.login(self.director)
        url = f"schools/{self.other_school.pk}/admissions/{target.pk}/convert"
        self.assertEqual(self.post(url, payload).status_code, 422)
        self.assertFalse(Student.objects.filter(school=self.other_school).exists())
        SchoolMember.objects.create(school=self.school, user=self.parent,
            role=SchoolRole.objects.get(school=self.school, code="parent"))
        GuardianAccountLink.objects.create(school=self.school, user=self.parent,
            guardian=StudentGuardian.objects.get(student=original), verified_by=self.director)
        response = self.post(url, payload)
        self.assertEqual(response.status_code, 201, response.content)
        transferred = Student.objects.get(school=self.other_school)
        self.assertNotEqual(original.pk, transferred.pk)
        self.assertEqual(original.matricule_yem, transferred.matricule_yem)

        lookup = f"/api/v1/schools/{self.other_school.pk}/students?matricule={original.matricule_yem.lower()}"
        self.assertEqual([row["id"] for row in self.client.get(lookup).json()["students"]], [str(transferred.pk)])
        self.login(self.parent)
        self.assertEqual(self.client.get(lookup).status_code, 404)
        self.assertEqual(len(self.client.get("/api/v1/parents/children").json()["children"]), 1)

    def test_other_account_cannot_access_child_or_application(self):
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        self.assertEqual(self.application(child_id).status_code, 201)
        self.login(self.other_parent)
        self.assertEqual(self.application(child_id).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/parents/family-children").json()["children"], [])
        self.assertEqual(self.client.get("/api/v1/parents/applications").json()["applications"], [])
        # The other parent cannot infer even the name of an applicant's child.
        self.assertNotIn("Aïcha Mavoungou", self.client.get("/api/v1/parents/applications").content.decode())
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/parent-listing").status_code, 404)

    def test_online_payment_cannot_be_faked_and_closed_school_rejects_submission(self):
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        self.assertEqual(self.application(child_id, payment_choice="online").status_code, 409)
        self.assertEqual(AdmissionApplication.objects.count(), 0)
        listing = SchoolPublicListing.objects.get(school=self.school)
        listing.published = False
        listing.save()
        self.assertEqual(self.application(child_id).status_code, 404)

    def test_no_available_places_is_not_an_admission(self):
        self.setup_listing()
        self.login(self.parent)
        child_id = self.create_child()
        # A submitted dossier does not reserve a place.
        self.assertEqual(self.application(child_id).status_code, 201)
        self.assertEqual(self.client.get("/api/v1/parents/catalog").json()["schools"][0]["classes"][0]["remaining"], 1)

    def test_publication_requires_school_manager_and_revision(self):
        self.setup_listing()
        self.login(self.parent)
        response = self.post(f"schools/{self.school.pk}/parent-listing", {
            "revision": 1, "published": False, "city": "X", "district": "",
            "description": "", "contact_phone": "", "cash_at_school": True,
        })
        self.assertEqual(response.status_code, 404)
        self.login(self.director)
        same = self.post(f"schools/{self.school.pk}/parent-listing", {
            "revision": 0, "published": False, "city": "", "district": "",
            "description": "", "contact_phone": "", "cash_at_school": True,
        })
        self.assertEqual(same.status_code, 409)

    def test_csrf_required_for_mutations(self):
        self.setup_listing()
        self.login(self.parent)
        response = self.client.post("/api/v1/parents/family-children",
            data=json.dumps({"first_name":"A","last_name":"B","date_of_birth":None}),
            content_type="application/json")
        self.assertEqual(response.status_code, 403)
