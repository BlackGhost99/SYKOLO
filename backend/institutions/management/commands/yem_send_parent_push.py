import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from institutions.parent_push_delivery import enqueue, deliver
from institutions.parent_push_transport import FcmTransport


class Command(BaseCommand):
    help = "Send queued generic family inbox alerts; run from a dedicated scheduled worker."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 200:
            raise CommandError("Limit must be between 1 and 200.")
        if not settings.YEM_PARENT_PUSH_ENABLED or len(settings.YEM_PARENT_PUSH_KEY) < 32:
            raise CommandError("Parent push disabled.")
        try:
            transport = FcmTransport(os.environ["YEM_FCM_SERVICE_ACCOUNT_JSON"], os.environ["YEM_FCM_PROJECT_ID"])
        except Exception:
            raise CommandError("FCM configuration unavailable or invalid.") from None
        created = enqueue(limit=limit * 4)
        self.stdout.write(json.dumps({"queued": created, **deliver(transport, limit=limit)}))
