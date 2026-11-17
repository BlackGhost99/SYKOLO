"""Append-only commercial amendments and explicit, non-billing trials."""
from datetime import date, timedelta
from .subscription_pricing import add_months, CYCLE_ORDER
from .subscription_models import PlatformSubscription, PlatformSubscriptionTrial


def amendment_rows(row):
    return sorted(row.amendments.all(), key=lambda item: item.revision)


def effective_ledger(row, amendments=None):
    amendments = amendment_rows(row) if amendments is None else amendments
    terms = dict(row.commercial_terms or {})
    schedule = list(terms.get("schedule", []))
    for item in amendments:
        if item.amount_xaf:
            schedule.append({"kind": "avenant", "number": item.revision,
                             "due_date": item.effective_on.isoformat(), "amount_xaf": item.amount_xaf})
    # Original instalments keep their original obligations, including same-day priority.
    schedule.sort(key=lambda item: (item["due_date"], item["kind"] == "avenant"))
    terms["schedule"] = schedule
    return row.total_xaf + sum(a.amount_xaf for a in amendments), terms


def amendment_quote(row, counts, today):
    terms = row.commercial_terms or {}
    initial_schedule = [s for s in terms.get("schedule", []) if s["kind"] == "abonnement"]
    if not initial_schedule:
        raise ValueError("Contrat historique sans échéancier : avenant manuel nécessaire.")
    start = date.fromisoformat(initial_schedule[0]["due_date"])
    end = add_months(start, 12)
    if not start <= today < end:
        raise ValueError("La date doit être dans la période commerciale de douze mois.")
    frozen = {line["cycle"]: line for line in row.lines}
    if set(counts) != set(frozen):
        raise ValueError("Les cycles ont changé : révision commerciale spécifique nécessaire.")
    amendments = amendment_rows(row)
    if amendments and today < amendments[-1].effective_on:
        raise ValueError("Date antérieure au dernier avenant.")
    old = (amendments[-1].snapshot["billed_counts"] if amendments else
           {key: value["students"] for key, value in frozen.items()})
    billed = {key: max(counts[key], old[key]) for key in frozen}
    days = (end - today).days
    duration = (end - start).days
    additions = []
    # Round the total prorated premium once, using integer arithmetic (half up).
    weighted = 0
    for key in CYCLE_ORDER:
        if key not in frozen or billed[key] == old[key]:
            continue
        number = billed[key] - old[key]
        rate = frozen[key]["rate_xaf"]
        weighted += number * rate * days
        additions.append({"cycle": key, "label": frozen[key]["label"],
                          "students": number, "rate_xaf": rate})
    gross = (2 * weighted + duration) // (2 * duration)
    previous_gross = sum(a.snapshot["gross_prorata_xaf"] for a in amendments)
    headroom = terms["minimum_adjustment_xaf"]
    absorbed = min(gross, max(0, headroom - previous_gross))
    return {"revision": len(amendments)+1, "effective_on": today.isoformat(),
            "service_end_exclusive": end.isoformat(), "remaining_days": days,
            "duration_days": duration, "counts": counts, "billed_counts": billed,
            "additions": additions, "gross_prorata_xaf": gross,
            "minimum_absorbed_xaf": absorbed, "amount_xaf": gross - absorbed}


def serialize_amendment(item):
    return {"id": item.pk, "revision": item.revision, "effective_on": item.effective_on.isoformat(),
            "amount_xaf": item.amount_xaf, "snapshot": item.snapshot, "issued_at": item.issued_at.isoformat()}


def trial_summary(school, today):
    row = PlatformSubscriptionTrial.objects.filter(school=school, year__school=school).first()
    if row is None:
        return None
    converted = PlatformSubscription.objects.filter(year__school=school).exists()
    return {"year_id": str(row.year_id), "starts_on": row.starts_on.isoformat(),
            "ends_before": row.ends_before.isoformat(), "status": "converted" if converted else
            "scheduled" if today < row.starts_on else "active" if today < row.ends_before else "expired"}


def start_trial(school, year, today, days, reason, user):
    if type(days) is not int or not 1 <= days <= 90:
        raise ValueError("Durée d'essai entre 1 et 90 jours.")
    if not school.is_active or not year.active or year.status == "closed" or today > year.end_date:
        raise ValueError("Établissement ou année non ouverte.")
    if PlatformSubscription.objects.filter(year__school=school).exists():
        raise ValueError("Un établissement déjà abonné ne peut pas ouvrir un essai.")
    if PlatformSubscriptionTrial.objects.filter(school=school).exists():
        raise ValueError("Un essai a déjà été accordé à cet établissement.")
    starts = max(today, year.start_date)
    ends = starts + timedelta(days=days)
    if ends > year.end_date + timedelta(days=1):
        raise ValueError("L'essai doit se terminer dans l'année pédagogique choisie.")
    return PlatformSubscriptionTrial.objects.create(school=school, year=year,
        starts_on=starts, ends_before=ends, reason=reason, issued_by=user)
