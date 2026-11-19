from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase


class SingPayReconciliationCommandTests(TestCase):
    def test_reject_invalid_limits(self):
        for limit in (0, 101):
            with self.assertRaises(CommandError):
                call_command("yem_reconcile_singpay", limit=limit)

    @patch("institutions.management.commands.yem_reconcile_singpay.reconcile")
    def test_empty_dry_run_never_calls_provider(self, reconcile):
        output = StringIO()
        call_command("yem_reconcile_singpay", stdout=output)
        self.assertIn("Dry run: 0", output.getvalue())
        reconcile.assert_not_called()

    @patch("institutions.management.commands.yem_reconcile_singpay.reconcile")
    def test_empty_apply_never_calls_provider(self, reconcile):
        call_command("yem_reconcile_singpay", apply=True, stdout=StringIO())
        reconcile.assert_not_called()
