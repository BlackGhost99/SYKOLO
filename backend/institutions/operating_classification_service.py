"""Validate classification choices without changing historical expense labels.

Classification references are optional for pre-existing clients and historical
drafts. New YEM screens use these references. A text-only legacy value stays
readable, but is never silently mapped to an unrelated configured option.
"""
import uuid

from .operating_models import ACTIVITY_POLES, OperatingClassificationOption


def pole_label(school, code, *, require_active=True):
    original = dict(ACTIVITY_POLES).get(code)
    if original is None or code == "unclassified":
        raise ValueError("Pôle de sorties invalide.")
    option = OperatingClassificationOption.objects.filter(
        school=school, kind="pole", code=code,
    ).first()
    if option and not option.active and require_active:
        raise ValueError("Pôle archivé : choisissez un pôle actif.")
    return option.name if option else original


def resolve_option(school, kind, value, activity_pole):
    if not isinstance(value, str) or not value:
        raise ValueError("Identifiant de classification requis.")
    try:
        identifier = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise ValueError("Identifiant de classification invalide.") from None
    option = OperatingClassificationOption.objects.filter(
        school=school, kind=kind, pk=identifier,
    ).first()
    if not option:
        raise LookupError("Classification introuvable dans cet établissement.")
    if not option.active:
        raise ValueError("Classification archivée : choix refusé.")
    if kind == "cost_center" and option.activity_pole and option.activity_pole != activity_pole:
        raise ValueError("Ce centre de coûts n'appartient pas au pôle choisi.")
    return option


def classification_fields(school, data, activity_pole, *, existing=None):
    """Resolve refs and stable text snapshots for both create and draft revision."""
    updates = {}
    for kind, ref, label in (
        ("cost_center", "cost_center_ref", "Centre de coûts"),
        ("accounting_nature", "accounting_nature_ref", "Nature comptable"),
    ):
        if ref in data:
            raw = data[ref]
            if raw in ("", None):
                updates[ref] = None
                # Clearing the ref does not silently discard a historic text
                # value if the caller intentionally retains it.
                text = data.get(kind, "")
                if not isinstance(text, str) or len(text.strip()) > 100:
                    raise ValueError(label + " : texte invalide.")
                updates[kind] = text.strip()
            else:
                option = resolve_option(school, kind, raw, activity_pole)
                updates[ref] = option
                updates[kind] = option.name
        elif kind in data:
            text = data[kind]
            if not isinstance(text, str) or len(text.strip()) > 100:
                raise ValueError(label + " : texte invalide.")
            updates[kind] = text.strip()
            updates[ref] = None
        elif existing is None:
            updates[kind] = ""
            updates[ref] = None
        elif getattr(existing, ref + "_id"):
            # An unchanged referenced center must still fit the chosen pole.
            option = getattr(existing, ref)
            if kind == "cost_center" and option.activity_pole and option.activity_pole != activity_pole:
                raise ValueError("Mettez à jour le centre de coûts avant de changer le pôle.")
    return updates
