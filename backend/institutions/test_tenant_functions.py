import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.utils import timezone
from .models import Organization, OrganizationMember, School, SchoolRole, SchoolMember, SchoolLogin, SchoolAudit, PermissionDelegation
from .services import ROLE_TEMPLATES, effective_permissions
from .school_functions import positions_for_school


class TenantFunctionTests(TestCase):
    password = "Marigold River Lantern 8294!"

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("school-owner", password=self.password)
        self.org = Organization.objects.create(name="Groupe")
        OrganizationMember.objects.create(organization=self.org,user=self.owner)
        self.schools = [School.objects.create(organization=self.org,name=n,school_type="lycee_general",education_cycles=["lycee_general"]) for n in ["Lycée A","Lycée B"]]
        for school in self.schools:
            for code,label,perms in ROLE_TEMPLATES:
                SchoolRole.objects.create(school=school,code=code,label=label,permissions=perms)
        self.school,self.other = self.schools
        self.base=f"/api/v1/schools/{self.school.pk}/"
        self.client.force_login(self.owner)

    def send(self,path,data,method="post",client=None):
        return getattr(client or self.client,method)(path,json.dumps(data),content_type="application/json")

    def create(self,school,username="directeur1",functions=None):
        response=self.send(f"/api/v1/schools/{school.pk}/users",dict(username=username,email="staff@example.test",password=self.password,role="enseignant",function_codes=functions or []))
        self.assertEqual(response.status_code,201,response.content)
        return SchoolLogin.objects.get(school=school,username=username).user

    def signin(self,client,school,username="directeur1"):
        return self.send("/api/v1/auth/login",dict(scope="school",school_code=str(school.pk),username=username,password=self.password),client=client)

    def test_same_credentials_different_schools_and_financial_session_isolation(self):
        a=self.create(self.school);b=self.create(self.other)
        self.assertNotEqual(a.pk,b.pk)
        ca,cb=Client(),Client()
        self.assertEqual(self.signin(ca,self.school).status_code,200)
        self.assertEqual(self.signin(cb,self.other).status_code,200)
        self.assertNotEqual(ca.session.session_key,cb.session.session_key)
        self.assertEqual(ca.get(f"/api/v1/schools/{self.other.pk}/finance/summary").status_code,403)
        self.assertEqual(cb.get(self.base+"access").status_code,403)
        self.assertEqual(len(ca.get("/api/v1/schools").json()["schools"]),1)
        self.assertEqual(ca.get("/api/v1/auth/me").json()["user"]["username"],"directeur1")
        self.assertEqual(self.send("/api/v1/auth/login",dict(username=a.username,password=self.password),client=Client()).status_code,401)

    def test_multiple_functions_without_posts_and_no_title_permissions(self):
        user=self.create(self.school,functions=["censeur_etudes","censeur_vie_scolaire"])
        member=SchoolMember.objects.get(school=self.school,user=user)
        self.assertEqual(len(member.function_codes),2)
        self.assertNotIn("school.attendance.write",effective_permissions(user,self.school))
        self.assertFalse(self.school.appointments.exists())
        self.assertEqual(self.send(self.base+"functions",{"enabled_functions":[]},"patch").status_code,200)
        self.assertEqual(self.send(self.base+"users",dict(username="x",email="x@x.test",password=self.password,role="enseignant",function_codes=["proviseur"])).status_code,422)
        self.create(self.school,"no-post")
        member.refresh_from_db();self.assertEqual(len(member.function_codes),2)

    def test_delegation_vacancy_revoke_audit_and_expiry(self):
        user=self.create(self.school)
        data=dict(user_id=str(user.pk),permissions=["school.attendance.write"],reason="Poste vie scolaire vacant",source_function="censeur_vie_scolaire")
        response=self.send(self.base+"delegations",data)
        self.assertEqual(response.status_code,201,response.content)
        self.assertIn("school.attendance.write",effective_permissions(user,self.school))
        self.assertNotIn("school.attendance.write",effective_permissions(user,self.other))
        grant=response.json()["id"]
        self.assertEqual(self.send(self.base+"delegations/"+grant,{"reason":"Fin de remplacement"},"delete").status_code,200)
        self.assertNotIn("school.attendance.write",effective_permissions(user,self.school))
        self.assertEqual(SchoolAudit.objects.filter(event__in=["delegation_granted","delegation_revoked"]).count(),2)
        self.assertTrue(PermissionDelegation.objects.get(pk=grant).revoked_by_id)
        data["expires_at"]=(timezone.now()+timedelta(hours=1)).isoformat()
        response=self.send(self.base+"delegations",data);self.assertEqual(response.status_code,201)
        PermissionDelegation.objects.filter(pk=response.json()["id"]).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertNotIn("school.attendance.write",effective_permissions(user,self.school))

    def test_foreign_target_privilege_escalation_and_financial_separation(self):
        a=self.create(self.school);b=self.create(self.other)
        data=dict(user_id=str(b.pk),permissions=["school.finance.receive"],reason="Test")
        self.assertEqual(self.send(self.base+"delegations",data).status_code,422)
        data.update(user_id=str(a.pk),permissions=["school.finance.receive","school.finance.approve"])
        self.assertEqual(self.send(self.base+"delegations",data).status_code,422)
        data["permissions"]=["school.roles.manage"]
        self.assertEqual(self.send(self.base+"delegations",data).status_code,422)
        self.client.force_login(a)
        data["permissions"]=["school.finance.receive"]
        self.assertEqual(self.send(self.base+"delegations",data).status_code,403)

    def test_founder_cannot_self_delegate_financial_authority(self):
        SchoolMember.objects.create(
            school=self.school, user=self.owner, role=self.school.roles.get(code="enseignant")
        )
        payload = {
            "user_id": str(self.owner.pk), "permissions": ["school.finance.receive"],
            "reason": "Tentative d'auto-attribution",
        }
        response = self.send(self.base + "delegations", payload)
        self.assertEqual(response.status_code, 403, response.content)
        self.assertFalse(PermissionDelegation.objects.filter(school=self.school, member__user=self.owner).exists())

    def test_catalogue_each_type_and_platform_login_separate(self):
        for kind,cycles,expected in [("maternelle",["prescolaire"],"directeur_maternelle"),("primaire",["primaire"],"directeur_primaire"),("college",["college"],"principal"),("lycee_general",["lycee_general"],"censeur_principal"),("lycee_technique",["lycee_technique"],"chef_travaux"),("groupe_scolaire",["primaire","college","lycee_general"],"proviseur")]:
            self.school.school_type,self.school.education_cycles=kind,cycles
            self.assertIn(expected,{f["code"] for f in positions_for_school(self.school)})
        admin=get_user_model().objects.create_superuser("platform",password=self.password)
        self.assertEqual(self.send("/api/v1/auth/login",dict(scope="platform",username=admin.username,password=self.password),client=Client()).status_code,200)
        self.assertEqual(self.send("/api/v1/auth/login",dict(scope="parent",username=admin.username,password=self.password),client=Client()).status_code,401)

    def test_migration_preserves_passwords_and_memberships(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        user=get_user_model().objects.create_user("legacy",password=self.password)
        SchoolMember.objects.create(school=self.school,user=user,role=self.school.roles.get(code="enseignant"))
        original=user.password
        from types import SimpleNamespace
        import_module("institutions.migrations.0023_school_identity_delegations").preserve_logins(apps,SimpleNamespace(connection=connection))
        self.assertTrue(SchoolLogin.objects.filter(school=self.school,user=user,username="legacy").exists())
        user.refresh_from_db();self.assertEqual(user.password,original)
        self.assertEqual(self.signin(Client(),self.school,"legacy").status_code,200)
