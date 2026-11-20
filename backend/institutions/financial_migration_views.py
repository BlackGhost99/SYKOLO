"""Historical opening balances; preview is read-only, approval is independent.

No normal payment or receipt is created. Original workbook bytes are not stored.
"""
import json
import re
import hashlib
from collections import Counter
from decimal import Decimal
from uuid import UUID
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_GET

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
from .intelligence_readiness import gemini_available
from .intelligence_live import analyze_financial_headers_with_gemini
from .student_models import Enrollment
from .models import School
from .singpay_models import SingPayIntent
from .views import log_event, access, refuse
from .services import has_permission

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
        raise ValueError("Associez entre 1 et 12 colonnes de montants.")
    if len(table["rows"]) * len(amounts) > MAX_CELLS:
        raise ValueError("Limitez un aperçu à 2 000 cellules financières.")
    indices, ids, pairs = {code_index}, set(), []
    for entry in amounts:
        if not isinstance(entry, dict) or set(entry) not in ({"column", "schedule"}, {"column", "schedules"}):
            raise ValueError("Correspondance de tarif invalide.")
        col = index(entry["column"], table["headers"])
        refs = entry.get("schedules", [entry.get("schedule")])
        if not isinstance(refs, list) or not 1 <= len(refs) <= 100:
            raise ValueError("Associez de 1 à 100 tarifs d'une même période par colonne.")
        schedule_ids = [UUID(str(ref)) for ref in refs]
        if col in indices or len(set(schedule_ids)) != len(schedule_ids) or ids.intersection(schedule_ids):
            raise ValueError("Une colonne ou un tarif ne peut être associé deux fois.")
        indices.add(col)
        ids.update(schedule_ids)
        if len(ids) > 240:
            raise ValueError("Limitez l'association à 240 tarifs par fichier.")
        schedules = list(FeeSchedule.objects.filter(school=school, year=year, pk__in=schedule_ids,
                                                   active=True, currency="XAF"))
        if len(schedules) != len(schedule_ids) or any(explicit_demo(t.label) for t in schedules):
            raise ValueError("Tarif XAF actif non démonstratif introuvable pour cette école et cette année.")
        if len({t.code for t in schedules}) != 1:
            raise ValueError("Les tarifs d'une colonne doivent partager le même code de frais/période.")
        options = {t.classroom_id: t for t in schedules}
        if len(options) != len(schedules):
            raise ValueError("Un seul tarif par classe (ou tarif général) dans chaque colonne.")
        pairs.append((col, options))
    return code_index, pairs


def selected_schedule(enrollment, options):
    # Explicit class-specific selection takes priority over an explicitly
    # selected general fallback. Never guess from a label or amount.
    result = options.get(enrollment.classroom_id, options.get(None))
    if result is None:
        raise ValueError("Aucun tarif associé pour la classe de cet élève.")
    return result


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


def migration_read_gate(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return None, error
    if not any(has_permission(request.user, school, permission) for permission in ("school.finance.receive", "school.finance.approve")):
        return None, refuse()
    return school, None


def batch_data(row, user):
    approved = row.status == row.STATUS_APPROVED
    owns_batch = row.prepared_by_id == user.pk
    can_receive = has_permission(user, row.school, "school.finance.receive")
    can_approve = has_permission(user, row.school, "school.finance.approve")
    year_open = row.year.active and row.year.status != AcademicYear.STATUS_CLOSED
    return {"id": str(row.pk), "year": str(row.year_id), "year_name": row.year.name,
            "cutoff": row.cutoff.isoformat(), "status": row.status,
            "source_reference": row.source_reference, "row_count": row.row_count,
            "prepared_at": row.prepared_at.isoformat(),
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "prepared_by_me": row.prepared_by_id == user.pk,
            "can_approve": row.status == "prepared" and not owns_batch and can_approve,
            "can_cancel": row.status == "prepared" and owns_batch and can_receive,
            "can_request_reversal": approved and year_open and owns_batch and can_receive and not row.reversal_requested_by_id,
            "can_withdraw_reversal": approved and year_open and can_receive and row.reversal_requested_by_id == user.pk,
            "can_confirm_reversal": approved and year_open and can_approve and bool(
                row.reversal_requested_by_id and row.reversal_requested_by_id != user.pk
            ),
            "reversal_pending": approved and bool(row.reversal_requested_by_id),
            "reversal_reason": row.reversal_reason,
            "reversal_evidence": row.reversal_evidence,
            "reversed_at": row.reversed_at.isoformat() if row.reversed_at else None}


def visible_batches(request, school):
    query = HistoricalFinancialMigration.objects.filter(school=school).select_related("year", "school")
    if not has_permission(request.user, school, "school.finance.approve"):
        query = query.filter(prepared_by=request.user)
    return query


@never_cache
@require_GET
@authorized
def batches(request, school_id):
    school, error = migration_read_gate(request, school_id)
    if error is not None:
        return error
    query = visible_batches(request, school)
    year = request.GET.get("year")
    if year:
        try:
            query = query.filter(year_id=UUID(year))
        except ValueError:
            return JsonResponse({"error": "Année invalide."}, status=422)
    return JsonResponse({"batches": [batch_data(row, request.user) for row in query.order_by("-prepared_at", "pk")[:100]],
                         "can_prepare": has_permission(request.user, school, "school.finance.receive")})


@never_cache
@require_GET
@authorized
def batch_detail(request, school_id, batch_id):
    school, error = migration_read_gate(request, school_id)
    if error is not None:
        return error
    row = visible_batches(request, school).filter(pk=batch_id).first()
    if row is None:
        return JsonResponse({"error": "Lot introuvable."}, status=404)
    entries = [{"line": entry.source_row, "student_code": entry.enrollment.student.student_code,
                "schedule": entry.schedule.label, "declared": fmt(entry.declared_amount),
                "net_due": fmt(entry.net_due), "scholarship": fmt(entry.scholarship), "state": entry.state}
               for entry in row.entries.filter(school=school, enrollment__school=school, schedule__school=school)
               .select_related("enrollment__student", "schedule").order_by("source_row", "schedule_id")[:MAX_CELLS]]
    return JsonResponse({**batch_data(row, request.user), "entries": entries})


@never_cache
@require_POST
@authorized
def inspect(request, school_id):
    school, error = migration_read_gate(request, school_id)
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
    available = gemini_available()
    requested = request.POST.get("assistant") == "gemini"
    if available and requested:
        analysis, gemini_status = analyze_financial_headers_with_gemini(table["headers"])
    else:
        analysis = analyze_import_headers(table["headers"])
        gemini_status = "unavailable" if requested else "local"
    return JsonResponse({
        "headers": table["headers"], "sheet": table["sheet"], "sheets": table["sheets"],
        "header_row": table["header_row"], "row_count": len(table["rows"]),
        "suggested_student_code": next((int(col) for col, field in mapping.items() if field == "student_code"), None),
        "financial_columns": analysis["financial_columns"],
        "financial_hints": analysis["financial_hints"],
        "gemini_available": available,
        "gemini_status": gemini_status,
        "years": [{"id": str(y.pk), "name": y.name, "start": y.start_date.isoformat(),
                   "end": y.end_date.isoformat(), "status": y.status} for y in years],
        "tariffs": [{"id": str(t.pk), "year": str(t.year_id), "label": t.label, "code": t.code,
                     "classroom": t.classroom.name if t.classroom_id else None, "classroom_id": str(t.classroom_id) if t.classroom_id else None, "amount": str(t.amount),
                     "due_date": t.due_date.isoformat() if t.due_date else None}
                    for t in tariffs if not explicit_demo(t.label)],
        "today": timezone.localdate().isoformat(),
        "notice": "Analyse locale sans enregistrement. Les montants ne sont pas confirmés.",
    })


@never_cache
@require_POST
@authorized
def preview(request, school_id):
    # Preparation and independent approval both require the financial workspace.
    school, error = migration_read_gate(request, school_id)
    if error is not None:
        return error
    try:
        table = inputs(request)
        raw = request.POST.get("mapping", "")
        if len(raw) > 20000:
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
        for col, options in pairs:
            schedule = None
            try:
                schedule = selected_schedule(enrollment, options)
                item = cell_preview(school, enrollment, schedule, row["cells"][col], cutoff)
            except ValueError as exc:
                item = {"status": "invalid", "error": str(exc)}
            cells.append({"column": col, "schedule": str(schedule.pk) if schedule else None, **item})
        reports.append({"line": row["line"], "status": "resolved", "cells": cells})
    counts = Counter(cell["status"] for row in reports for cell in row["cells"])
    counts["identity_review"] = sum(row["status"] == "identity_review" for row in reports)
    return JsonResponse({
        "mode": "preview_only", "commit_available": False, "currency": "XAF",
        "cutoff": cutoff.isoformat(), "rows": reports, "counts": dict(counts),
        "notice": "Aucun frais, paiement, reçu ni solde modifié. Montants déclarés à justifier.",
    })


def migration_fingerprint(identity):
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def preview_data(school, request):
    table = inputs(request)
    raw = request.POST.get("mapping", "")
    if len(raw) > 20000:
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
    identity = {
        "year": str(year.pk), "cutoff": cutoff.isoformat(), "mapping": json.loads(raw),
        "file": table["sha256"], "sheet": table["sheet"], "header_row": table["header_row"],
    }
    legacy = migration_fingerprint(identity)
    groups = [
        (column, sorted(str(tariff.pk) for tariff in options.values()))
        for column, options in sorted(pairs)
    ]
    identity["mapping"] = {
        "student_code": code_index,
        "amounts": [{"column": column, "schedules": ids} for column, ids in groups],
    }
    previous_multiclass = migration_fingerprint(identity)
    identity["mapping"]["amounts"] = [
        {"column": column, "schedule": ids[0]} if len(ids) == 1
        else {"column": column, "schedules": ids}
        for column, ids in groups
    ]
    fingerprints = (migration_fingerprint(identity), legacy, previous_multiclass)

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
        for col, options in pairs:
            schedule = None
            try:
                schedule = selected_schedule(enrollment, options)
                item = cell_preview(school, enrollment, schedule, row["cells"][col], cutoff)
            except ValueError as exc:
                item = {"status": "invalid", "error": str(exc)}
            cells.append({"column": col, "schedule": str(schedule.pk) if schedule else None, **item})
            if item["status"] in {"proposed", "zero", "unknown"}:
                entries.append({
                    "line": row["line"], "enrollment": enrollment, "schedule": schedule,
                    "state": item["status"], "declared": None if item["declared"] is None else Decimal(item["declared"]),
                    "net_due": Decimal(item["net_due"]), "scholarship": Decimal(item["scholarship"]),
                    "evidence_reference": "",
                })
        reports.append({"line": row["line"], "status": "resolved", "cells": cells})
    return year, cutoff, fingerprints, upload.name, table, reports, entries


@never_cache
@require_POST
@authorized
def prepare(request, school_id):
    school, error = gate(request, school_id, "school.finance.receive")
    if error is not None:
        return error
    try:
        year, cutoff, fingerprints, source_name, table, reports, entries = preview_data(
            school, request
        )
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        fingerprint = fingerprints[0]
        existing = HistoricalFinancialMigration.objects.filter(
            school=school, fingerprint__in=fingerprints,
        ).exclude(status__in=("cancelled", "reversed")).order_by("prepared_at").first()
        if existing:
            return JsonResponse({"batch": str(existing.pk), "status": existing.status,
                                 "idempotent": True, "row_count": existing.row_count})
        while (previous := HistoricalFinancialMigration.objects.filter(
            school=school, fingerprint=fingerprint,
        ).first()):
            if previous.status not in (previous.STATUS_CANCELLED, previous.STATUS_REVERSED):
                return JsonResponse({"batch": str(previous.pk), "status": previous.status,
                                     "idempotent": True, "row_count": previous.row_count})
            fingerprint = migration_fingerprint([fingerprint, str(previous.pk)])
        if not entries or any(row["status"] == "identity_review" for row in reports):
            return JsonResponse({"error": "Régularisez les identités avant préparation."}, status=422)
        if any(
            item["status"] in {"invalid", "overpayment", "existing_review", "unknown"}
            for row in reports for item in row["cells"]
        ):
            return JsonResponse({"error": "Montants inconnus, invalides, dépassés ou déjà comptabilisés : régularisez avant préparation."}, status=422)
        if not AcademicYear.objects.select_for_update().filter(pk=year.pk, school=school, active=True).exclude(status=AcademicYear.STATUS_CLOSED).exists():
            return JsonResponse({"error": "Année scolaire fermée ou inactive."}, status=409)
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
        log_event(school, request, "historical_migration_prepared", batch.pk, {"row_count": batch.row_count})
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
            School.objects.select_for_update().get(pk=school.pk)
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
            year = AcademicYear.objects.select_for_update().filter(pk=batch.year_id, school=school, active=True).exclude(status=AcademicYear.STATUS_CLOSED).first()
            if year is None or not year.start_date <= batch.cutoff <= min(year.end_date, timezone.localdate()):
                return JsonResponse({"error": "Année scolaire clôturée, inactive ou date invalide."}, status=409)

            entries = list(batch.entries.select_for_update().order_by("enrollment_id", "schedule_id"))
            if not entries:
                raise ValueError("Lot vide.")
            for entry in entries:
                if entry.school_id != school.pk or entry.state not in ("proposed", "zero") or entry.declared_amount is None:
                    raise ValueError("Entrée inconnue ou invalide : nouvelle préparation nécessaire.")
                enrollment = Enrollment.objects.select_for_update().filter(pk=entry.enrollment_id, school=school, year=year, active=True, student__school=school, student__active=True, classroom__school=school, classroom__year=year).first()
                schedule = FeeSchedule.objects.select_for_update().filter(pk=entry.schedule_id, school=school, year=year, active=True, currency="XAF").first()
                if enrollment is None or schedule is None or explicit_demo(schedule.label):
                    raise ValueError("Inscription ou tarif non admissible.")
                if schedule.classroom_id and schedule.classroom_id != enrollment.classroom_id:
                    raise ValueError("Tarif incompatible avec la classe.")
                if schedule.due_date and schedule.due_date > batch.cutoff:
                    raise ValueError("Échéance postérieure à la date de reprise.")
                if HistoricalFinancialMigrationEntry.objects.filter(
                    school=school, enrollment=enrollment, schedule=schedule, batch__status="approved",
                ).exists():
                    raise ValueError("Une reprise a déjà été approuvée pour cette inscription et ce tarif.")
                charge = FeeCharge.objects.select_for_update().filter(
                    school=school, enrollment=enrollment, schedule=schedule
                ).first()
                discount = tuition_discount(enrollment, schedule)
                if charge is not None:
                    if charge.currency != "XAF" or explicit_demo(charge.label) or (charge.due_date and charge.due_date > batch.cutoff):
                        raise ValueError("Frais existant incompatible.")
                    if cleared_total(charge) != 0 or SingPayIntent.objects.filter(charge=charge, school=school, state__in=("initiating", "pending", "unknown", "review", "refund_review")).exists():
                        raise ValueError("Paiement, ajustement ou transaction en cours : rapprochement requis.")
                    gross, covered = charge.amount, charge.scholarship_discount
                else:
                    gross, covered = schedule.amount, discount
                if (gross != schedule.amount or covered != entry.scholarship
                        or gross - covered != entry.net_due or covered != discount):
                    raise ValueError("Tarif ou bourse modifié depuis la préparation. Préparez un nouveau lot.")
                if entry.declared_amount < 0 or entry.declared_amount > gross - covered:
                    raise ValueError("Montant historique incompatible.")
                entry.evidence_reference = reason[:255]
                entry.save(update_fields=["evidence_reference"])
                if charge is None and gross == covered:
                    # Fully covered students must not receive a tuition debt.
                    continue
                if charge is None:
                    charge = FeeCharge(school=school, enrollment=enrollment, schedule=schedule,
                        label=schedule.label, amount=gross, scholarship_discount=covered,
                        currency="XAF", due_date=schedule.due_date, created_by=batch.prepared_by)
                    charge.full_clean()
                    charge.save()
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
            log_event(school, request, "historical_migration_approved", batch.pk, {"row_count": batch.row_count})
    except (ValueError, ValidationError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except IntegrityError:
        return JsonResponse({"error": "Conflit concurrent : rechargez le lot avant toute nouvelle validation."}, status=409)
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
        if batch.prepared_by_id != request.user.pk:
            return refuse()
        if batch.status in (batch.STATUS_APPROVED, batch.STATUS_REVERSED):
            return JsonResponse({"error": "Un lot approuvé ne peut pas être annulé par cette opération."}, status=409)
        if batch.status == HistoricalFinancialMigration.STATUS_CANCELLED:
            return JsonResponse({"batch": str(batch.pk), "status": "cancelled", "idempotent": True})
        batch.status = HistoricalFinancialMigration.STATUS_CANCELLED
        batch.cancelled_at = timezone.now()
        batch.cancellation_reason = reason[:1000]
        batch.save(update_fields=["status", "cancelled_at", "cancellation_reason"])
        log_event(school, request, "historical_migration_cancelled", batch.pk)
    return JsonResponse({"batch": str(batch.pk), "status": "cancelled", "idempotent": False})


@never_cache
@require_POST
@authorized
def reversal(request, school_id, batch_id, action):
    if action not in ("request", "withdraw", "confirm"):
        return JsonResponse({"error": "Opération inconnue."}, status=404)
    permission = "school.finance.receive" if action != "confirm" else "school.finance.approve"
    school, error = gate(request, school_id, permission)
    if error is not None:
        return error
    reason = request.POST.get("reason", "").strip()
    if not 5 <= len(reason) <= 255:
        return JsonResponse({"error": "Motif ou référence requis (5 à 255 caractères)."}, status=422)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        batch = HistoricalFinancialMigration.objects.select_for_update().filter(
            school=school, pk=batch_id,
        ).first()
        if batch is None:
            return JsonResponse({"error": "Lot introuvable."}, status=404)
        if action != "confirm" and batch.prepared_by_id != request.user.pk:
            return refuse()
        if action == "confirm" and batch.reversal_requested_by_id == request.user.pk:
            return refuse()
        if batch.status == batch.STATUS_REVERSED:
            return JsonResponse({"batch": str(batch.pk), "status": batch.status, "idempotent": True})
        if batch.status != batch.STATUS_APPROVED:
            return JsonResponse({"error": "Seul un lot approuvé peut être contrepassé."}, status=409)
        year = AcademicYear.objects.select_for_update().filter(
            school=school, pk=batch.year_id, active=True,
        ).exclude(status=AcademicYear.STATUS_CLOSED).first()
        if year is None:
            return JsonResponse({"error": "Année scolaire clôturée ou inactive."}, status=409)
        if action == "request":
            if batch.reversal_requested_by_id:
                return JsonResponse({"batch": str(batch.pk), "status": "reversal_pending", "idempotent": True})
            batch.reversal_requested_by = request.user
            batch.reversal_requested_at = timezone.now()
            batch.reversal_reason = reason
            batch.save(update_fields=["reversal_requested_by", "reversal_requested_at", "reversal_reason"])
            log_event(school, request, "historical_reversal_requested", batch.pk)
            status = "reversal_pending"
        elif action == "withdraw":
            if not batch.reversal_requested_by_id:
                return JsonResponse({"batch": str(batch.pk), "status": batch.status, "idempotent": True})
            log_event(school, request, "historical_reversal_withdrawn", batch.pk, {
                "request_reason": batch.reversal_reason, "withdrawal_reason": reason,
            })
            batch.reversal_requested_by = None
            batch.reversal_requested_at = None
            batch.reversal_reason = ""
            batch.save(update_fields=["reversal_requested_by", "reversal_requested_at", "reversal_reason"])
            status = batch.status
        else:
            if not batch.reversal_requested_by_id:
                return JsonResponse({"error": "Demande de contrepassation requise."}, status=409)
            batch.status = batch.STATUS_REVERSED
            batch.reversed_by = request.user
            batch.reversed_at = timezone.now()
            batch.reversal_evidence = reason
            batch.save(update_fields=["status", "reversed_by", "reversed_at", "reversal_evidence"])
            log_event(school, request, "historical_reversal_confirmed", batch.pk)
            status = batch.status
    return JsonResponse({"batch": str(batch.pk), "status": status, "idempotent": False})
