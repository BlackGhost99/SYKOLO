"""Validated advice about candidate headers. The only wired advisor runs locally."""
import re
from collections.abc import Callable


FINANCIAL_TYPES = (
    ("balance", re.compile(r"\b(?:soldes?|impayes?|restes?)\b")),
    ("scholarship", re.compile(r"\b(?:bourses?|exonerations?|remises?)\b")),
    ("billing", re.compile(r"\b(?:frais|factures?|echeances?|scolarite)\b")),
    ("payment_candidate", re.compile(r"\b(?:payes?|paiements?|acomptes?|versements?|encaisses?|reglements?)\b")),
)


def local_financial_kind(name: str) -> str:
    for kind, pattern in FINANCIAL_TYPES:
        if pattern.search(name):
            return kind
    return "ambiguous"


FINANCIAL_KINDS = frozenset(kind for kind, _ in FINANCIAL_TYPES) | {"ambiguous"}
HeaderAdvisor = Callable[[dict[str, str]], dict[str, str]]


def local_header_advisor(headers: dict[str, str]) -> dict[str, str]:
    return {column: local_financial_kind(name) for column, name in headers.items()}


def classify_financial_headers(
    headers: dict[str, str], *, advisor: HeaderAdvisor = local_header_advisor,
) -> dict[str, str]:
    """An advisor may label only the candidate indices selected by YEM."""
    if not headers:
        return {}
    try:
        advice = advisor(headers.copy())
        if (type(advice) is dict and advice.keys() == headers.keys()
                and all(type(kind) is str and kind in FINANCIAL_KINDS for kind in advice.values())):
            return advice
    except Exception:
        # Advisor errors can contain header text. Fall back without exposing it.
        return local_header_advisor(headers)
    return local_header_advisor(headers)
