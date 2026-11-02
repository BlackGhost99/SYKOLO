import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class PlatformBootstrapTests(TestCase):
    credentials = {
        "YEM_BOOTSTRAP_USERNAME": "founder",
        "YEM_BOOTSTRAP_EMAIL": "founder@example.org",
        "YEM_BOOTSTRAP_PASSWORD": "A-strong-unique-password-2026!",
    }

    def test_no_secrets_creates_no_account(self):
        with patch.dict(os.environ, {}, clear=True):
            call_command("bootstrap_platform_admin")
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_creates_exactly_one_superuser(self):
        with patch.dict(os.environ, self.credentials):
            call_command("bootstrap_platform_admin")
            call_command("bootstrap_platform_admin")
        users = get_user_model().objects.all()
        self.assertEqual(users.count(), 1)
        self.assertTrue(users.first().is_superuser)
        self.assertTrue(users.first().is_staff)
        self.assertTrue(users.first().check_password(self.credentials["YEM_BOOTSTRAP_PASSWORD"]))

    def test_does_not_elevate_existing_user(self):
        User = get_user_model()
        User.objects.create_user(username="founder", password="an-existing-password")
        with patch.dict(os.environ, self.credentials):
            call_command("bootstrap_platform_admin")
        self.assertFalse(User.objects.get(username="founder").is_superuser)

    def test_partial_secrets_are_rejected(self):
        with patch.dict(os.environ, {"YEM_BOOTSTRAP_USERNAME": "founder"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("bootstrap_platform_admin")
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_weak_password_is_rejected(self):
        with patch.dict(os.environ, {**self.credentials, "YEM_BOOTSTRAP_PASSWORD": "123"}, clear=True):
            with self.assertRaises(CommandError):
                call_command("bootstrap_platform_admin")
        self.assertEqual(get_user_model().objects.count(), 0)
