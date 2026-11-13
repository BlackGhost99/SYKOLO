"""Payroll ledger: independent approval, partial settlements, privacy and school isolation."""
import json
import uuid
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from .academic_models import AcademicYear
from .models import Organization, School, SchoolAudit, SchoolMember, SchoolRole
from .payroll_models import StaffPayDisbursement, StaffPayRun
from .services import ROLE_TEMPLATES
from .staff_models import StaffRecord


class PayrollLedgerTests(TestCase):
    def setUp(self):
        User=get_user_model()
        org=Organization.objects.create(name="Groupe paie fictif TEST")
        self.school=School.objects.create(organization=org,name="Lycée TEST - salariés",
                                          school_type="lycee_general",education_cycles=["lycee_general"])
        self.other=School.objects.create(organization=org,name="École étrangère TEST",
                                         school_type="lycee_general",education_cycles=["lycee_general"])
        for school in (self.school,self.other):
            for code,label,permissions in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=list(permissions))
        self.users={}
        for code in ("direction","comptabilite","econome","enseignant","secretariat","parent"):
            user=User.objects.create_user(username="paie-"+code,password="test-paies-yem-2026!")
            SchoolMember.objects.create(school=self.school,user=user,
              role=SchoolRole.objects.get(school=self.school,code=code))
            self.users[code]=user
        self.stranger=User.objects.create_user(username="paie-stranger",password="test-paies-yem-2026!")
        self.year=AcademicYear.objects.create(school=self.school,code="2026-2027",
           name="2026-2027",start_date="2026-09-01",end_date="2027-07-31",status="current")
        self.other_year=AcademicYear.objects.create(school=self.other,code="2026-2027",
           name="2026-2027",start_date="2026-09-01",end_date="2027-07-31",status="current")
        self.staff=StaffRecord.objects.create(school=self.school,account=self.users["enseignant"],
            staff_code="P-TEST-001",first_name="Mathilde",last_name="FICTIVE",
            position="Professeure de mathématiques")
        self.cashier_record=StaffRecord.objects.create(school=self.school,account=self.users["econome"],
            staff_code="P-TEST-002",first_name="Agent",last_name="CAISSE",position="Économe")
        self.other_staff=StaffRecord.objects.create(school=self.other,staff_code="P-EXTERNE",
            first_name="Inconnu",last_name="TEST",position="Agent externe")
        self.client=Client(enforce_csrf_checks=True)
        self.root=f"/api/v1/schools/{self.school.pk}/payroll/"
        self.login("comptabilite")

    def login(self,role):
        user=self.users[role] if isinstance(role,str) and role in self.users else role
        self.client.force_login(user)
        self.csrf=self.client.get("/api/v1/auth/csrf").cookies["csrftoken"].value

    def post(self,path,data):
        return self.client.post(self.root+path,data=json.dumps(data),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def patch(self,path,data):
        return self.client.patch(self.root+path,data=json.dumps(data),
            content_type="application/json",HTTP_X_CSRFTOKEN=self.csrf)

    def prepare(self,**overrides):
        payload={"staff":str(self.staff.pk),"year":str(self.year.pk),
            "period":"2026-11-01","basis":"monthly","gross_amount":"120000.00",
            "deductions":"20000.00","currency":"XAF","note":"Traitement novembre TEST"}
        payload.update(overrides)
        return self.post("runs",payload)

    def pay(self,run_id,amount="40000.00",idem=None,**overrides):
        data={"amount":amount,"method":"especes","reference":"PAIE-TEST-2026",
              "paid_on":"2026-11-12","idempotency_key":idem or str(uuid.uuid4())}
        data.update(overrides)
        return self.post(f"runs/{run_id}/payments",data)

    def approve(self,run_id,revision=1):
        return self.post(f"runs/{run_id}/approve",{"revision":revision})

    def test_salary_privacy_and_role_separation(self):
        self.assertEqual(self.client.get("staff").status_code,200)
        self.assertEqual(self.client.get("runs").status_code,200)
        self.assertEqual(self.prepare().status_code,201)
        self.login("enseignant")
        self.assertEqual(self.client.get("runs").status_code,403)
        self.assertEqual(self.client.get("staff").status_code,403)
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.school.pk}/staff/{self.staff.pk}/dossier"
        ).status_code,403)
        self.login("secretariat")
        self.assertEqual(self.client.get("runs").status_code,403)
        # Secretariat can read the professional dossier but must never see salary.
        result=self.client.get(f"/api/v1/schools/{self.school.pk}/staff/{self.staff.pk}/dossier")
        self.assertEqual(result.status_code,200,result.content)
        self.assertNotIn("gross_amount",str(result.json()))
        self.assertNotIn("payroll",str(result.json()))
        self.login("parent")
        self.assertEqual(self.client.get("runs").status_code,403)
        self.login("direction")
        self.assertEqual(self.client.get("runs").status_code,200)
        self.assertEqual(self.prepare().status_code,403)
        self.login("econome")
        self.assertEqual(self.client.get("runs").status_code,200)
        self.assertEqual(self.prepare().status_code,403)
        self.login(self.stranger)
        self.assertEqual(self.client.get("runs").status_code,404)

    def test_independent_approval_then_partial_declared_payments(self):
        created=self.prepare()
        self.assertEqual(created.status_code,201,created.content)
        row=created.json()
        self.assertEqual(row["status"],"draft")
        self.assertEqual(row["gross_amount"],"120000.00")
        self.assertEqual(row["net_amount"],"100000.00")
        self.assertEqual(row["balance"],"100000.00")
        self.assertEqual(self.approve(row["id"]).status_code,403)
        self.login("econome")
        self.assertEqual(self.pay(row["id"]).status_code,409)
        self.login("direction")
        approved=self.approve(row["id"])
        self.assertEqual(approved.status_code,200,approved.content)
        self.assertEqual(approved.json()["status"],"approved")
        self.assertEqual(self.approve(row["id"],revision=1).status_code,409)
        self.login("econome")
        key=str(uuid.uuid4())
        paid=self.pay(row["id"],idem=key)
        self.assertEqual(paid.status_code,201,paid.content)
        same=self.pay(row["id"],idem=key)
        self.assertEqual(same.status_code,200,same.content)
        self.assertEqual(same.json()["id"],paid.json()["id"])
        self.assertEqual(self.pay(row["id"],amount="50000.00",idem=key).status_code,409)
        self.assertEqual(self.pay(row["id"],amount="60000.01").status_code,409)
        detail=self.client.get("runs/"+row["id"])
        self.assertEqual(detail.status_code,200,detail.content)
        self.assertEqual(detail.json()["run"]["paid"],"40000.00")
        self.assertEqual(detail.json()["run"]["balance"],"60000.00")
        self.assertEqual(detail.json()["run"]["status"],"partially_paid")
        self.assertEqual(self.pay(row["id"],amount="60000.00").status_code,201)
        self.assertEqual(self.client.get("runs/"+row["id"]).json()["run"]["status"],"paid")
        self.assertEqual(StaffPayDisbursement.objects.filter(school=self.school).count(),2)
        self.assertEqual(self.pay(row["id"],amount="1.00").status_code,409)
        # Audit entries must not expose salary amounts; do not mix with tuition.
        self.assertFalse(any("120000" in str(a.details) or "40000" in str(a.details)
            for a in SchoolAudit.objects.filter(school=self.school)))
        self.assertTrue(SchoolAudit.objects.filter(event="staff_pay_run_approved").exists())
        self.assertTrue(SchoolAudit.objects.filter(event="staff_pay_disbursed").exists())

    def test_revocation_independent_and_no_deleted_financial_history(self):
        row=self.prepare().json()
        self.login("direction")
        self.assertEqual(self.approve(row["id"]).status_code,200)
        self.login("econome")
        payment=self.pay(row["id"]).json()
        member=SchoolMember.objects.get(school=self.school,user=self.users["econome"])
        member.additional_roles.add(SchoolRole.objects.get(school=self.school,code="comptabilite"))
        self.assertEqual(self.post("payments/"+payment["id"]+"/void",{
            "reason":"Annulation après double contrôle"
        }).status_code,403)
        self.login("comptabilite")
        voided=self.post("payments/"+payment["id"]+"/void",{
            "reason":"Montant erroné vérifié par le contrôleur"
        })
        self.assertEqual(voided.status_code,200,voided.content)
        self.assertTrue(voided.json()["voided"])
        self.assertEqual(self.client.get("runs/"+row["id"]).json()["run"]["balance"],"100000.00")
        self.assertEqual(self.post("payments/"+payment["id"]+"/void",{
            "reason":"Tentative de second remboursement"
        }).status_code,409)
        self.assertEqual(StaffPayDisbursement.objects.count(),1)

    def test_version_updates_and_protection_closed_year(self):
        row=self.prepare().json()
        updated=self.patch("runs/"+row["id"],{
            "revision":1,"gross_amount":"140000.00","deductions":"10000.00",
        })
        self.assertEqual(updated.status_code,200,updated.content)
        self.assertEqual(updated.json()["net_amount"],"130000.00")
        self.assertEqual(self.patch("runs/"+row["id"],{
            "revision":1,"note":"Modification obsolète",
        }).status_code,409)
        self.login("direction")
        self.assertEqual(self.approve(row["id"],revision=1).status_code,409)
        self.assertEqual(self.approve(row["id"],revision=2).status_code,200)
        self.login("comptabilite")
        self.assertEqual(self.patch("runs/"+row["id"],{
            "revision":3,"deductions":"8000.00",
        }).status_code,409)
        self.year.status="closed"
        self.year.save(update_fields=["status"])
        self.assertEqual(self.prepare(period="2027-01-01").status_code,409)
        self.login("econome")
        self.assertEqual(self.pay(row["id"]).status_code,409)

    def test_another_school_invalid_dates_and_self_pay_blocked(self):
        self.assertEqual(self.prepare(staff=str(self.other_staff.pk)).status_code,404)
        self.assertEqual(self.prepare(year=str(self.other_year.pk)).status_code,404)
        self.assertEqual(self.prepare(period="2026-08-01").status_code,422)
        self.assertEqual(self.prepare(period="2026-11-15").status_code,422)
        self.assertEqual(self.prepare(gross_amount="0").status_code,422)
        self.assertEqual(self.prepare(deductions="120000").status_code,422)
        self.assertEqual(self.prepare(currency="xaf").status_code,422)
        self.assertEqual(self.prepare(basis=[]).status_code,422)
        self.assertEqual(StaffPayRun.objects.count(),0)
        # A cashier cannot manufacture a payroll item for themself, even if
        # additional accountant and director rights are granted.
        self.login("comptabilite")
        self.assertEqual(self.prepare(staff=str(uuid.uuid4())).status_code,404)
        own=StaffRecord.objects.create(school=self.school,account=self.users["comptabilite"],
            staff_code="COMPTA-SELF",first_name="Comptable",last_name="TEST",position="Comptable")
        self.assertEqual(self.prepare(staff=str(own.pk)).status_code,403)
        row=self.prepare().json()
        self.login("enseignant")
        self.assertEqual(self.client.get("runs/"+row["id"]).status_code,403)
        self.login("direction")
        self.assertEqual(self.client.get(
            f"/api/v1/schools/{self.other.pk}/payroll/runs/{row['id']}"
        ).status_code,404)
