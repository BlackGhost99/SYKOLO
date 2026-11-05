"""Effective direction rights, privilege ceilings and independent delegation."""
import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Organization, OrganizationMember, School, SchoolMember, SchoolRole
from .services import ROLE_TEMPLATES, effective_permissions


class DirectionRightsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user('audit-owner')
        self.director = User.objects.create_user('audit-director')
        self.target = User.objects.create_user('audit-target')
        self.school = School.objects.create(organization=Organization.objects.create(name='Audit'), name='Audit')
        OrganizationMember.objects.create(organization=self.school.organization, user=self.owner, role='founder')
        for code, label, permissions in ROLE_TEMPLATES:
            SchoolRole.objects.create(school=self.school, code=code, label=label, permissions=permissions)
        self.member = SchoolMember.objects.create(school=self.school, user=self.director, role=self.role('direction'))
        self.base = f'/api/v1/schools/{self.school.pk}/'
        self.client.force_login(self.director)

    def role(self, code):
        return SchoolRole.objects.get(school=self.school, code=code)

    def send(self, path, data, method='post'):
        return getattr(self.client, method)(self.base+path, json.dumps(data), content_type='application/json')

    def test_direct_financial_endpoints_reject_direction_before_payload_processing(self):
        paths = ['finance/schedules', 'finance/charges', 'finance/payments', 'finance/batches',
                 'finance/cash/closings', f'finance/payments/{self.school.pk}/void',
                 f'finance/cash/closings/{self.school.pk}/transfers']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.send(path, {}).status_code, 403)
        # Approval is explicitly part of direction, not a missing gate.
        self.assertIn('school.finance.approve', effective_permissions(self.director, self.school))

    def test_cannot_add_missing_financial_permission_to_own_role(self):
        role = self.role('direction')
        for permission in ['manage', 'receive', 'reverse', 'deposit']:
            response = self.send(f'roles/{role.pk}', {'label':role.label, 'revision':role.revision,
                'permissions':role.permissions+[f'school.finance.{permission}']}, 'patch')
            self.assertEqual(response.status_code, 403)
        role.refresh_from_db()
        self.assertNotIn('school.finance.receive', role.permissions)

    def test_cannot_create_role_with_missing_right(self):
        self.assertEqual(self.send('roles', {'code':'supercash', 'label':'Cash',
            'permissions':['school.finance.receive']}).status_code, 403)

    def test_cannot_self_assign_financial_primary_or_additional_role(self):
        for data in [{'role':'econome'}, {'role':'direction', 'additional_roles':['econome']},
                     {'role':'direction', 'additional_roles':['tarification','comptabilite']}]:
            self.assertEqual(self.send('members', {'username':self.director.username, **data}).status_code, 403)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role.code, 'direction')
        self.assertFalse(self.member.additional_roles.exists())

    def test_controlled_approver_exploit_on_original_policy(self):
        # Bypass only the new delegation boundary to reproduce main's behavior.
        with patch('institutions.views.may_delegate_finance', return_value=True, create=True):
            response = self.send('users', {'username':'controlled-approver', 'email':'controlled@example.test',
                'password':'Marigold River Lantern 8294!', 'role':'direction'})
        self.assertEqual(response.status_code, 201, response.content)
        user = get_user_model().objects.get(username='controlled-approver')
        self.assertTrue(user.check_password('Marigold River Lantern 8294!'))
        self.assertIn('school.finance.approve', effective_permissions(user, self.school))
        from django.utils import timezone
        from .finance_models import CashClosing
        closing = CashClosing.objects.create(school=self.school, day=timezone.localdate(),
            currency='XAF', expected=0, counted=0, difference=0, submitted_by=self.director)
        # One account cannot approve itself, but an account with a known password can.
        path = f'finance/cash/closings/{closing.pk}/approve'
        self.assertEqual(self.send(path, {'note':''}).status_code, 403)
        self.client.force_login(user)
        self.assertEqual(self.send(path, {'note':''}).status_code, 200)
        closing.refresh_from_db()
        self.assertEqual(closing.approved_by, user)

    def test_cannot_create_or_appoint_controlled_approver(self):
        self.assertEqual(self.send('users', {'username':'blocked-approver', 'email':'blocked@example.test',
            'password':'Marigold River Lantern 8294!', 'role':'direction'}).status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username='blocked-approver').exists())
        self.assertEqual(self.send('members', {'username':self.target.username, 'role':'direction'}).status_code, 403)
        self.assertFalse(SchoolMember.objects.filter(school=self.school, user=self.target).exists())

    def test_cannot_launder_approval_through_custom_role(self):
        self.assertEqual(self.send('roles', {'code':'approval', 'label':'Contrôle',
            'permissions':['school.finance.approve']}).status_code, 403)
        teacher = self.role('enseignant')
        self.assertEqual(self.send(f'roles/{teacher.pk}', {'label':teacher.label, 'revision':teacher.revision,
            'permissions':teacher.permissions+['school.finance.approve']}, 'patch').status_code, 403)

    def test_founder_can_explicitly_delegate_but_has_no_implicit_finance(self):
        self.assertEqual(effective_permissions(self.owner, self.school), {'school.members.write'})
        self.client.force_login(self.owner)
        self.assertEqual(self.send('members', {'username':self.director.username, 'role':'direction',
            'additional_roles':['econome','tarification','comptabilite']}).status_code, 200)
        permissions = effective_permissions(self.director, self.school)
        for duty in ['receive','manage','reverse','deposit','approve']:
            self.assertIn('school.finance.'+duty, permissions)

    def test_nonfinancial_members_and_roles_remain_delegable(self):
        self.assertEqual(self.send('members', {'username':self.target.username, 'role':'enseignant'}).status_code, 201)
        self.assertEqual(self.send('roles', {'code':'library', 'label':'Bibliothèque',
            'permissions':['school.view']}).status_code, 201)
        role = self.role('direction')
        self.assertEqual(self.send(f'roles/{role.pk}', {'label':'Directrice', 'revision':role.revision,
            'permissions':role.permissions}, 'patch').status_code, 200)
