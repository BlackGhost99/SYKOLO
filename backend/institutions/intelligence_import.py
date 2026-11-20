"""Advisory classification of candidate headers without reading workbook rows."""
import re

from .import_service import normalized, suggested_mapping
from .intelligence_engine import engine

MONTH = re.compile(r"\b(?:janvier|janv|fevrier|fevr|mars|avril|avr|mai|juin|juillet|juil|aout|septembre|sept|octobre|oct|novembre|nov|decembre|dec)\b")
FINANCE = re.compile(r"\b(?:paiements?|payes?|payee?s?|versements?|verses?|reglements?|encaisses?|encaissements?|scolarite|mensualites?|frais|montants?|soldes?|impayes?|restes?|bourses?|exonerations?|remises?|acomptes?|recus?|factures?)\b")


def analyze_import_headers(headers, custom_fields=(), *, advisor_engine=engine):
    mapping = suggested_mapping(headers, custom_fields)
    financial = []
    unmapped = []
    candidates = {}
    for index, header in enumerate(headers):
        key = str(index)
        name = normalized(header)
        if not name:
            continue
        # Recognized administrative fields take priority: e.g. date inscription.
        if key in mapping:
            continue
        if (MONTH.search(name) or FINANCE.search(name)
                or name in ("inscription", "reinscription", "reste a payer")):
            financial.append(index)
            candidates[key] = name
        else:
            unmapped.append(index)
    advice = advisor_engine.classify_headers(candidates)
    return {
        "engine": "gemini" if advice.source == "advisor" else "local",
        "advice_source": advice.source,
        "version": 2,
        "external_provider_used": advice.source == "advisor",
        "financial_columns": financial,
        "financial_hints": advice.hints,
        "unmapped_columns": unmapped,
        "financial_import_available": False,
    }
