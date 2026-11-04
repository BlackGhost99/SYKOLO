import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from . import test_finance_batch as batch_tests
from .models import SchoolMember, SchoolRole, OrganizationMember
from .services import has_permission


class FinancialControlTests(TestCase):
    setUp = batch_tests.MultiFeeReceiptTests.setUp
    login = batch_tests.MultiFeeReceiptTests.login
    payload = batch_tests.MultiFeeReceiptTests.payload
    send = batch_tests.MultiFeeReceiptTests.send
    post_closing = batch_tests.MultiFeeReceiptTests.post_closing
    approve_closing = batch_tests.MultiFeeReceiptTests.approve_closing

    def post(self, path, data):
        return self.client.post(self.base + path, json.dumps(data), content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

    def controller(self):
        user = get_user_model().objects.create_user("independent-controller")
        SchoolMember.objects.create(school=self.school, user=user, role=SchoolRole.objects.get(school=self.school, code="comptabilite"))
        return user

    def test_roles_and_cumulative_functions(self):
        director_role = SchoolRole.objects.get(school=self.school, code="direction")
        for permission in ["school.finance.receive", "school.finance.manage", "school.finance.reverse"]:
            self.assertNotIn(permission, director_role.permissions)
        OrganizationMember.objects.create(organization=self.school.organization, user=self.cashier, role="founder")
        self.assertIn("school.members.write", self.client.get(f"/api/v1/schools/{self.school.pk}/my-access").json()["permissions"])
        controller = self.controller()
        self.assertFalse(has_permission(controller, self.school, "school.finance.receive"))
        self.assertFalse(has_permission(controller, self.school, "school.finance.manage"))
        self.assertFalse(has_permission(self.cashier, self.school, "school.finance.reverse"))
        member = SchoolMember.objects.get(user=self.cashier, school=self.school)
        member.additional_roles.add(SchoolRole.objects.get(school=self.school, code="comptabilite"))
        receipt = self.send(self.payload()).json()
        self.assertEqual(self.post("payments/"+receipt["payments"][0]["id"]+"/void", {"reason":"Erreur documentée du caissier"}).status_code, 403)
        closure = self.post_closing("30000").json()
        self.assertEqual(self.approve_closing(closure["id"]).status_code, 403)
        access = self.client.get(f"/api/v1/schools/{self.school.pk}/my-access").json()
        self.assertIn("econome", access["roles"])
        self.assertIn("comptabilite", access["roles"])
        foreign = SchoolRole.objects.get(school=self.other_school, code="tarification")
        member.additional_roles.add(foreign)
        self.assertFalse(has_permission(self.cashier, self.school, "school.finance.manage"))

    def test_transfer_limits_and_independent_receipt_control(self):
        self.send(self.payload())
        closure = self.post_closing("30000").json()
        path = "cash/closings/"+closure["id"]+"/transfers"
        data = {"kind":"handover", "amount":"30000", "reference":"PIECE-1", "destination":"Trésorerie", "day":timezone.localdate().isoformat()}
        self.assertEqual(self.post(path,data).status_code,409)
        controller = self.controller()
        self.login(controller)
        self.assertEqual(self.approve_closing(closure["id"]).status_code,200)
        self.login(self.cashier)
        transfer = self.post(path,data)
        self.assertEqual(transfer.status_code,201,transfer.content)
        self.assertEqual(self.post(path,data).status_code,409)
        deposit = {**data,"kind":"deposit","reference":"BANQUE-1"}
        self.assertEqual(self.post(path,deposit).status_code,409)
        approval = path+"/"+transfer.json()["id"]+"/approve"
        self.login(controller)
        self.assertEqual(self.post(approval,{}).status_code,200)
        self.login(self.cashier)
        self.assertEqual(self.post(path,{**deposit,"amount":"30001"}).status_code,409)
        deposit_response = self.post(path,deposit)
        self.assertEqual(deposit_response.status_code,201,deposit_response.content)
        member = SchoolMember.objects.get(school=self.school,user=self.cashier)
        member.additional_roles.add(SchoolRole.objects.get(school=self.school,code="comptabilite"))
        self.assertEqual(self.post(path+"/"+deposit_response.json()["id"]+"/approve",{}).status_code,403)
        self.login(controller)
        self.assertEqual(self.post(path+"/"+deposit_response.json()["id"]+"/approve",{}).status_code,200)

    def test_overview_explicit_currency_and_year(self):
        self.send(self.payload())
        base = f"/api/v1/schools/{self.school.pk}/overview/finance"
        eur = self.client.get(base+"?currency=EUR").json()
        self.assertEqual(eur["currency"],"EUR")
        self.assertEqual(eur["outstanding"],"10000.00")
        self.assertEqual(eur["today"]["total"],"0.00")
        self.assertEqual(set(eur["currencies"]),{"EUR","XAF"})
        self.assertEqual(self.client.get(base+"?year=invalid").status_code,422)
        self.assertEqual(self.client.get(base+"?currency=xaf").status_code,422)
        from .academic_models import AcademicYear
        past = AcademicYear.objects.create(school=self.school, code="past", name="Ancien exercice", start_date="2024-09-01", end_date="2025-07-31")
        report = self.client.get(base+"?currency=XAF&year="+str(past.pk)).json()
        self.assertEqual(report["today"]["total"],"0.00")
        self.assertEqual(report["outstanding"],"0.00")


class FinanceRoleMigrationTests(TestCase):
    def test_existing_roles_lose_unsafe_rights_without_losing_customization(self):
        import importlib
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        from .models import Organization, School
        school = School.objects.create(organization=Organization.objects.create(name="Migration"), name="Migration")
        role = SchoolRole.objects.create(school=school,code="direction",label="Directrice personnalisée",permissions=["school.students.read","school.finance.receive","school.finance.manage","school.finance.reverse"])
        accountant = SchoolRole.objects.create(school=school,code="comptabilite",label="Contrôle",permissions=["school.finance.read","school.finance.receive","school.finance.manage"])
        migrate = importlib.import_module("institutions.migrations.0022_finance_role_separation").separate_roles
        migrate(apps,SimpleNamespace(connection=connection))
        role.refresh_from_db(); accountant.refresh_from_db()
        self.assertEqual(role.label,"Directrice personnalisée")
        self.assertIn("school.students.read",role.permissions)
        self.assertIn("school.finance.approve",role.permissions)
        self.assertNotIn("school.finance.receive",role.permissions)
        self.assertNotIn("school.finance.manage",accountant.permissions)
        self.assertNotIn("school.finance.receive",accountant.permissions)
        self.assertEqual(school.roles.filter(code__in=["econome","tarification"]).count(),2)


from django.test import TransactionTestCase
from django.db import connection
from unittest import skipUnless


@skipUnless(connection.vendor == "postgresql", "Row locking requires PostgreSQL")
class CashTransferConcurrencyTests(TransactionTestCase):
    def test_parallel_handovers_cannot_reserve_the_same_cash(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        from django.test import Client
        from .models import Organization, School
        from .finance_models import CashClosing, CashTransfer
        school = School.objects.create(organization=Organization.objects.create(name="Concurrent"),name="Concurrent")
        role = SchoolRole.objects.create(school=school,code="econome",permissions=["school.finance.deposit"])
        users = [get_user_model().objects.create_user("parallel-"+str(i)) for i in range(2)]
        clients = []
        for user in users:
            SchoolMember.objects.create(school=school,user=user,role=role)
            client = Client(); client.force_login(user); clients.append(client)
        closing = CashClosing.objects.create(school=school,day=timezone.localdate(),currency="XAF",expected=100,counted=100,difference=0,submitted_by=users[0],approved_by=users[1],approved_at=timezone.now())
        barrier = Barrier(2)
        def submit(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return clients[index].post(f"/api/v1/schools/{school.pk}/finance/cash/closings/{closing.pk}/transfers",json.dumps({"kind":"handover","amount":"60","reference":"parallel-"+str(index),"destination":"Trésorerie","day":timezone.localdate().isoformat()}),content_type="application/json").status_code
            finally:
                # Worker threads must close live DB handles, not merely stale
                # ones, or PostgreSQL will refuse Django's test DB teardown.
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(submit,range(2)))
        self.assertEqual(sorted(codes),[201,409])
        self.assertEqual(CashTransfer.objects.filter(closing=closing).count(),1)
