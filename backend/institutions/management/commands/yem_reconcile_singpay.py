from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from institutions.singpay_models import SingPayIntent, SingPayMerchant
from institutions.singpay_service import merchant_ready, reconcile, ProviderError


class Command(BaseCommand):
    help = "Reconcile pending SingPay intents via authenticated GET; never initiate a debit."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        limit = options["limit"]
        if not 1 <= limit <= 100:
            raise CommandError("limit must be between 1 and 100")
        cutoff = timezone.now() - timedelta(minutes=2)
        merchants = SingPayMerchant.objects.filter(enabled=True)
        rows = SingPayIntent.objects.filter(
            state__in=("initiating", "pending", "unknown"),
            school_id__in=merchants.values("school_id"),
            created_at__lte=cutoff,
        ).filter(Q(checked_at__isnull=True) | Q(checked_at__lte=cutoff))
        rows = list(rows.order_by(F("checked_at").asc(nulls_first=True), "created_at", "pk")[:limit])
        if not options["apply"]:
            self.stdout.write(f"Dry run: {len(rows)} candidate(s)")
            return
        failures = 0
        checked = 0
        for row in rows:
            merchant = merchants.filter(school_id=row.school_id).first()
            if not merchant_ready(merchant):
                continue
            try:
                reconcile(row, merchant)
                checked += 1
            except ProviderError:
                failures += 1
                # Back off without changing the financial state.
                SingPayIntent.objects.filter(pk=row.pk, state=row.state,
                    checked_at=row.checked_at).update(checked_at=timezone.now())
        # Independent platform wallet; never reuse a school merchant for subscriptions.
        from institutions.commercial_singpay_models import PlatformSingPayMerchant, SubscriptionSingPayIntent
        from institutions.commercial_singpay import reconcile as reconcile_subscription
        platform = PlatformSingPayMerchant.objects.first()
        if merchant_ready(platform):
            candidates = SubscriptionSingPayIntent.objects.filter(
                state__in=("initiating", "pending", "unknown"), created_at__lte=cutoff,
            ).filter(Q(checked_at__isnull=True) | Q(checked_at__lte=cutoff))
            for row in candidates.order_by(F("checked_at").asc(nulls_first=True), "created_at", "pk")[:limit]:
                try:
                    reconcile_subscription(row, platform)
                    checked += 1
                except ProviderError:
                    failures += 1
                    SubscriptionSingPayIntent.objects.filter(pk=row.pk, state=row.state,
                        checked_at=row.checked_at).update(checked_at=timezone.now())
        self.stdout.write(f"Checked: {checked}; provider errors: {failures}")
        if failures:
            raise CommandError("Some reconciliations require another check.")
