"""Bounded, resumable delivery of durable school-to-family inbox notices."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from .family_notification_models import SchoolFamilyNotification as Notice
from .parent_push_models import ParentPushDevice, ParentPushDelivery
from .parent_push_transport import PushError
from .parent_push_views import push_cipher


def active_device(device, now):
    user, session = device.parent, device.session
    if not user.is_active or user.is_superuser or session.expire_date <= now:
        return False
    data = session.get_decoded()
    return (data.get("login_scope") == "parent" and not data.get("school_id")
            and str(data.get("_auth_user_id")) == str(user.pk)
            and constant_time_compare(data.get("_auth_user_hash", ""), user.get_session_auth_hash()))


def enqueue(limit=200):
    now = timezone.now()
    devices = ParentPushDevice.objects.select_related("parent", "session").filter(
        session__expire_date__gt=now, parent__is_active=True, parent__is_superuser=False
    ).order_by("pk")
    created = 0
    # Session lifetime is at most eight hours. No historic backlog or inactive school alerts.
    for device in devices.iterator(chunk_size=100):
        if not active_device(device, now):
            continue
        notices = Notice.objects.filter(
            parent_id=device.parent_id, destination=Notice.TO_PARENT, school__is_active=True,
            read_at__isnull=True, created_at__gte=max(device.registered_at, now - timedelta(hours=8))
        ).exclude(parentpushdelivery__device_id=device.pk).order_by("created_at", "pk")[:max(0, limit-created)]
        rows = [ParentPushDelivery(device_id=device.pk, notice_id=n.pk) for n in notices]
        # Unique(device, notice) protects repeated scans; disappearing sessions are harmless.
        if rows:
            try:
                with transaction.atomic():
                    if ParentPushDevice.objects.select_for_update().filter(pk=device.pk).exists():
                        ParentPushDelivery.objects.bulk_create(rows, ignore_conflicts=True)
                        created += len(rows)
            except ParentPushDevice.DoesNotExist:
                pass
        if created >= limit:
            break
    return created


def deliver(transport, limit=50):
    stats = {"accepted": 0, "retry": 0, "skipped": 0, "unregistered": 0}
    for _ in range(limit):
        now = timezone.now()
        with transaction.atomic():
            row = (ParentPushDelivery.objects.select_for_update(skip_locked=True)
                   .filter(state="pending", next_try__lte=now).order_by("next_try", "pk").first())
            if row is None:
                break
            # Serialize claims; short lease permits recovery after a killed worker.
            row.attempts += 1
            row.next_try = now + timedelta(minutes=5)
            row.save(update_fields=["attempts", "next_try"])
            pk = row.pk
        device = ParentPushDevice.objects.select_related("parent", "session").filter(pk=row.device_id).first()
        notice = Notice.objects.filter(pk=row.notice_id, destination=Notice.TO_PARENT, school__is_active=True, read_at__isnull=True).first()
        if not device or not notice or notice.parent_id != device.parent_id or not active_device(device, now) or notice.created_at < device.registered_at or notice.created_at < now - timedelta(hours=8) or row.attempts > 5:
            ParentPushDelivery.objects.filter(pk=pk).update(state="skipped", completed_at=now)
            stats["skipped"] += 1
            continue
        try:
            token = push_cipher().decrypt(device.encrypted_token.encode()).decode()
        except Exception:
            ParentPushDelivery.objects.filter(pk=pk).update(state="skipped", completed_at=now)
            stats["skipped"] += 1
            continue
        try:
            transport.send(token)
        except PushError as exc:
            if exc.unregistered:
                ParentPushDevice.objects.filter(pk=device.pk, token_digest=device.token_digest).delete()
                stats["unregistered"] += 1
            else:
                delay = max(exc.retry_after, min(3600, 60 * 2 ** min(row.attempts - 1, 6)))
                ParentPushDelivery.objects.filter(pk=pk).update(next_try=timezone.now() + timedelta(seconds=delay))
                stats["retry"] += 1
                if exc.fatal:
                    break
        else:
            ParentPushDelivery.objects.filter(pk=pk).update(state="accepted", completed_at=timezone.now())
            stats["accepted"] += 1
    return stats
