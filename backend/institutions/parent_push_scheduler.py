"""One-time database-authorized dispatch for a small free-tier pilot."""
import hashlib
import os
import re

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .parent_push_delivery import enqueue, deliver
from .parent_push_models import ParentPushDevice
from .parent_push_transport import FcmTransport

MAX_PILOT_DEVICES = 25


def take_ticket(token):
    # A single UPDATE consumes the high-entropy ticket, with a lease to stop
    # overlapping calls. The private schema is provisioned separately on Supabase.
    if connection.vendor != "postgresql":
        return False
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE yem_push_private.dispatch_state
               SET ticket_digest = NULL, ticket_expires = NULL,
                   running_until = now() + interval '3 minutes'
             WHERE singleton = true AND ticket_digest = %s
               AND ticket_expires > now() AND running_until <= now()
            RETURNING singleton
        """, [digest])
        return cursor.fetchone() is not None


@csrf_exempt
@require_POST
def run_scheduled_push(request):
    # No user/session credentials grant access. No body, account or payload
    # accepted. Header never appears in standard access logs.
    header = request.headers.get("Authorization", "")
    match = re.fullmatch(r"Bearer ([0-9a-f]{64})", header)
    if not match or request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    if not settings.YEM_PARENT_PUSH_ENABLED or len(settings.YEM_PARENT_PUSH_KEY) < 32:
        return JsonResponse({"error": "Unavailable"}, status=503)
    try:
        if not take_ticket(match.group(1)):
            return JsonResponse({"error": "Unauthorized"}, status=401)
    except DatabaseError:
        return JsonResponse({"error": "Unavailable"}, status=503)
    try:
        active = list(ParentPushDevice.objects.filter(
            valid_until__gt=timezone.now(), parent__is_active=True,
            parent__is_superuser=False,
        ).order_by().values_list("pk", flat=True)[:MAX_PILOT_DEVICES + 1])
        if len(active) > MAX_PILOT_DEVICES:
            return JsonResponse({"error": "Pilot capacity exceeded"}, status=503)
        transport = FcmTransport(os.environ["YEM_FCM_SERVICE_ACCOUNT_JSON"],
                                 os.environ["YEM_FCM_PROJECT_ID"], timeout=5)
        queued = enqueue(limit=12)
        stats = deliver(transport, limit=3)
        return JsonResponse({"queued": queued, **stats})
    except Exception:
        # Do not expose tokens, credentials, SQL or upstream response bodies.
        return JsonResponse({"error": "Dispatch unavailable"}, status=503)
