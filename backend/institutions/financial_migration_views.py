"""Read-only financial migration preview; the workbook is never executed or stored.

An explicit mapping links a column of cumulative historic amounts to a tariff.
No payment, balance adjustment, admission fee or receipt is created here.
"""
import json
import re
import hashlib
from collections import Counter
from decimal import Decimal
from uuid import UUID
from django.db import transaction

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.views import authorized
from .academic_models import AcademicYear
from .admission_scholarship_amounts import tuition_discount
from .finance_evidence import explicit_demo
from .finance_models import (
    FeeCharge,
    FeeSchedule,
    HistoricalFinancialMigration,
    HistoricalFinancialMigrationEntry,
    HistoricalFeeAdjustment,
)
from .finance_views import cleared_total, gate, iso_day
from .import_views import inputs
from .import_service import suggested_mapping
from .intelligence_import import analyze_import_headers
from .student_models import Enrollment

MAX_CELLS = 2000
XAF = re.compile(r"(?:0|[1-9][0-9]{0,9}|[1-9][0-9]{0,2}(?: [0-9]{3}){1,3})(?:[.,]00)?\Z")


def historical_amount(value):
    """Blank is unknown, zero is explicit, and ambiguous formats are rejected."""
    value = value.strip().replace("\u00a0", " ").replace("\u202f", " ")
    if not value:
        return None
    if not XAF.fullmatch(value):
        raise ValueError("Montant XAF entier non ambigu requis.")
    amount = Decimal(value.replace(" ", "").replace(",", "."))
    if amount > 9999999999:
        raise ValueError("Montant hors limites.")
    return amount


def fmt(value):
    return None if value is None else str(value.quantize(Decimal("0.01")))


def index(value, headers):
    if type(value) is not int or not 0 <= value < len(headers):
        raise ValueError("Indice de colonne invalide.")
    return value


def mapped_schedules(school, year, table, mapping):
    if not isinstance(mapping, dict) or set(mapping) != {"student_code", "amounts"}:
        raise ValueError("Associez explicitement le matricule et les colonnes de montants.")
    code_index = index(mapping["student_code"], table["headers"])
    amounts = mapping["amounts"]
    if not isinstance(amounts, list) or not amounts or len(amounts) > 12:
        raise ValueError("Associez entre 1 et 12 colonnes à des tarifs.")
    if len(table["rows"]) * len(amounts) > MAX_CELLS:
        raise ValueError("Limitez un aperçu à 2 000 cellules financières.")
    indices, ids, pairs = {code_index}, set(), []
    for entry in amounts:
        if not isinstance(entry, dict) or set(entry) != {"column", "schedule"}:
            raise ValueError("Correspondance de tarif invalide.")
        col = index(entry["column"], table["headers"])
        schedule_id = UUID(str(entry["schedule"]))
        if col in indices or schedule_id in ids:
            raise ValueError("Une colonne ou un tarif ne peut être associé deux fois.")
        indices.add(col)
        ids.add(schedule_id)
        schedule = FeeSchedule.objects.filter(
            school=school, year=year, pk=schedule_id, active=True, currency="XAF",
        ).first()
        if schedule is None or explicit_demo(schedule.label):
            raise ValueError("Tarif XAF actif non démonstratif introuvable pour cette école et cette année.")
        # Admission charges have a dedicated ledger in YEM and are not inferred here.
        pairs.append((col, schedule))
    return code_index, pairs


def cell_preview(school, enrollment, schedule, value, cutoff):
    if schedule.classroom_id and schedule.classroom_id != enrollment.classroom_id:
        raise ValueError("Tarif incompatible avec la classe.")
    if schedule.due_date and schedule.due_date > cutoff:
        raise ValueError("Échéance postérieure à la date de reprise.")
    imported = historical_amount(value)
    charge = FeeCharge.objects.filter(school=school, enrollment=enrollment, schedule=schedule).first()
    if charge and (charge.currency != "XAF" or explicit_demo(charge.label)):
        raise ValueError("Frais existant incompatible avec une reprise réelle.")
    gross = charge.amount if charge else schedule.amount
    discount = charge.scholarship_discount if charge else tuition_discount(enrollment, schedule)
    due = gross - discount
    booked = cleared_total(charge) if charge else Decimal("0")
    if imported is None:
        state = "unknown"
    elif imported > due or booked > due:
        state = "overpayment"
    elif booked != 0:
        state = "existing_review"  # No subtraction or replay assumption from cumulative totals.
    elif imported == 0:
        state = "zero"
    else:
        state = "proposed"
    return {"status": state, "declared": fmt(imported), "gross": fmt(gross),
            "scholarship": fmt(discount), "net_due": fmt(due), "already_booked": fmt(booked),
            "declared_balance": fmt(due - imported) if imported is not None and imported <= due else None,
            "charge_exists": bool(charge)}


@never_cache
@require_POST
@authorized
def inspect(request, school_id):
    school, error = gate(request, school_id, "school.finance.approve")
    if error is not None:
        return error
    try:
        table = inputs(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    years = AcademicYear.objects.filter(school=school, active=True).exclude(
        status=AcademicYear.STATUS_CLOSED).order_by("-start_date")
    tariffs = FeeSchedule.objects.filter(school=school, year__in=years, active=True,
        currency="XAF").select_related("classroom").order_by("due_date", "label", "pk")
    mapping = suggested_mapping(table["headers"])
    return JsonResponse({
        "headers": table["headers"], "sheet": table["sheet"], "sheets": table["sheets"],
        "header_row": table["header_row"], "row_count": len(table["rows"]),
        "suggested_student_code": next((int(col) for col, field in mapping.items() if field == "student_code"), None),
        "financial_columns": analyze_import_headers(table["headers"])["financial_columns"],
        "years": [{"id": str(y.pk), "name": y.name, "start": y.start_date.isoformat(),
                   "end": y.end_date.isoformat(), "status": y.status} for y in years],
        "tariffs": [{"id": str(t.pk), "year": str(t.year_id), "label": t.label, "code": t.code,
                     "classroom": t.classroom.name if t.classroom_id else None, "amount": str(t.amount),
                     "due_date": t.due_date.isoformat() if t.due_date else None}
                    for t in tariffs if not explicit_demo(t.label)],
        "today": timezone.localdate().isoformat(),
        "notice": "Analyse locale sans enregistrement. Les montants ne sont pas confirmés.",
    })


@never_cache
@require_POST
@authorized
def preview(request, school_id):
    # Only the accounting approval role may inspect financial migration data.
    school, error = gate(request, school_id, "school.finance.approve")
    if error is not None:
        return error
    try:
        table = inputs(request)
        raw = request.POST.get("mapping", "")
        if len(raw) > 10000:
            raise ValueError("Correspondances trop volumineuses.")
        year = AcademicYear.objects.filter(
            pk=UUID(request.POST.get("year", "")), school=school, active=True,
        ).exclude(status=AcademicYear.STATUS_CLOSED).first()
        if year is None:
            raise ValueError("Année ouverte introuvable.")
        cutoff = iso_day(request.POST.get("cutoff", ""))
        if not year.start_date <= cutoff <= min(year.end_date, timezone.localdate()):
            raise ValueError("Date de reprise hors année ou future.")
        code_index, pairs = mapped_schedules(school, year, table, json.loads(raw))
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    codes = Counter(row["cells"][code_index].casefold() for row in table["rows"])
    reports = []
    for row in table["rows"]:
        code = row["cells"][code_index]
        enrollments = list(Enrollment.objects.filter(
            school=school, year=year, active=True, student__school=school,
            student__active=True, student__student_code__iexact=code,
            classroom__school=school, classroom__year=year,
        ).select_related("student")[:2]) if code and codes[code.casefold()] == 1 else []
        if len(enrollments) != 1:
            reports.append({"line": row["line"], "status": "identity_review", "cells": []})
            continue
        enrollment = enrollments[0]
        cells = []
        for col, schedule in pairs:
            try:
                item = cell_preview(school, enrollment, schedule, row["cells"][col], cutoff)
            except ValueError as exc:
                item = {"status": "invalid", "error": str(exc)}
            cells.append({"column": col, "schedule": str(schedule.pk), **item})
        reports.append({"line": row["line"], "status": "resolved", "cells": cells})
    counts = Counter(cell["status"] for row in reports for cell in row["cells"])
    counts["identity_review"] = sum(row["status"] == "identity_review" for row in reports)
    return JsonResponse({
        "mode": "preview_only", "commit_available": False, "currency": "XAF",
        "cutoff": cutoff.isoformat(), "rows": reports, "counts": dict(counts),
        "notice": "Aucun frais, paiement, reçu ni solde modifié. Montants déclarés à justifier.",
    })


def preview_data(school, school_id, request):
    table = inputs(request)
    raw = request.POST.get("mapping", "")
    if len(raw) > 10000:
        raise ValueError("Correspondances trop volumineuses.")
    year = AcademicYear.objects.filter(
        pk=UUID(request.POST.get("year", "")), school=school, active=True,
    ).exclude(status=AcademicYear.STATUS_CLOSED).first()
    if year is None:
        raise ValueError("Année ouverte introuvable.")
    cutoff = iso_day(request.POST.get("cutoff", ""))
    if not year.start_date <= cutoff <= min(year.end_date, timezone.localdate()):
        raise ValueError("Date de reprise hors année ou future.")
    code_index, pairs = mapped_schedules(school, year, table, json.loads(raw))

    upload = request.FILES.get("file")
    upload.seek(0)
    payload = upload.read()
    upload.seek(0)
    canonical = json.dumps({
        "year": str(year.pk), "cutoff": cutoff.isoformat(), "mapping": json.loads(raw),
        "file": hashlib.sha256(payload).hexdigest(),
    }, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    codes = Counter(row["cells"][code_index].casefold() for row in table["rows"])
    entries = []
    reports = []
    for row in table["rows"]:
        code = row["cells"][code_index]
        enrollments = list(Enrollment.objects.filter(
            school=school, year=year, active=True, student__school=school,
            student__active=True, student__student_code__iexact=code,
            classroom__school=school, classroom__year=year,
        ).select_related("student")[:2]) if code and codes[code.casefold()] == 1 else []
        if len(enrollments) != 1:
            reports.append({"line": row["line"], "status": "identity_review", "cells": []})
            continue
        enrollment = enrollments[0]
        cells = []
        for col, schedule in pairs:
            try:
                item = cell_preview(school, enrollment, schedule, row["cells"][col], cutoff)
            except ValueError as exc:
                item = {"status": "invalid", "error": str(exc)}
            cells.append({"column": col, "schedule": str(schedule.pk), **item})
            if item["status"] in {"proposed", "zero", "unknown"}:
                entries.append({
                    "line": row["line"], "enrollment": enrollment, "schedule": schedule,
                    "state": item["status"], "declared": None if item["declared"] is None else Decimal(item["declared"]),
                    "net_due": Decimal(item["net_due"]), "scholarship": Decimal(item["scholarship"]),
                    "evidence_reference": "",
                })
        reports.append({"line": row["line"], "status": "resolved", "cells": cells})
    return year, cutoff, fingerprint, upload.name, table, reports, entries


@never_cache
@require_POST
@authorized
def prepare(request, school_id):
    school, error = gate(request, school_id, "school.finance.receive")
    if error is not None:
        return error
    try:
        year, cutoff, fingerprint, source_name, table, reports, entries = preview_data(
            school, school_id, request
        )
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    if any(row["status"] == "identity_review" for row in reports):
        return JsonResponse({"error": "Régularisez les identités avant préparation."}, status=422)
    if any(
        item["status"] in {"invalid", "overpayment", "existing_review"}
        for row in reports for item in row["cells"]
    ):
        return JsonResponse({"error": "Aucun montant invalide, dépassé ou déjà comptabilisé ne peut être préparé."}, status=422)

    existing = HistoricalFinancialMigration.objects.filter(
        school=school, fingerprint=fingerprint
    ).first()
    if existing:
        return JsonResponse({"batch": str(existing.pk), "status": existing.status,
                             "idempotent": True, "row_count": existing.row_count})
    with transaction.atomic():
        batch = HistoricalFinancialMigration.objects.create(
            school=school, year=year, cutoff=cutoff, fingerprint=fingerprint,
            source_reference=source_name[:255], row_count=len(table["rows"]),
            prepared_by=request.user,
        )
        for entry in entries:
            HistoricalFinancialMigrationEntry.objects.create(
                batch=batch, school=school, enrollment=entry["enrollment"],
                schedule=entry["schedule"], source_row=entry["line"],
                state=entry["state"], declared_amount=entry["declared"],
                net_due=entry["net_due"], scholarship=entry["scholarship"],
                evidence_reference=entry["evidence_reference"],
            )
    return JsonResponse({"batch": str(batch.pk), "status": batch.status,
                         "idempotent": False, "row_count": batch.row_count})


@never_cache
@require_POST
@authorized
def approve(request, school_id, batch_id):
    school, error = gate(request, school_id, "school.finance.approve")
    if error is not None:
        return error
    reason = request.POST.get("reason", "").strip()
    if len(reason) < 5:
        return JsonResponse({"error": "Justificatif comptable requis."}, status=422)
    try:
        with transaction.atomic():
            batch = HistoricalFinancialMigration.objects.select_for_update().filter(
                school=school, pk=batch_id
            ).first()
            if batch is None:
                return JsonResponse({"error": "Lot introuvable."}, status=404)
            if batch.status == HistoricalFinancialMigration.STATUS_APPROVED:
                return JsonResponse({"batch": str(batch.pk), "status": "approved", "idempotent": True})
            if batch.status != HistoricalFinancialMigration.STATUS_PREPARED:
                return JsonResponse({"error": "Lot annulé ou déjà clôturé."}, status=409)
            if batch.prepared_by_id == request.user.pk:
                return JsonResponse({"error": "Le préparateur ne peut pas approuver son propre lot."}, status=403)
            if batch.year.status == AcademicYear.STATUS_CLOSED:
                return JsonResponse({"error": "Année scolaire clôturée."}, status=409)

            entries = list(batch.entries.select_for_update().select_related(
                "enrollment", "schedule"
            ))
            for entry in entries:
                if entry.schedule.classroom_id and entry.schedule.classroom_id != entry.enrollment.classroom_id:
                    raise ValueError("Tarif incompatible avec la classe.")
                if entry.schedule.due_date and entry.schedule.due_date > batch.cutoff:
                    raise ValueError("Échéance postérieure à la date de reprise.")
                charge = FeeCharge.objects.select_for_update().filter(
                    school=school, enrollment=entry.enrollment, schedule=entry.schedule
                ).first()
                if charge is None:
                    charge = FeeCharge.objects.create(
                        school=school, enrollment=entry.enrollment, schedule=entry.schedule,
                        label=entry.schedule.label, amount=entry.schedule.amount,
                        scholarship_discount=entry.scholarship,
                        currency=entry.schedule.currency, due_date=entry.schedule.due_date,
                        created_by=batch.prepared_by,
                    )
                elif cleared_total(charge) != 0:
                    raise ValueError("Des paiements ou ajustements existent déjà pour ce frais.")
                entry.charge = charge
                entry.save(update_fields=["charge"])
                if entry.state == "proposed" and entry.declared_amount:
                    if entry.declared_amount > charge.amount - charge.scholarship_discount:
                        raise ValueError("Montant historique supérieur au dû.")
                    HistoricalFeeAdjustment.objects.create(
                        school=school, batch=batch, charge=charge,
                        amount=entry.declared_amount, currency=charge.currency,
                        cutoff=batch.cutoff, evidence_reference=reason[:255],
                        approved_by=request.user,
                    )
            batch.status = HistoricalFinancialMigration.STATUS_APPROVED
            batch.approved_by = request.user
            batch.approved_at = timezone.now()
            batch.save(update_fields=["status", "approved_by", "approved_at"])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    return JsonResponse({"batch": str(batch.pk), "status": "approved", "idempotent": False})


@never_cache
@require_POST
@authorized
def cancel(request, school_id, batch_id):
    school, error = gate(request, school_id, "school.finance.receive")
    if error is not None:
        return error
    reason = request.POST.get("reason", "").strip()
    if len(reason) < 5:
        return JsonResponse({"error": "Motif d'annulation requis."}, status=422)
    with transaction.atomic():
        batch = HistoricalFinancialMigration.objects.select_for_update().filter(
            school=school, pk=batch_id
        ).first()
        if batch is None:
            return JsonResponse({"error": "Lot introuvable."}, status=404)
        if batch.status == HistoricalFinancialMigration.STATUS_APPROVED:
            return JsonResponse({"error": "Un lot approuvé ne peut pas être annulé par cette opération."}, status=409)
        if batch.status == HistoricalFinancialMigration.STATUS_CANCELLED:
            return JsonResponse({"batch": str(batch.pk), "status": "cancelled", "idempotent": True})
        batch.status = HistoricalFinancialMigration.STATUS_CANCELLED
        batch.cancelled_at = timezone.now()
        batch.cancellation_reason = reason[:1000]
        batch.save(update_fields=["status", "cancelled_at", "cancellation_reason"])
    return JsonResponse({"batch": str(batch.pk), "status": "cancelled", "idempotent": False})
