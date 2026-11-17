import json
from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from .academic_models import AcademicYear, AcademicCycle, AcademicLevel, AcademicClass
from .models import Organization, OrganizationMember, School, PlatformAudit, SchoolMember, SchoolRole
from .student_models import Student, Enrollment
from .subscription_models import PlatformSubscription, PlatformSubscriptionPayment
from .finance_models import FeePayment
from .subscription_views import quote_lines
from .subscription_pricing import calculate_terms, DEFAULT_RATES, DEFAULT_MINIMUMS
from unittest.mock import patch


class PlatformSubscriptionTests(TestCase):
    def setUp(self):
        clock = patch('institutions.subscription_views.timezone.localdate', return_value=date(2026, 11, 17))
        clock.start()
        self.addCleanup(clock.stop)
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(username="billing", email="billing@example.test", password="Test-billing-2026!")
        self.ordinary = user_model.objects.create_user(username="staff", email="staff@example.test", password="Test-staff-2026!")
        self.client.force_login(self.admin)
        self.mfa()
        org = Organization.objects.create(name="Complexe test")
        self.school = School.objects.create(organization=org, name="Complexe", school_type="groupe_scolaire",
            education_cycles=["prescolaire", "primaire", "college"])
        self.other = School.objects.create(organization=org, name="Autre")
        self.year = AcademicYear.objects.create(school=self.school, code="2026", name="2026–2027",
            start_date=date(2026,9,1), end_date=date(2027,7,31), status="current")
        self.foreign_year = AcademicYear.objects.create(school=self.other, code="2026", name="2026–2027",
            start_date=date(2026,9,1), end_date=date(2027,7,31), status="current")
        self.path = f"/api/v1/platform/schools/{self.school.pk}/subscriptions"
        self.counts = {"prescolaire":1, "primaire":2, "college":3}
        self.rates = {"prescolaire":1000, "primaire":1500, "college":2000}
        for code, count in self.counts.items():
            cycle = AcademicCycle.objects.create(school=self.school, code=code, name=code)
            level = AcademicLevel.objects.create(school=self.school, cycle=cycle, code="test", name="Test")
            room = AcademicClass.objects.create(school=self.school, year=self.year, level=level, code=code, name=code)
            for i in range(count):
                student = Student.objects.create(school=self.school, student_code=f"{code}-{i}", first_name="Test", last_name="Élève")
                Enrollment.objects.create(school=self.school, student=student, year=self.year, classroom=room, enrolled_on=date(2026,9,12))

    def mfa(self):
        session = self.client.session
        session["mfa_verified"] = True
        session.save()

    def post(self, action, **kwargs):
        payload = {"action": action, "year_id": str(self.year.pk), **kwargs}
        return self.client.post(self.path, json.dumps(payload), content_type="application/json")

    def issue(self, **kwargs):
        return self.post("issue", **({"policy_revision":1,"expected_counts":self.counts,"reason":"Contrat test","period":"annuel","discount_xaf":0,"include_setup":False,"expected_total_xaf":100000} | kwargs))

    def test_commercial_documents_use_frozen_terms_and_private_ledger(self):
        from .subscription_document_pdf import invoice_lines
        result = self.issue(period="mensuel", discount_xaf=3, include_setup=True,
                            expected_total_xaf=149997)
        self.assertEqual(result.status_code, 201, result.content)
        sub = PlatformSubscription.objects.get()
        items, schedule = invoice_lines(sub)
        self.assertEqual(sum(amount for _, amount in items), 149997)
        self.assertIn(("Remise commerciale", -3), items)
        self.assertEqual(sum(s["amount_xaf"] for s in schedule), 149997)
        self.assertEqual(len(schedule), 13)
        documents = result.json()["subscription"]["documents"]
        invoice = documents["invoice"]["url"]
        audit_count = PlatformAudit.objects.count()
        first = self.client.get(invoice)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertTrue(first.content.startswith(b"%PDF-"))
        self.assertIn("private", first["Cache-Control"])
        self.assertIn("no-store", first["Cache-Control"])
        self.assertEqual(first["X-YEM-Document-Reference"], documents["invoice"]["reference"])
        self.assertTrue(first["Content-Disposition"].startswith("attachment;"))
        self.assertTrue(self.client.get(invoice + "?preview=1")["Content-Disposition"].startswith("inline;"))
        self.assertEqual(PlatformAudit.objects.count(), audit_count)
        self.assertEqual(PlatformSubscriptionPayment.objects.count(), 0)
        self.assertEqual(self.client.post(invoice, {}).status_code, 405)
        # Live tariff/roster do not rewrite historical amounts.
        Enrollment.objects.filter(school=self.school).update(active=False)
        updated = dict(DEFAULT_RATES, primaire=1600)
        self.assertEqual(self.client.post("/api/v1/platform/subscription-pricing",
            json.dumps({"rates": updated, "minimums": DEFAULT_MINIMUMS,
                        "revision": 1, "reason": "Nouvelle grille"}), content_type="application/json").status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(invoice_lines(sub), (items, schedule))
        payment = self.post("payment", reference="F2-REC", amount_xaf=10000,
                            method="mobile_money", reason="Règlement déclaré")
        self.assertEqual(payment.status_code, 201, payment.content)
        receipt = payment.json()["subscription"]["documents"]["receipts"][0]
        pdf = self.client.get(receipt["url"])
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF-"))
        self.assertEqual(pdf["X-YEM-Document-Reference"], receipt["reference"])
        self.assertEqual(pdf["X-YEM-Document-Status"], "issued")
        self.assertEqual(self.post("void", payment_id=receipt["id"], reason="Erreur documentée").status_code, 200)
        voided = self.client.get(receipt["url"])
        self.assertEqual(voided.status_code, 200)
        self.assertEqual(voided["X-YEM-Document-Status"], "voided")
        self.assertEqual(voided["X-YEM-Document-Reference"], receipt["reference"])
        self.assertNotEqual(pdf.content, voided.content)
        self.assertEqual(PlatformSubscriptionPayment.objects.count(), 1)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_commercial_document_mfa_and_school_scope(self):
        result = self.issue()
        invoice = result.json()["subscription"]["documents"]["invoice"]["url"]
        payment = self.post("payment", reference="F2-PRIVATE", amount_xaf=3000,
                            method="especes", reason="Justificatif privé")
        receipt = payment.json()["subscription"]["documents"]["receipts"][0]["url"]
        foreign = PlatformSubscription.objects.create(year=self.foreign_year, total_xaf=2000,
            lines=[{"cycle":"college","label":"Collège","students":1,"rate_xaf":2000,"amount_xaf":2000}])
        foreign_payment = PlatformSubscriptionPayment.objects.create(subscription=foreign,
            reference="FOREIGN", amount_xaf=1000, method="especes")
        self.assertEqual(self.client.get(invoice.replace(str(self.school.pk), str(self.other.pk))).status_code, 404)
        self.assertEqual(self.client.get(receipt.rsplit("/", 2)[0] + f"/{foreign_payment.pk}/receipt").status_code, 404)
        session = self.client.session
        session["mfa_verified"] = False
        session.save()
        self.assertEqual(self.client.get(invoice).status_code, 403)
        self.client.force_login(self.ordinary)
        self.assertEqual(self.client.get(invoice).status_code, 403)
        direction = SchoolRole.objects.create(school=self.school, code="direction", label="Direction",
                                              permissions=["school.view"])
        member = SchoolMember.objects.create(school=self.school, user=self.ordinary, role=direction)
        school_root = f"/api/v1/schools/{self.school.pk}/owner/subscriptions"
        summary = self.client.get(school_root).json()["subscriptions"][0]
        doc = summary["documents"]["invoice"]["url"]
        rec = summary["documents"]["receipts"][0]["url"]
        self.assertNotIn("payments", summary)
        self.assertNotIn("void_reason", summary["documents"]["receipts"][0])
        self.assertEqual(self.client.get(doc).status_code, 200)
        self.assertEqual(self.client.get(rec).status_code, 200)
        self.assertEqual(self.client.post(doc,{}).status_code, 405)
        self.assertEqual(self.client.get(doc.replace(str(self.school.pk),str(self.other.pk))).status_code, 403)
        self.assertEqual(self.client.get(doc.replace(f"/{summary['id']}/",f"/{foreign.pk}/")).status_code, 404)
        member.access_cycle_ids = []
        member.save(update_fields=["access_cycle_ids"])
        self.assertEqual(self.client.get(doc).status_code, 403)
        teacher = SchoolRole.objects.create(school=self.school, code="enseignant", label="Professeur",
                                            permissions=["school.view"])
        member.role = teacher
        member.access_cycle_ids = None
        member.save(update_fields=["role", "access_cycle_ids"])
        self.assertEqual(self.client.get(doc).status_code, 403)
        self.assertEqual(self.client.get(rec).status_code, 403)
        self.client.logout()
        self.assertIn(self.client.get(doc).status_code, (401,403,404))

    def test_legacy_contract_pdf_without_schedule_or_repricing(self):
        from .subscription_document_pdf import invoice_lines
        row = PlatformSubscription.objects.create(year=self.year, total_xaf=1500,
            lines=[{"cycle":"primaire","label":"Primaire","students":1,"rate_xaf":1500,"amount_xaf":1500}])
        self.assertEqual(invoice_lines(row)[1], [])
        self.assertEqual(self.client.get(self.path + f"/{row.pk}/invoice").status_code, 200)
        row.total_xaf = 1501
        row.save(update_fields=["total_xaf"])
        self.assertEqual(self.client.get(self.path + f"/{row.pk}/invoice").status_code, 409)

    def test_commercial_reminders_automatic_thresholds_partial_payment_and_void(self):
        from datetime import timedelta
        from .family_notification_models import SchoolFamilyNotification
        self.assertEqual(self.issue(period="mensuel").status_code, 201)
        root = "/api/v1/platform/subscription-reminders"
        today = date(2026, 11, 17)
        row = PlatformSubscription.objects.get()
        for offset, stage in [(-8, None), (-7, "soon"), (-1, "soon"), (0, "due"),
                              (1, "late"), (7, "late_7"), (30, "late_30")]:
            with self.subTest(offset=offset), patch("institutions.subscription_reminders.timezone.localdate",
                                                    return_value=today+timedelta(days=offset)):
                response = self.client.get(root)
                self.assertEqual(response.status_code, 200, response.content)
                first = next((r for r in response.json()["reminders"] if r["number"] == 1), None)
                self.assertEqual(first["stage"] if first else None, stage)
                if first:
                    self.assertEqual(first["id"], f"{row.pk}:abonnement:1:2026-11-17")
                    self.assertEqual(first["balance_xaf"], 8334)
        response = self.post("payment", reference="F3-PART", amount_xaf=3000, method="especes", reason="Versement")
        self.assertEqual(response.status_code, 201, response.content)
        result = self.client.get(root).json()
        self.assertEqual(result["reminders"][0]["balance_xaf"], 5334)
        self.assertEqual(result["count"], 1)
        self.assertEqual(self.client.get(root).json(), result)
        second = self.post("payment", reference="F3-END", amount_xaf=5334, method="especes", reason="Complément")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(self.client.get(root).json()["count"], 0)
        payment_id = second.json()["subscription"]["payments"][-1]["id"]
        self.assertEqual(self.post("void", payment_id=payment_id, reason="Erreur de saisie").status_code, 200)
        result = self.client.get(root).json()
        self.assertEqual(result["reminders"][0]["balance_xaf"], 5334)
        self.assertEqual(result["due_count"], 1)
        audit_count = PlatformAudit.objects.count()
        self.assertEqual(self.client.get(root+"?page=999").json()["page"], 1)
        self.assertEqual(self.client.get(root+"?page=-1").status_code, 422)
        self.assertEqual(self.client.post(root, {}).status_code, 405)
        self.assertEqual(PlatformAudit.objects.count(), audit_count)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(SchoolFamilyNotification.objects.count(), 0)

    def test_commercial_reminders_school_isolation_and_mfa(self):
        self.assertEqual(self.issue().status_code, 201)
        PlatformSubscription.objects.create(year=self.foreign_year, total_xaf=2000, lines=[])
        root = "/api/v1/platform/subscription-reminders"
        central = self.client.get(root).json()
        self.assertEqual(central["count"], 1)
        self.assertEqual(central["missing_schedule_count"], 1)
        session = self.client.session
        session["mfa_verified"] = False
        session.save()
        self.assertEqual(self.client.get(root).status_code, 403)
        self.client.force_login(self.ordinary)
        url = f"/api/v1/schools/{self.school.pk}/owner/subscription-reminders"
        self.assertEqual(self.client.get(url).status_code, 403)
        role = SchoolRole.objects.create(school=self.school, code="direction", label="Direction", permissions=["school.view"])
        member = SchoolMember.objects.create(school=self.school, user=self.ordinary, role=role)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reminders"], central["reminders"])
        self.assertEqual(response.json()["missing_schedule_count"], 0)
        self.assertEqual(self.client.get(url.replace(str(self.school.pk), str(self.other.pk))).status_code, 403)
        self.assertEqual(self.client.get(root).status_code, 403)
        member.access_cycle_ids = []
        member.save(update_fields=["access_cycle_ids"])
        self.assertEqual(self.client.get(url).status_code, 403)
        role.code = "enseignant"
        role.save(update_fields=["code"])
        member.access_cycle_ids = None
        member.save(update_fields=["access_cycle_ids"])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_trial_is_explicit_unique_free_and_never_auto_converted(self):
        from .subscription_models import PlatformSubscriptionTrial
        self.assertEqual(self.post("trial_start", days=91, reason="Essai").status_code, 409)
        result = self.post("trial_start", days=30, reason="Essai commercial")
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.json()["trial"]["status"], "active")
        self.assertEqual(result.json()["trial"]["ends_before"], "2026-12-17")
        self.assertEqual(PlatformSubscriptionTrial.objects.count(), 1)
        self.assertEqual(PlatformSubscription.objects.count(), 0)
        self.assertEqual(self.post("trial_start", days=30, reason="Double").status_code, 409)
        with patch("institutions.subscription_views.timezone.localdate", return_value=date(2026,12,17)):
            self.assertEqual(self.post("quote").json()["trial"]["status"], "expired")
            self.assertEqual(PlatformSubscription.objects.count(), 0)
            self.school.refresh_from_db()
            self.assertTrue(self.school.is_active)
            issued = self.issue()
            self.assertEqual(issued.status_code, 201, issued.content)
            self.assertEqual(issued.json()["trial"]["status"], "converted")
            self.assertEqual(issued.json()["subscription"]["schedule"][0]["due_date"], "2026-12-17")
        self.assertEqual(PlatformSubscriptionPayment.objects.count(), 0)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_amendment_proration_absorbs_minimum_and_keeps_original_invoice(self):
        from .subscription_document_pdf import invoice_lines
        from .subscription_models import PlatformSubscriptionAmendment
        self.assertEqual(self.issue(period="mensuel").status_code, 201)
        row = PlatformSubscription.objects.get()
        original = invoice_lines(row)
        room = AcademicClass.objects.get(school=self.school, year=self.year, level__cycle__code="college")
        def add(number, offset):
            for i in range(offset, offset+number):
                student = Student.objects.create(school=self.school, student_code=f"F4-{i}", first_name="Test", last_name="Ajout")
                Enrollment.objects.create(school=self.school, student=student, year=self.year, classroom=room, enrolled_on=date(2026,11,17))
        add(1, 0)
        quote = self.post("amendment_quote").json()["amendment"]
        self.assertEqual(quote["gross_prorata_xaf"], 2000)
        self.assertEqual(quote["amount_xaf"], 0)
        self.assertEqual(self.post("amendment_issue", expected=quote, reason="Effectif couvert").status_code, 201)
        self.assertEqual(self.post("amendment_issue", expected=quote, reason="Rejeu").status_code, 409)
        add(45, 1)
        second = self.post("amendment_quote").json()["amendment"]
        self.assertEqual(second["minimum_absorbed_xaf"], 88000)
        self.assertEqual(second["amount_xaf"], 2000)
        result = self.post("amendment_issue", expected=second, reason="Effectif complémentaire")
        self.assertEqual(result.status_code, 201, result.content)
        sub = result.json()["subscription"]
        self.assertEqual(sub["original_total_xaf"], 100000)
        self.assertEqual(sub["total_xaf"], 102000)
        self.assertEqual(sum(s["amount_xaf"] for s in sub["schedule"]), 102000)
        self.assertEqual(len([s for s in sub["schedule"] if s["kind"]=="abonnement"]), 12)
        row.refresh_from_db()
        self.assertEqual(row.total_xaf, 100000)
        self.assertEqual(invoice_lines(row), original)
        self.assertEqual(PlatformSubscriptionAmendment.objects.count(), 2)
        amendment = sub["documents"]["amendments"][-1]
        self.assertTrue(self.client.get(amendment["url"]).content.startswith(b"%PDF-"))
        self.assertEqual(self.client.get(amendment["url"].replace(str(self.school.pk),str(self.other.pk))).status_code, 404)
        reminders = self.client.get("/api/v1/platform/subscription-reminders").json()["reminders"]
        self.assertEqual([r["balance_xaf"] for r in reminders if r["kind"]=="avenant"], [2000])
        with patch("institutions.subscription_views.timezone.localdate", return_value=date(2026,12,17)):
            add(1, 46)
            third = self.post("amendment_quote").json()["amendment"]
            self.assertEqual(third["remaining_days"], 335)
            self.assertEqual(third["amount_xaf"], 1836)
            self.assertEqual(self.post("amendment_issue", expected=third, reason="Prorata").status_code, 201)
        # A decrease/replacement of already billed capacity does not recharge.
        Enrollment.objects.filter(school=self.school, student__student_code__startswith="F4-").update(active=False)
        with patch("institutions.subscription_views.timezone.localdate", return_value=date(2026,12,17)):
            empty = self.post("amendment_quote").json()["amendment"]
            self.assertEqual(empty["additions"], [])
            self.assertEqual(self.post("amendment_issue", expected=empty, reason="Pas d’ajout").status_code, 409)
        self.assertEqual(self.post("payment", reference="F4-FULL", amount_xaf=103836, method="especes", reason="Test").status_code, 201)
        self.assertEqual(self.post("quote").json()["subscription"]["balance_xaf"], 0)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_trial_amendments_remain_platform_only_and_school_reads_scoped(self):
        self.assertEqual(self.issue().status_code, 201)
        self.assertEqual(self.post("trial_start",days=30,reason="Déjà abonné").status_code, 409)
        self.client.force_login(self.ordinary)
        direction = SchoolRole.objects.create(school=self.school, code="direction", label="Direction", permissions=["school.view"])
        SchoolMember.objects.create(school=self.school, user=self.ordinary, role=direction)
        self.assertEqual(self.post("amendment_quote").status_code, 403)
        self.assertEqual(self.post("trial_start",days=30,reason="Non autorisé").status_code, 403)
        data = self.client.get(f"/api/v1/schools/{self.school.pk}/owner/subscriptions").json()
        self.assertEqual(data["subscriptions"][0]["amendments"], [])
        self.assertNotIn("payments", data["subscriptions"][0])

    def test_commercial_expiration_restriction_and_manual_restoration(self):
        from .subscription_models import PlatformCommercialAccessDecision
        self.assertEqual(self.issue(period="mensuel").status_code, 201)
        url = f"/api/v1/platform/schools/{self.school.pk}/commercial-access"
        school_url = f"/api/v1/schools/{self.school.pk}/owner/commercial-access"
        def decide(restricted, revision, reason="Décision documentée"):
            return self.client.post(url, json.dumps({"restricted":restricted,"revision":revision,"reason":reason}), content_type="application/json")
        status = self.client.get(url).json()
        self.assertEqual(status["lifecycle"], "active")
        self.assertFalse(status["restricted"])
        self.assertFalse(status["can_restrict"])
        self.assertEqual(decide(True,0).status_code,409)
        with patch("institutions.subscription_views.timezone.localdate", return_value=date(2026,12,16)):
            status = self.client.get(url).json()
            self.assertFalse(status["can_restrict"])
            self.assertEqual(status["grace_days_remaining"],1)
            self.assertEqual(decide(True,0).status_code,409)
        with patch("institutions.subscription_views.timezone.localdate", return_value=date(2026,12,17)):
            status = self.client.get(url).json()
            self.assertTrue(status["can_restrict"])
            self.assertEqual(status["late_30_xaf"],8334)
            self.assertFalse(status["restricted"])
            result = decide(True,0)
            self.assertEqual(result.status_code,201,result.content)
            self.assertTrue(result.json()["restricted"])
            self.assertEqual(decide(True,0).status_code,409)
            self.assertEqual(decide(False,0).status_code,409)
        self.school.refresh_from_db()
        self.assertTrue(self.school.is_active)
        self.assertEqual(PlatformCommercialAccessDecision.objects.count(),1)
        self.client.force_login(self.ordinary)
        role = SchoolRole.objects.create(school=self.school,code="direction",label="Direction",permissions=["school.view"])
        SchoolMember.objects.create(school=self.school,user=self.ordinary,role=role)
        self.assertTrue(self.client.get(school_url).json()["restricted"])
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(school_url,{},content_type="application/json").status_code,403)
        self.assertTrue(self.client.get(f"/api/v1/schools/{self.school.pk}/my-access").json()["commercial_workspace_restricted"])
        for suffix in ("students","enrollments","reports","attendance/sessions","finance/payments","staff","owner/overview","academic/years","notification-inbox"):
            response = self.client.get(f"/api/v1/schools/{self.school.pk}/{suffix}")
            self.assertEqual(response.status_code,403,suffix)
            self.assertEqual(response.json()["code"],"commercial_workspace_restricted",suffix)
        blocked = self.client.post(f"/api/v1/schools/{self.school.pk}/academic/quick-classes",{},content_type="application/json")
        self.assertEqual(blocked.status_code,403)
        self.assertEqual(blocked.json()["code"],"commercial_workspace_restricted")
        blocked_staff = self.client.post(f"/api/v1/schools/{self.school.pk}/staff/onboard",{},content_type="application/json")
        self.assertEqual(blocked_staff.json()["code"],"commercial_workspace_restricted")
        self.assertEqual(self.client.get(f"/api/v1/schools/{self.school.pk}/owner/subscriptions").status_code,200)
        self.assertEqual(self.client.get(school_url.replace(str(self.school.pk),str(self.other.pk))).status_code,403)
        self.client.force_login(self.admin)
        self.mfa()
        self.assertEqual(self.post("payment",reference="F5-PAY",amount_xaf=100000,method="especes",reason="Règlement test").status_code,201)
        self.assertTrue(self.client.get(url).json()["restricted"])
        self.assertEqual(decide(False,1).status_code,201)
        self.assertFalse(self.client.get(url).json()["restricted"])
        self.assertEqual(PlatformCommercialAccessDecision.objects.count(),2)
        self.client.force_login(self.ordinary)
        restored = self.client.post(f"/api/v1/schools/{self.school.pk}/academic/quick-classes",{},content_type="application/json")
        self.assertNotEqual(restored.json().get("code"),"commercial_workspace_restricted")
        self.assertEqual(FeePayment.objects.count(),0)

    def test_commercial_trial_expiration_is_read_only(self):
        from .subscription_models import PlatformCommercialAccessDecision
        self.assertEqual(self.post("trial_start",days=30,reason="Essai").status_code,201)
        url = f"/api/v1/platform/schools/{self.school.pk}/commercial-access"
        self.assertEqual(self.client.get(url).json()["lifecycle"],"trial_active")
        with patch("institutions.subscription_views.timezone.localdate",return_value=date(2026,12,17)):
            status = self.client.get(url).json()
            self.assertEqual(status["lifecycle"],"expired")
            self.assertFalse(status["restricted"])
            self.assertFalse(status["can_restrict"])
            self.assertEqual(status["grace_days_remaining"],30)
        with patch("institutions.subscription_views.timezone.localdate",return_value=date(2027,1,16)):
            self.assertTrue(self.client.get(url).json()["can_restrict"])
        self.assertEqual(PlatformCommercialAccessDecision.objects.count(),0)
        self.assertEqual(PlatformSubscription.objects.count(),0)
        self.school.refresh_from_db()
        self.assertTrue(self.school.is_active)

    def test_quote_uses_real_counts_and_snapshot(self):
        self.assertEqual(self.client.get(self.path).json()["suggested_year"], str(self.year.pk))
        quote = self.post("quote")
        self.assertEqual(quote.status_code, 200)
        self.assertEqual(quote.json()["counts"], self.counts)
        self.assertEqual(quote.json()["rates"], self.rates)
        self.assertEqual(PlatformSubscription.objects.count(), 0)
        result = self.issue()
        self.assertEqual(result.status_code, 201, result.content)
        self.assertEqual(result.json()["subscription"]["total_xaf"], 100000)
        self.assertEqual(self.issue().status_code, 409)
        Enrollment.objects.filter(school=self.school, classroom__level__cycle__code="college").update(active=False)
        self.assertEqual(self.post("quote").json()["subscription"]["total_xaf"], 100000)
        self.assertEqual(FeePayment.objects.count(), 0)

    def test_payment_idempotence_overpayment_and_void(self):
        self.assertEqual(self.issue().status_code, 201)
        values = {"reference":"X-1", "amount_xaf":3000, "method":"especes", "reason":"Justificatif"}
        self.assertEqual(self.post("payment", **values).status_code, 201)
        self.assertEqual(self.post("payment", **values).status_code, 200)
        self.assertEqual(self.post("payment", **{**values,"amount_xaf":4000}).status_code, 409)
        self.assertEqual(self.post("payment", **{**values,"reference":"X-2","amount_xaf":98000}).status_code, 409)
        self.assertEqual(PlatformSubscriptionPayment.objects.count(), 1)
        payment = PlatformSubscriptionPayment.objects.get()
        result = self.post("void", payment_id=payment.pk, reason="Erreur de saisie")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["subscription"]["balance_xaf"], 100000)
        self.assertEqual(self.post("payment", **values).status_code, 409)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(PlatformAudit.objects.filter(event__startswith="subscription_").count(), 3)

    def test_wrong_year_permissions_and_stale_quote(self):
        self.assertEqual(self.post("quote", year_id=str(self.foreign_year.pk)).status_code, 404)
        self.assertEqual(self.issue(expected_counts={"college":3}).status_code, 409)
        self.client.force_login(self.ordinary)
        self.mfa()
        self.assertEqual(self.client.get(self.path).status_code, 403)
        self.assertEqual(self.post("quote").status_code, 403)
        self.assertEqual(PlatformSubscription.objects.count(), 0)

    def test_rates_validated_zero_and_unknown(self):
        with self.assertRaises(ValueError):
            quote_lines({"college":2}, {"college":True})
        with self.assertRaises(ValueError):
            quote_lines({"unknown":3}, {})
        self.assertEqual(quote_lines({"college":2}, {"college":0})[0]["amount_xaf"], 0)
        rows = quote_lines({"primaire":4,"college":2}, {"primaire":1250,"college":2300})
        self.assertEqual(sum(r["amount_xaf"] for r in rows), 9600)

    def test_actual_cycle_prices_and_one_minimum(self):
        quote=self.post("quote").json()
        self.assertEqual(quote["terms"]["gross_xaf"],10000)
        self.assertEqual(quote["terms"]["minimum_xaf"],100000)
        self.assertEqual(quote["terms"]["minimum_adjustment_xaf"],90000)
        result=self.issue(period="trimestriel",discount_xaf=3,include_setup=True,expected_total_xaf=149997)
        self.assertEqual(result.status_code,201,result.content)
        sub=result.json()["subscription"]
        self.assertEqual(sub["terms"]["annual_xaf"],99997)
        self.assertEqual(sum(x["amount_xaf"] for x in sub["schedule"]),149997)
        self.assertEqual([x["amount_xaf"] for x in sub["schedule"]],[50000,25000,24999,24999,24999])
        self.assertEqual(sub["schedule"][1]["due_date"],"2026-11-17")
        self.assertEqual(sub["schedule"][2]["due_date"],"2027-02-17")
        self.assertEqual(FeePayment.objects.count(),0)

    def test_global_policy_revision_and_existing_contract_immutable(self):
        url="/api/v1/platform/subscription-pricing"
        self.assertEqual(self.client.get(url).json()["rates"],DEFAULT_RATES)
        self.assertEqual(self.issue().status_code,201)
        updated=dict(DEFAULT_RATES,primaire=1600)
        data={"rates":updated,"minimums":DEFAULT_MINIMUMS,"revision":1,"reason":"Révision commerciale"}
        r=self.client.post(url,json.dumps(data),content_type="application/json")
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(r.json()["revision"],2)
        self.assertEqual(self.client.post(url,json.dumps(data),content_type="application/json").status_code,409)
        self.assertEqual(self.post("quote").json()["subscription"]["total_xaf"],100000)
        self.assertEqual(PlatformSubscription.objects.get().lines[1]["rate_xaf"],1500)

    def test_stale_total_and_revision_refused_without_contract(self):
        self.assertEqual(self.issue(expected_total_xaf=99999).status_code,409)
        self.assertEqual(self.issue(policy_revision=99).status_code,409)
        self.assertEqual(PlatformSubscription.objects.count(),0)

    def test_complex_example(self):
        counts={"prescolaire":80,"primaire":200,"college":250,"lycee_general":150}
        terms=calculate_terms(counts,{k:DEFAULT_RATES[k] for k in counts},DEFAULT_MINIMUMS,
                              period="trimestriel",first_due=date(2026,9,1))
        self.assertEqual(terms["annual_xaf"],1180000)
        self.assertEqual([r["amount_xaf"] for r in terms["schedule"]],[295000]*4)

    def test_owner_only_read_of_own_contract(self):
        self.assertEqual(self.issue().status_code,201)
        url=f"/api/v1/schools/{self.school.pk}/owner/subscriptions"
        self.client.force_login(self.ordinary)
        self.mfa()
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.get("/api/v1/platform/subscription-pricing").status_code,403)
        OrganizationMember.objects.create(organization=self.school.organization,user=self.ordinary,role="founder")
        r=self.client.get(url)
        self.assertEqual(r.status_code,200,r.content)
        row=r.json()["subscriptions"][0]
        self.assertEqual(row["total_xaf"],100000)
        self.assertNotIn("payments",row)
        self.assertEqual(self.client.post(url,{},content_type="application/json").status_code,405)
        other=School.objects.create(organization=Organization.objects.create(name="École indépendante"),name="Indépendante")
        self.assertEqual(self.client.get(f"/api/v1/schools/{other.pk}/owner/subscriptions").status_code,403)

    def test_monthly_exact_rounding_calendar_and_shared_balance(self):
        # Twelve monthly instalments; calendar clamps correctly for short months.
        terms=calculate_terms({"primaire":1},{"primaire":1500},DEFAULT_MINIMUMS,
            period="mensuel",discount=1,first_due=date(2027,1,31))
        self.assertEqual(len(terms["schedule"]),12)
        self.assertEqual(sum(x["amount_xaf"] for x in terms["schedule"]),74999)
        self.assertEqual([x["due_date"] for x in terms["schedule"][:3]],["2027-01-31","2027-02-28","2027-03-31"])
        result=self.issue(period="mensuel",expected_total_xaf=100000)
        self.assertEqual(result.status_code,201,result.content)
        sub=result.json()["subscription"]
        self.assertEqual(sub["terms"]["period"],"mensuel")
        self.assertEqual([s["amount_xaf"] for s in sub["schedule"]],[8334]*4+[8333]*8)
        self.assertEqual(sub["schedule"][-1]["due_date"],"2027-10-17")
        payment=self.post("payment",reference="MENS-1",amount_xaf=10000,method="especes",reason="Versement déclaré")
        self.assertEqual(payment.status_code,201,payment.content)
        issued=payment.json()["subscription"]
        self.assertEqual(issued["schedule"][0]["balance_xaf"],0)
        self.assertEqual(issued["schedule"][1]["balance_xaf"],6668)
        direction=SchoolRole.objects.create(school=self.school,code="direction",label="Direction",permissions=["school.view"])
        member=SchoolMember.objects.create(school=self.school,user=self.ordinary,role=direction)
        self.client.force_login(self.ordinary)
        url=f"/api/v1/schools/{self.school.pk}/owner/subscriptions"
        school_response=self.client.get(url)
        self.assertEqual(school_response.status_code,200,school_response.content)
        shared=school_response.json()["subscriptions"][0]
        for key in ("total_xaf","paid_xaf","balance_xaf","terms","schedule"):
            self.assertEqual(issued[key],shared[key])
        self.assertNotIn("payments",shared)
        self.assertEqual(self.client.get(self.path).status_code,403)
        member.access_cycle_ids=[]
        member.save(update_fields=["access_cycle_ids"])
        self.assertEqual(self.client.get(url).status_code,403)
        teacher=SchoolRole.objects.create(school=self.school,code="enseignant",label="Enseignant",permissions=["school.view"])
        member.role=teacher
        member.access_cycle_ids=None
        member.save(update_fields=["role","access_cycle_ids"])
        self.assertEqual(self.client.get(url).status_code,403)

    def test_principal_proviseur_direction_read_only_and_teacher_denied(self):
        self.assertEqual(self.issue(period="mensuel").status_code, 201)
        url=f"/api/v1/schools/{self.school.pk}/owner/subscriptions"
        for role_code in ("direction", "principal", "proviseur"):
            school_role=SchoolRole.objects.create(
                school=self.school, code=role_code, label=role_code, permissions=["school.view"])
            SchoolMember.objects.update_or_create(
                school=self.school, user=self.ordinary, defaults={"role":school_role,"active":True,"access_cycle_ids":None})
            self.client.force_login(self.ordinary)
            response=self.client.get(url)
            self.assertEqual(response.status_code, 200, (role_code,response.content))
            self.assertEqual(response.json()["subscriptions"][0]["terms"]["period"], "mensuel")
            self.assertEqual(self.client.get(self.path).status_code, 403)
        teacher=SchoolRole.objects.create(
            school=self.school,code="enseignant",label="Enseignant",permissions=["school.view"])
        SchoolMember.objects.filter(school=self.school,user=self.ordinary).update(role=teacher)
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.get("/api/v1/platform/subscription-pricing").status_code,403)

    def test_enrollment_changes_requote_before_contract_and_unknown_cycle_blocked(self):
        first=self.post("quote").json()
        self.assertEqual(first["counts"]["primaire"],2)
        cycle=AcademicCycle.objects.get(school=self.school,code="primaire")
        classroom=AcademicClass.objects.get(school=self.school,year=self.year,level__cycle=cycle)
        student=Student.objects.create(school=self.school,student_code="NOUVEAU",first_name="A",last_name="B")
        Enrollment.objects.create(school=self.school,year=self.year,student=student,
            classroom=classroom,enrolled_on=date(2026,10,2))
        revised=self.post("quote").json()
        self.assertEqual(revised["counts"]["primaire"],3)
        self.assertEqual(self.issue(expected_counts=first["counts"]).status_code,409)
        self.assertEqual(PlatformSubscription.objects.count(),0)
        # An enrolled but undeclared cycle must never silently enter the commercial quote.
        invalid_cycle=AcademicCycle.objects.create(school=self.school,code="lycee_general",name="Lycée")
        level=AcademicLevel.objects.create(school=self.school,cycle=invalid_cycle,code="terminale",name="Terminale")
        room=AcademicClass.objects.create(school=self.school,year=self.year,level=level,code="terminale",name="Terminale")
        pupil=Student.objects.create(school=self.school,student_code="LYCEE-1",first_name="C",last_name="D")
        Enrollment.objects.create(school=self.school,year=self.year,student=pupil,
            classroom=room,enrolled_on=date(2026,10,3))
        self.assertEqual(self.post("quote").status_code,409)
