"""Multi-fee manual receipts: one DB transaction, one idempotency key, one PDF.

This endpoint *records money already received*; it never starts a bank/mobile transfer.
"""
import hashlib
import json
from decimal import Decimal
from html import escape
from io import BytesIO
from uuid import uuid5

from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from accounts.views import authorized
from .finance_models import FeeCharge, FeePayment, FeePaymentBatch
from .finance_views import (
    CODE_PATTERN, MAX_MONEY, gate, iso_day, model_error, money,
    payment_data, cleared_total, uid,
)
from .models import School
from .finance_cash_policy import cash_closed_for_recorder
from .views import log_event, parse_body


def batch_data(batch):
    payments = list(batch.lines.select_related("charge").order_by("charge_id"))
    return {
        "id": str(batch.pk),
        "enrollment": str(batch.enrollment_id),
        "total": str(batch.total),
        "currency": batch.currency,
        "method": batch.method,
        "reference": batch.reference,
        "paid_on": batch.paid_on.isoformat(),
        "recorded_at": batch.created_at.isoformat(),
        "payments": [payment_data(line) for line in payments],
        "receipt_url": f"/api/v1/schools/{batch.school_id}/finance/batches/{batch.pk}/receipt",
    }


@require_POST
@authorized
def create_batch(request, school_id):
    school, error = gate(request, school_id, "school.finance.receive")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"enrollment", "lines", "method", "reference", "paid_on", "idempotency_key"}:
        return JsonResponse({"error": "Champs de paiement groupé invalides."}, status=422)
    enrollment_id, idem = uid(data["enrollment"]), uid(data["idempotency_key"])
    method, reference = data["method"], data["reference"]
    if method == "singpay":
        return JsonResponse({"error": "SingPay est réservé aux confirmations serveur du prestataire."}, status=422)
    if enrollment_id is None or idem is None or not isinstance(method, str) or not CODE_PATTERN.fullmatch(method):
        return JsonResponse({"error": "Inscription, méthode ou clé d'opération invalide."}, status=422)
    if not isinstance(reference, str) or len(reference) > 100:
        return JsonResponse({"error": "Référence de paiement invalide."}, status=422)
    if not isinstance(data["lines"], list) or not 1 <= len(data["lines"]) <= 30:
        return JsonResponse({"error": "Entre 1 et 30 frais sont autorisés par opération."}, status=422)

    try:
        paid_on = iso_day(data["paid_on"])
        if paid_on > timezone.localdate():
            raise ValueError("Un encaissement futur ne peut pas être déclaré comme reçu.")
        entries = {}
        total = Decimal("0.00")
        for line in data["lines"]:
            if not isinstance(line, dict) or set(line) != {"charge", "amount"}:
                raise ValueError("Ligne de paiement invalide.")
            charge_id = uid(line["charge"])
            if charge_id is None or charge_id in entries:
                raise ValueError("Frais invalide ou répété.")
            amount = money(line["amount"])
            entries[charge_id] = amount
            total += amount
        if total > MAX_MONEY:
            raise ValueError("Montant total trop élevé.")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)

    normalized = {
        "enrollment": str(enrollment_id),
        "lines": [[str(k), str(entries[k])] for k in sorted(entries)],
        "method": method,
        "reference": reference.strip(),
        "paid_on": paid_on.isoformat(),
    }
    fingerprint = hashlib.sha256(json.dumps(
        normalized, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()

    try:
        with transaction.atomic():
            # Serializes groups with the same key, including groups on disjoint charges.
            School.objects.select_for_update().get(pk=school.pk)
            previous = FeePaymentBatch.objects.filter(school=school, idempotency_key=idem).first()
            if previous:
                if previous.request_hash != fingerprint:
                    return JsonResponse({"error": "Clé réutilisée avec une autre opération."}, status=409)
                return JsonResponse(batch_data(previous))

            charges = list(FeeCharge.objects.select_for_update().filter(
                school=school, enrollment_id=enrollment_id, pk__in=entries,
            ).order_by("pk"))
            if len(charges) != len(entries):
                return JsonResponse({"error": "Frais ou inscription introuvable dans cette école."}, status=404)
            currency = charges[0].currency
            if any(charge.currency != currency for charge in charges):
                return JsonResponse({"error": "Plusieurs devises : effectuez des paiements séparés."}, status=422)
            if method == "especes" and cash_closed_for_recorder(
                school=school, day=paid_on, currency=currency, user=request.user,
            ):
                return JsonResponse({"error": "Caisse du jour déjà déclarée par ce caissier."}, status=409)
            for charge in charges:
                if cleared_total(charge) + entries[charge.pk] > charge.amount - charge.scholarship_discount:
                    return JsonResponse({"error": "Solde insuffisant pour " + charge.label}, status=422)

            batch = FeePaymentBatch(
                school=school, enrollment_id=enrollment_id, idempotency_key=idem,
                request_hash=fingerprint, total=total, currency=currency,
                method=method, reference=reference.strip(), paid_on=paid_on,
                recorded_by=request.user,
            )
            batch.full_clean()
            batch.save()
            for charge in charges:
                line = FeePayment(
                    school=school, batch=batch, charge=charge,
                    idempotency_key=uuid5(idem, str(charge.pk)),
                    amount=entries[charge.pk], currency=currency,
                    method=method, reference=reference.strip(),
                    paid_on=paid_on, recorded_by=request.user,
                )
                line.full_clean()
                line.save()
            log_event(school, request, "fee_batch_recorded", batch.pk)
    except ValidationError as exc:
        return model_error(exc)
    except IntegrityError:
        return JsonResponse({"error": "Opération concurrente : vérifiez les encaissements avant de réessayer."}, status=409)
    return JsonResponse(batch_data(batch), status=201)


@require_GET
@authorized
def batch_detail(request, school_id, batch_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    batch = FeePaymentBatch.objects.filter(school=school, pk=batch_id).first()
    if batch is None:
        return JsonResponse({"error": "Encaissement groupé introuvable."}, status=404)
    return JsonResponse(batch_data(batch))


@require_GET
@authorized
def batch_receipt(request, school_id, batch_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    batch = FeePaymentBatch.objects.select_related("enrollment__student").filter(
        school=school, pk=batch_id,
    ).first()
    if batch is None:
        return JsonResponse({"error": "Reçu groupé introuvable."}, status=404)

    lines = list(batch.lines.select_related("charge").order_by("charge__label", "pk"))
    student = batch.enrollment.student
    active_sum = sum((p.amount for p in lines if not hasattr(p, "void")), Decimal("0.00"))
    cancelled = any(hasattr(p, "void") for p in lines)
    text = [
        "YEM — REÇU GROUPÉ D'ENCAISSEMENT ENREGISTRÉ",
        "Référence interne : " + str(batch.pk),
        "Établissement : " + school.name,
        "Élève : " + student.first_name + " " + student.last_name,
        "Date déclarée : " + batch.paid_on.isoformat(),
        "Méthode déclarée : " + batch.method,
        "Référence externe déclarée : " + (batch.reference or "Non renseignée"),
        "— Détail des frais —",
    ]
    for p in lines:
        text.append(
            p.charge.label + " : " + str(p.amount) + " " + p.currency
            + (" (ANNULÉ)" if hasattr(p, "void") else "")
        )
    text.extend([
        "Montant initial déclaré : " + str(batch.total) + " " + batch.currency,
        "Montant restant après annulations : " + str(active_sum) + " " + batch.currency,
        "Statut : PARTIELLEMENT OU TOTALEMENT ANNULÉ" if cancelled else "Statut : Enregistré par l'établissement.",
        "Reçu interne — ne constitue pas une confirmation bancaire ou Mobile Money automatique.",
    ])

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(t), styles["Normal"]) for t in text]
    story.insert(1, Spacer(1, 8*mm))
    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="yem-recu-groupe-{batch.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response
