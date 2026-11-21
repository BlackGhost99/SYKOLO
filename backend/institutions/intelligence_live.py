"""Explicit free Gemini pilot for financial header suggestions only."""
from datetime import timezone as datetime_timezone

from django.conf import settings
from django.db import DatabaseError
from django.db.models import F
from django.utils import timezone

from .intelligence_engine import IntelligenceEngine
from .intelligence_import import analyze_import_headers
from .intelligence_providers import MAX_COLUMNS, ProviderError, header_adapter
from .models import GeminiDailyUsage

# Shared across schools, workers and restarts. Failed calls count as attempts.
DAILY_LIMIT = 10


def usage_day():
    return timezone.now().astimezone(datetime_timezone.utc).date()


def gemini_usage():
    day = usage_day()
    daily_counts = dict(GeminiDailyUsage.objects.filter(
        day__range=(day.replace(day=1), day),
    ).values_list("day", "requests"))
    today = daily_counts.get(day, 0)
    return {
        "today": today, "daily_limit": DAILY_LIMIT,
        "remaining": max(0, DAILY_LIMIT - today),
        "month": sum(daily_counts.values()), "timezone": "UTC",
    }


def analyze_financial_headers_with_gemini(headers):
    adapter = header_adapter(
        "gemini", model=settings.YEM_GEMINI_MODEL, api_key=settings.YEM_GEMINI_API_KEY,
    )
    status = "no_clues"

    def classify(clues):
        nonlocal status
        if len(clues) > MAX_COLUMNS:
            status = "column_limit"
            raise ProviderError("Too many columns")
        day = usage_day()
        try:
            GeminiDailyUsage.objects.get_or_create(day=day)
            reserved = GeminiDailyUsage.objects.filter(day=day, requests__lt=DAILY_LIMIT).update(
                requests=F("requests") + 1,
            )
        except DatabaseError:
            status = "unavailable"
            raise ProviderError("Quota store unavailable") from None
        if not reserved:
            status = "daily_limit"
            raise ProviderError("Daily quota reached")
        status = "fallback"
        hints = adapter(clues)
        status = "used"
        return hints

    result = analyze_import_headers(headers, advisor_engine=IntelligenceEngine(header_advisor=classify))
    if status == "used" and result["advice_source"] != "advisor":
        status = "fallback"
    return result, status
