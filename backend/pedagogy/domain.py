import math
from decimal import Decimal, ROUND_HALF_UP


class ValidationError(ValueError):
    pass


def fail(message):
    raise ValidationError(message)


def number(value, label, minimum, maximum):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not minimum <= value <= maximum
        or not math.isfinite(value)
    ):
        fail(f"{label} : nombre attendu entre {minimum} et {maximum}.")


def text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 120:
        fail(f"{label} : texte de 1 à 120 caractères attendu.")


def validate_policy(p):
    if (
        not isinstance(p, dict)
        or p.get("schemaVersion") != 1
        or isinstance(p.get("schemaVersion"), bool)
    ):
        fail("Version de configuration non prise en charge.")
    text(p.get("name"), "Nom du profil")
    scale = p.get("scale")
    if (
        not isinstance(scale, dict)
        or not isinstance(scale.get("kind"), str)
        or scale.get("kind")
        not in {
            "numeric",
            "percentage",
            "letters",
            "appreciation",
            "competency",
        }
    ):
        fail("Type de barème inconnu.")
    number(scale.get("max"), "Maximum", 0.01, 100000)
    number(p.get("precision"), "Décimales", 0, 4)
    if int(p["precision"]) != p["precision"]:
        fail("Le nombre de décimales doit être entier.")
    if not isinstance(p.get("missing"), str) or p.get("missing") not in {
        "exclude",
        "zero",
    }:
        fail("Gestion des absences inconnue.")
    bands = p.get("bands")
    if not isinstance(bands, list) or not 1 <= len(bands) <= 30:
        fail("Prévoir de 1 à 30 niveaux.")
    for band in bands:
        if not isinstance(band, dict):
            fail("Niveau invalide.")
        number(band.get("min"), "Seuil (%)", 0, 100)
        text(band.get("label"), "Libellé")
    bands = sorted(bands, key=lambda b: b["min"])
    if bands[0]["min"] != 0:
        fail("Le premier seuil doit commencer à 0 %.")
    if len({b["min"] for b in bands}) != len(bands):
        fail("Les seuils doivent être distincts.")
    if len({b["label"].strip() for b in bands}) != len(bands):
        fail("Les libellés doivent être distincts.")
    for i, b in enumerate(bands):
        upper = bands[i + 1]["min"] if i + 1 < len(bands) else 100
        number(b.get("value"), "Équivalence (%)", b["min"], upper)
        if i + 1 < len(bands) and b["value"] == upper:
            fail("Une équivalence doit rester dans son niveau.")
    report = p.get("report")
    if not isinstance(report, dict) or any(
        type(report.get(k)) is not bool for k in ["showScore", "showLabel"]
    ):
        fail("Options de bulletin invalides.")
    if not report["showScore"] and not report["showLabel"]:
        fail("Le bulletin doit afficher au moins un résultat.")
    notification = p.get("notification")
    if (
        not isinstance(notification, dict)
        or type(notification.get("enabled")) is not bool
    ):
        fail("Règle de notification invalide.")
    number(notification.get("below"), "Seuil de notification (%)", 0, 100)
    text(notification.get("message"), "Message de notification")
    return p


def evaluate(policy, entries):
    validate_policy(policy)
    if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
        fail("Prévoir de 1 à 100 évaluations.")
    total = Decimal(0)
    weights = Decimal(0)
    numeric = policy["scale"]["kind"] in {"numeric", "percentage"}
    maximum = 100 if policy["scale"]["kind"] == "percentage" else policy["scale"]["max"]
    for entry in entries:
        if not isinstance(entry, dict) or "score" not in entry:
            fail("Évaluation invalide.")
        number(entry.get("weight"), "Coefficient", 0.01, 1000)
        score = entry["score"]
        if score is None and policy["missing"] == "exclude":
            continue
        percent = Decimal(0)
        if score is not None:
            if numeric:
                number(score, "Note", 0, maximum)
                percent = Decimal(str(score)) / Decimal(str(maximum)) * 100
            else:
                band = next((b for b in policy["bands"] if b["label"] == score), None)
                if band is None:
                    fail("Niveau inconnu dans une évaluation.")
                percent = Decimal(str(band["value"]))
        weight = Decimal(str(entry["weight"]))
        total += percent * weight
        weights += weight
    if weights == 0:
        return {
            "status": "empty",
            "score": None,
            "percent": None,
            "label": None,
            "notification": None,
        }
    raw = total / weights
    label = next(
        b["label"]
        for b in sorted(policy["bands"], key=lambda b: b["min"], reverse=True)
        if raw >= Decimal(str(b["min"]))
    )
    score = (raw / 100 * Decimal(str(maximum))).quantize(
        Decimal(10) ** -int(policy["precision"]), rounding=ROUND_HALF_UP
    )
    return {
        "status": "calculated",
        "score": float(score),
        "percent": float(raw.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)),
        "label": label,
        "notification": policy["notification"]["message"]
        if policy["notification"]["enabled"]
        and raw < Decimal(str(policy["notification"]["below"]))
        else None,
    }
