"""Read-only drilldown from fee category to payment and verified-document route.

Never mix admission-cash receipts, school fees, simulations or currencies.
Only finance readers have access to the immutable payment references.
"""
from uuid import UUID
from decimal import Decimal
from datetime import date
from io import StringIO
import csv
import re

from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from accounts.views import authorized

from .academic_models import AcademicYear
from .entry_category_policy import fee_category_overrides, resolved_fee_category
from .entry_income import CATEGORIES
from .finance_evidence import classify_payment
from .finance_models import FeePayment
from .finance_views import gate


def _failure(error, status=422):
    return JsonResponse({"error":error},status=status,headers={"Cache-Control":"no-store"})


@require_GET
@authorized
def transactions(request, school_id):
    """An audited income ledger slice, not a bank-certified turnover report."""
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    try:
        year_id = UUID(request.GET.get("year", ""))
    except (ValueError, TypeError, AttributeError):
        return _failure("Année scolaire valide obligatoire.")
    year = AcademicYear.objects.filter(school=school, pk=year_id).first()
    if year is None:
        return _failure("Année scolaire étrangère ou introuvable.")
    category = request.GET.get("category", "")
    if category not in ("", *(key for key, _ in CATEGORIES)):
        return _failure("Catégorie invalide.")
    fee_code = request.GET.get("fee_code", "").strip()
    if len(fee_code) > 48:
        return _failure("Code tarif invalide.")
    currency = request.GET.get("currency", "").strip().upper()
    if currency and (len(currency) != 3 or not currency.isalpha() or not currency.isascii()):
        return _failure("Devise invalide.")
    try:
        page = int(request.GET.get("page", "1"))
    except (ValueError, TypeError):
        return _failure("Pagination invalide.")
    if page < 1 or page > 100000:
        return _failure("Pagination hors limite.")
    csv_export = request.GET.get("format", "") == "csv"
    if request.GET.get("format", "") not in ("", "csv"):
        return _failure("Format d'export non pris en charge.")
    raw_start, raw_end = request.GET.get("from", ""), request.GET.get("to", "")
    dates = []
    for raw in (raw_start, raw_end):
        if raw and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return _failure("Dates au format AAAA-MM-JJ obligatoires.")
        try:
            dates.append(date.fromisoformat(raw) if raw else None)
        except ValueError:
            return _failure("Date de filtre invalide.")
    start, end = dates
    if start and end and start > end:
        return _failure("La date de début doit précéder la date de fin.")
    if csv_export and page != 1:
        return _failure("La pagination n'est pas disponible pour l'export CSV.")
    page_size = 25
    offset = (page - 1) * page_size
    overrides = fee_category_overrides(school)
    payments = FeePayment.objects.filter(
        school=school, charge__school=school,
        charge__enrollment__school=school, charge__enrollment__year=year,
        charge__schedule__school=school, charge__schedule__year=year,
        void__isnull=True,
    )
    if currency:
        payments = payments.filter(currency=currency)
    if fee_code:
        payments = payments.filter(charge__schedule__code=fee_code)
    if start:
        payments = payments.filter(paid_on__gte=start)
    if end:
        payments = payments.filter(paid_on__lte=end)
    payments = payments.select_related("charge__schedule").order_by("-paid_on", "-pk")
    total = 0
    result = []
    for row in payments.iterator(chunk_size=500):
        code = row.charge.schedule.code
        item_category = resolved_fee_category(row.charge.schedule_id, code,
            row.charge.label, row.method, overrides=overrides)
        if category and category != item_category:
            continue
        if (csv_export and total < 2000) or (not csv_export and offset <= total < offset + page_size):
            result.append({
                "id": str(row.pk), "date": row.paid_on.isoformat(),
                "amount": str(row.amount.quantize(Decimal("0.01"))),
                "currency": row.currency, "method": row.method,
                "category": item_category, "fee_code": code,
                "evidence": classify_payment(row.method, row.charge.label),
                "future_dated": row.paid_on > timezone.localdate(),
                "receipt_url": f"/api/v1/schools/{school.pk}/finance/payments/{row.pk}/receipt",
                "batch_id": str(row.batch_id) if row.batch_id else None,
            })
        total += 1
        if csv_export and total > 2000:
            return _failure("Export limité à 2 000 règlements ; affinez les dates ou le tarif.")

    if csv_export:
        output = StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "Date", "Catégorie", "Code tarif", "Montant déclaré",
            "Devise", "Mode déclaré", "Indice de preuve", "Identifiant règlement",
            "Date future", "Reçu interne",
        ])
        def safe_cell(text):
            value = str(text or "").replace("\r", " ").replace("\n", " ")
            return "'" + value if value.startswith(("=", "+", "-", "@", "\t")) else value
        for row in result:
            writer.writerow([
                row["date"], safe_cell(row["category"]), safe_cell(row["fee_code"]),
                row["amount"], row["currency"], safe_cell(row["method"]),
                row["evidence"], row["id"],
                "oui" if row["future_dated"] else "non", safe_cell(row["receipt_url"]),
            ])
        response = HttpResponse("\ufeff" + output.getvalue(),
                                content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = "attachment; filename=entrees-declarees.csv"
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    return JsonResponse({
        "year": str(year.pk), "source": "fee_payment", "read_only": True,
        "revenue_certified": False,
        "note": ("Transactions scolaires manuelles, hors annulations. Les inscriptions encaissées "
                 "à la caisse relèvent d'un registre distinct. Les démonstrations ne sont pas des recettes réelles."),
        "filters": {"category": category, "currency": currency, "fee_code": fee_code,
                    "from": raw_start, "to": raw_end},
        "rows": result, "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1)//page_size,
    },headers={"Cache-Control":"no-store"})
