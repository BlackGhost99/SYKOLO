"""Server-only Gemini readiness and a synthetic adapter self-test."""
from django.conf import settings

from .intelligence_engine import IntelligenceEngine
from .intelligence_providers import header_adapter


def gemini_readiness():
    key = settings.YEM_GEMINI_API_KEY
    model = settings.YEM_GEMINI_MODEL
    if not key:
        status = "key_missing"
    elif not model:
        status = "model_missing"
    else:
        try:
            header_adapter("gemini", model=model, api_key=key)
        except ValueError:
            status = "invalid_configuration"
        else:
            status = "ready_unverified"
    return {"status": status}


def simulate_gemini():
    def fixture(url, auth, payload):
        return {"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": '{"0":"balance","1":"payment_candidate"}'}],
        }}]}

    advisor = header_adapter(
        "gemini", model="fixture-model", api_key="fixture-key", transport=fixture,
    )
    result = IntelligenceEngine(header_advisor=advisor).classify_headers({
        "0": "solde", "1": "versement", "2": "octobre",
    })
    return result.source == "advisor" and result.hints == {
        "0": "balance", "1": "payment_candidate", "2": "ambiguous",
    }
