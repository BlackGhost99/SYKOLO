"""Bounded polling in a single dedicated process, never initiates a debit."""
import signal
import threading
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import connection, close_old_connections

class Command(BaseCommand):
    help = "Continuously reconcile SingPay with a PostgreSQL singleton lock."
    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=60)
        parser.add_argument("--once", action="store_true")
    def handle(self, *args, **options):
        interval = options["interval"]
        if not 30 <= interval <= 3600:
            raise CommandError("interval must be between 30 and 3600 seconds")
        if connection.vendor != "postgresql":
            raise CommandError("PostgreSQL is required for the worker singleton lock")
        stop = threading.Event()
        for sig in (signal.SIGTERM,signal.SIGINT):
            signal.signal(sig,lambda *_: stop.set())
        while not stop.is_set():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_try_advisory_lock(%s)",[736401228])
                    acquired = cursor.fetchone()[0]
                if acquired:
                    try:
                        call_command("yem_reconcile_singpay", apply=True, limit=20, stdout=self.stdout)
                    finally:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_advisory_unlock(%s)",[736401228])
            except Exception:
                # No provider payload, phone, credentials or SQL parameters in logs.
                self.stderr.write("SingPay reconciliation cycle failed; next cycle will check again.")
                connection.close()
            if options["once"]:
                break
            stop.wait(interval)
