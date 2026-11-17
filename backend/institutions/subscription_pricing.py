"""Commercial arithmetic: FCFA integers, whole-school minimum, no automatic discount."""
from calendar import monthrange
from datetime import date
from .school_profiles import CYCLE_LABELS

DEFAULT_RATES = {"prescolaire": 1000, "primaire": 1500, "college": 2000,
                 "lycee_general": 2000, "lycee_technique": 2000}
DEFAULT_MINIMUMS = {"prescolaire": 50000, "primaire": 75000, "college": 100000,
                    "lycee_general": 100000, "lycee_technique": 100000}
PERIODS = {"annuel": 1, "semestriel": 2, "trimestriel": 4}
CYCLE_ORDER = list(DEFAULT_RATES)


def validate_schedule(values):
    if not isinstance(values, dict) or set(values) != set(DEFAULT_RATES):
        raise ValueError("Renseignez les cinq cycles.")
    if any(type(v) is not int or not 0 <= v <= 10000000 for v in values.values()):
        raise ValueError("Saisissez des montants FCFA entiers entre 0 et 10 000 000.")
    return values


def quote_lines(counts, rates):
    if not isinstance(rates, dict) or set(rates) != set(counts):
        raise ValueError("Indiquez un tarif pour chaque cycle.")
    if any(type(value) is not int or not 0 <= value <= 10000000 for value in rates.values()):
        raise ValueError("Les tarifs doivent être des francs CFA entiers positifs ou nuls.")
    if not set(counts).issubset(CYCLE_LABELS):
        raise ValueError("Cycle non reconnu : corrigez la classification de l'établissement.")
    return [{"cycle": code, "label": CYCLE_LABELS[code], "students": counts[code],
             "rate_xaf": rates[code], "amount_xaf": counts[code] * rates[code]}
            for code in CYCLE_ORDER if code in counts]


def setup_fee(count):
    return 50000 if count <= 150 else 75000 if count <= 500 else 100000 if count <= 1000 else 150000


def add_months(day, months):
    y, m = divmod(day.year * 12 + day.month - 1 + months, 12)
    return date(y, m + 1, min(day.day, monthrange(y, m + 1)[1]))


def calculate_terms(counts, rates, minimums, *, period="annuel", discount=0,
                    setup=0, first_due, revision=1):
    lines = quote_lines(counts, rates)
    if not lines:
        raise ValueError("Configurez au moins un cycle avant de créer un abonnement.")
    minimum = max(minimums[k] for k in counts)
    gross = sum(line["amount_xaf"] for line in lines)
    annual_before_discount = max(minimum, gross)
    if type(discount) is not int or not 0 <= discount <= annual_before_discount:
        raise ValueError("Remise exceptionnelle invalide.")
    if type(setup) is not int or setup < 0 or period not in PERIODS:
        raise ValueError("Modalité de règlement ou mise en service invalide.")
    annual = annual_before_discount - discount
    count = PERIODS[period]
    share, remainder = divmod(annual, count)
    schedule = [{"kind": "abonnement", "number": n + 1,
                 "due_date": add_months(first_due, n * (12 // count)).isoformat(),
                 "amount_xaf": share + (1 if n < remainder else 0)}
                for n in range(count)]
    if setup:
        schedule.insert(0, {"kind": "mise_en_service", "number": 0,
                            "due_date": first_due.isoformat(), "amount_xaf": setup})
    return {"policy_revision": revision, "student_count": sum(counts.values()),
            "minimums": {k: minimums[k] for k in counts},
            "gross_xaf": gross, "minimum_xaf": minimum,
            "minimum_adjustment_xaf": annual_before_discount - gross,
            "discount_xaf": discount, "annual_xaf": annual, "setup_xaf": setup,
            "total_xaf": annual + setup, "period": period, "schedule": schedule}


def schedule_balances(terms, paid, today):
    remaining = paid
    result = []
    for item in terms.get("schedule", []):
        settled = min(remaining, item["amount_xaf"])
        remaining -= settled
        balance = item["amount_xaf"] - settled
        due = date.fromisoformat(item["due_date"])
        days = max(0, (today - due).days) if balance else 0
        result.append({**item, "paid_xaf": settled, "balance_xaf": balance,
                       "days_overdue": days,
                       "status": "paid" if not balance else "overdue" if days else "due" if due == today else "upcoming"})
    return result
