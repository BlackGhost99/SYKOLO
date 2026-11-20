"""Local, deterministic analysis for YEM Intelligence migration.

No row values, external provider, credentials or writes. Column classifications
are advisory; never treat a header or a non-empty cell as proof of payment.
"""
import re

from .import_service import normalized, suggested_mapping
from .intelligence_engine import engine

MONTH = re.compile(r"\b(?:janvier|janv|fevrier|fevr|mars|avril|avr|mai|juin|juillet|juil|aout|septembre|sept|octobre|oct|novembre|nov|decembre|dec)\b")
FINANCE = re.compile(r"\b(?:paiements?|payes?|payee?s?|versements?|verses?|reglements?|encaisses?|encaissements?|scolarite|mensualites?|frais|montants?|soldes?|impayes?|restes?|bourses?|exonerations?|remises?|acomptes?|recus?|factures?)\b")


def analyze_import_headers(headers, custom_fields=()):
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
    return {
        "engine": "local",
        "version": 2,
        "external_provider_used": False,
        "financial_columns": financial,
        "financial_hints": engine.classify_headers(candidates).hints,
        "unmapped_columns": unmapped,
        "financial_import_available": False,
    }
