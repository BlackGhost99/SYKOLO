from datetime import timedelta
from unittest.mock import Mock
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .models import Organization, School
from .family_notification_models import SchoolFamilyNotification as Notice
from .parent_push_models import ParentPushDevice, ParentPushDelivery
from .parent_push_views import push_cipher, binding_for
from .parent_push_delivery import enqueue, deliver
from .parent_push_transport import PushError


@override_settings(YEM_PARENT_PUSH_ENABLED=True, YEM_PARENT_PUSH_KEY="synthetic-push-delivery-key-for-tests")
class ParentPushDeliveryTests(TestCase):
    def setUp(self):
        self.parent = get_user_model().objects.create_user(username="delivery-parent")
        self.other = get_user_model().objects.create_user(username="delivery-other")
        self.school = School.objects.create(organization=Organization.objects.create(name="Push test"), name="Push school")
        self.client = Client()
        self.client.force_login(self.parent)
        session = self.client.session
        session["login_scope"] = "parent"
        session.save()
        self.device = ParentPushDevice.objects.create(
            parent=self.parent, session_id=session.session_key, token_digest="synthetic",
            encrypted_token=push_cipher().encrypt(b"fake-fcm-device-token").decode(),
            auth_binding=binding_for(self.parent), valid_until=timezone.now()+timedelta(days=30))
        self.transport = Mock()

    def notice(self, parent=None, destination=Notice.TO_PARENT):
        return Notice.objects.create(school=self.school, parent=parent or self.parent, destination=destination,
                                     origin="school", message="Private content must never enter FCM")

    def test_only_new_owned_unread_inbox_and_no_repeat(self):
        good = self.notice()
        self.notice(self.other)
        self.notice(destination=Notice.TO_SCHOOL)
        read = self.notice()
        Notice.objects.filter(pk=read.pk).update(read_at=timezone.now())
        old = self.notice()
        Notice.objects.filter(pk=old.pk).update(created_at=self.device.registered_at - timedelta(seconds=1))
        self.assertEqual(enqueue(), 1)
        self.assertEqual(enqueue(), 0)
        self.assertEqual(ParentPushDelivery.objects.get().notice_id, good.pk)
        self.assertEqual(deliver(self.transport)["accepted"], 1)
        self.transport.send.assert_called_once_with("fake-fcm-device-token")
        self.assertEqual(deliver(self.transport)["accepted"], 0)

    def test_retry_then_accept_and_honor_backoff(self):
        self.notice()
        enqueue()
        self.transport.send.side_effect = PushError(retry_after=180)
        self.assertEqual(deliver(self.transport)["retry"], 1)
        row = ParentPushDelivery.objects.get()
        self.assertEqual(row.state, "pending")
        self.assertGreater(row.next_try, timezone.now() + timedelta(seconds=170))
        self.transport.send.reset_mock()
        deliver(self.transport)
        self.transport.send.assert_not_called()
        ParentPushDelivery.objects.update(next_try=timezone.now())
        self.transport.send.side_effect = None
        self.assertEqual(deliver(self.transport)["accepted"], 1)

    def test_unregistered_device_removed(self):
        self.notice()
        enqueue()
        self.transport.send.side_effect = PushError(unregistered=True)
        self.assertEqual(deliver(self.transport)["unregistered"], 1)
        self.assertFalse(ParentPushDevice.objects.exists())

    def test_revoked_or_read_before_delivery(self):
        notice = self.notice()
        enqueue()
        Notice.objects.filter(pk=notice.pk).update(read_at=timezone.now())
        self.assertEqual(deliver(self.transport)["skipped"], 1)
        self.notice()
        enqueue()
        self.client.logout()
        self.assertFalse(ParentPushDelivery.objects.exists())
        deliver(self.transport)
        self.transport.send.assert_not_called()

    def test_invalid_session_auth_hash_refuses_send(self):
        self.notice()
        enqueue()
        self.parent.set_password("different-password-after-registration")
        self.parent.save()
        self.assertEqual(deliver(self.transport)["skipped"], 1)
        self.transport.send.assert_not_called()


    def test_notification_lease_survives_expired_session_cleanup(self):
        from django.contrib.sessions.models import Session
        Session.objects.filter(pk=self.device.session_id).update(expire_date=timezone.now()-timedelta(seconds=1))
        Session.objects.filter(pk=self.device.session_id).delete()
        self.device.refresh_from_db()
        self.assertIsNone(self.device.session_id)
        self.notice()
        self.assertEqual(enqueue(), 1)
        self.assertEqual(deliver(self.transport)["accepted"], 1)
        self.transport.reset_mock()
        self.notice()
        enqueue()
        ParentPushDevice.objects.filter(pk=self.device.pk).update(valid_until=timezone.now()-timedelta(seconds=1))
        self.assertEqual(deliver(self.transport)["skipped"], 1)
        self.transport.send.assert_not_called()
