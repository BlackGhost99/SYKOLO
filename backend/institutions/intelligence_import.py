"""Local, deterministic analysis for YEM Intelligence migration.

No row values, external provider, credentials or writes. Column classifications
are advisory; never treat a header or a non-empty cell as proof of payment.
"""
import re

from .import_service import normalized, suggested_mapping

MONTH = re.compile(r"\b(?:janvier|janv|fevrier|fevr|mars|avril|avr|mai|juin|juillet|juil|aout|septembre|sept|octobre|oct|novembre|nov|decembre|dec)\b")
FINANCE = re.compile(r"\b(?:paiements?|payes?|payee?s?|versements?|verses?|reglements?|encaisses?|encaissements?|scolarite|mensualites?|frais|montants?|soldes?|impayes?|restes?|bourses?|exonerations?|remises?|acomptes?|recus?|factures?)\b")


FINANCIAL_TYPES = (
    ("balance", re.compile(r"\b(?:soldes?|impayes?|restes?)\b")),
    ("scholarship", re.compile(r"\b(?:bourses?|exonerations?|remises?)\b")),
    ("billing", re.compile(r"\b(?:frais|factures?|echeances?|scolarite)\b")),
    ("payment_candidate", re.compile(r"\b(?:payes?|paiements?|acomptes?|versements?|encaisses?|reglements?)\b")),
)


def local_financial_kind(name):
    for kind, pattern in FINANCIAL_TYPES:
        if pattern.search(name):
            return kind
    return "ambiguous"


def analyze_import_headers(headers, custom_fields=()):
    mapping = suggested_mapping(headers, custom_fields)
    financial = []
    unmapped = []
    financial_hints = {}
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
            financial_hints[key] = local_financial_kind(name)
        else:
            unmapped.append(index)
    return {
        "engine": "local",
        "version": 2,
        "external_provider_used": False,
        "financial_columns": financial,
        "financial_hints": financial_hints,
        "unmapped_columns": unmapped,
        "financial_import_available": False,
    }
