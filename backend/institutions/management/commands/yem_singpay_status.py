"""Safe operator diagnostics; no secret or personal payment data is printed."""
import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from institutions.singpay_models import SingPayMerchant, SingPayIntent
from institutions.commercial_singpay_models import PlatformSingPayMerchant
from institutions.singpay_service import merchant_ready, verify_wallet_access, ProviderError

class Command(BaseCommand):
    help = "Print non-secret SingPay readiness; optional authenticated wallet verification, no debit."
    def add_arguments(self, parser):
        parser.add_argument("--verify-wallets",action="store_true")
    def handle(self,*args,**options):
        approved={x.strip() for x in getattr(settings,"YEM_SINGPAY_APPROVED_DESTINATIONS","").split(",") if x.strip()}
        result={"singpay_enabled":settings.YEM_SINGPAY_ENABLED,
                "live_payments_enabled":settings.YEM_PAYMENTS_LIVE_ENABLED,
                "https":settings.AUTH_PUBLIC_BASE_URL.startswith("https://"),
                "encryption_configured":len(settings.YEM_PAYMENT_ENCRYPTION_KEY)>=32,
                "reconciliation_enabled":os.environ.get("YEM_SINGPAY_RECONCILIATION_ENABLED","")=="true",
                "approved_destination_count":len(approved),"merchants":[]}
        rows=[(str(m.school_id),m) for m in SingPayMerchant.objects.all()]
        platform=PlatformSingPayMerchant.objects.first()
        if platform: rows.append(("platform",platform))
        for scope,row in rows:
            item={"scope":scope,"enabled":row.enabled,"mode":row.mode,"active":merchant_ready(row),
                  "approved":f"{scope}:{row.wallet_id}:{row.disbursement_id}:{row.mode}" in approved}
            if options["verify_wallets"]:
                try: verify_wallet_access(row);item["wallet_verified"]=True
                except ProviderError:item["wallet_verified"]=False
            result["merchants"].append(item)
        from django.db.models import Count
        result["school_intents"]={r["state"]:r["count"] for r in SingPayIntent.objects.values("state").annotate(count=Count("pk"))}
        self.stdout.write(json.dumps(result,ensure_ascii=False))
