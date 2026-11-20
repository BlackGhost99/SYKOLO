"""Validated advice about candidate headers. The only wired advisor runs locally."""
import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .intelligence_numbering import suggest_series

logger = logging.getLogger(__name__)


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


COLUMN_INDEX = re.compile(r"0|[1-9][0-9]{0,3}")
FINANCIAL_KINDS = frozenset(kind for kind, _ in FINANCIAL_TYPES) | {"ambiguous"}
HeaderAdvisor = Callable[[dict[str, tuple[str, ...]]], dict[str, str]]


@dataclass(frozen=True)
class HeaderAdvice:
    hints: dict[str, str]
    source: str


def local_header_advisor(headers: dict[str, str]) -> dict[str, str]:
    return {column: local_financial_kind(name) for column, name in headers.items()}


def advisory_clues(headers: dict[str, str]) -> dict[str, tuple[str, ...]]:
    """Project candidate labels to approved vocabulary before any adapter runs."""
    return {
        index: tuple(dict.fromkeys(
            clue
            for _, pattern in FINANCIAL_TYPES
            for clue in pattern.findall(name)
        ))[:8]
        for index, name in headers.items()
    }


class IntelligenceEngine:
    """Routes advisory tasks. No adapter is registered in the application."""

    def __init__(self, *, header_advisor: HeaderAdvisor | None = None):
        self._header_advisor = header_advisor

    def capabilities(self) -> dict:
        return {
            "financial_headers": True,
            "numbering_suggestions": True,
            "header_adapter_configured": self._header_advisor is not None,
        }

    def classify_headers(self, headers: dict[str, str]) -> HeaderAdvice:
        if not headers or self._header_advisor is None:
            return HeaderAdvice(local_header_advisor(headers), "local")

        if any(type(index) is not str or not COLUMN_INDEX.fullmatch(index) for index in headers):
            logger.warning("Intelligence header advisor skipped invalid column indices")
            return HeaderAdvice(local_header_advisor(headers), "local_fallback")

        clues = {index: tokens for index, tokens in advisory_clues(headers).items() if tokens}
        if not clues:
            return HeaderAdvice(local_header_advisor(headers), "local")

        try:
            advice = self._header_advisor(clues)
        except Exception:
            # Exception text can carry inputs or credentials.
            logger.warning("Intelligence header advisor unavailable")
        else:
            if (type(advice) is dict and advice.keys() == clues.keys()
                    and all(type(kind) is str and kind in FINANCIAL_KINDS for kind in advice.values())):
                hints = {
                    index: advice[index] if index in advice else local_financial_kind(name)
                    for index, name in headers.items()
                }
                return HeaderAdvice(hints, "advisor")
            logger.warning("Intelligence header advisor returned invalid categories")

        return HeaderAdvice(local_header_advisor(headers), "local_fallback")

    def suggest_numbering(self, codes: Iterable[str | None]) -> dict:
        """Matricules stay in the local deterministic task."""
        return suggest_series(codes)


engine = IntelligenceEngine()
