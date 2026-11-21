"""A9a: read-only, branded PDF documents for recorded extracurricular sales.

Never create payments, alter the ledger or claim bank certification.
"""
from decimal import Decimal

from accounts.views import authorized
from django.db.models import Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from institutions.finance_document_pdf import previewable_pdf, render_school_financial_pdf
from institutions.finance_views import gate

from .models import ExtraPayment, ExtraSale


@require_GET
@authorized
@previewable_pdf
def invoice(request, school_id, sale_id):
    school, denied = gate(request, school_id, "school.finance.manage")
    if denied is not None:
        return denied
    sale = ExtraSale.objects.select_related("year").filter(
        school=school, pk=sale_id
    ).first()
    if sale is None:
        return JsonResponse({"error": "Vente extrascolaire introuvable."}, status=404)
    paid = sale.manual_receipts.aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
    rows = [
        (f"{line.label} ({line.quantity} × {line.unit_price:.2f})", line.line_total)
        for line in sale.lines.order_by("position")
    ]
    return render_school_financial_pdf(
        school=school, title="Facture extrascolaire", receipt=False,
        reference=sale.reference, issued_on=sale.created_at,
        student_name="", payer=sale.buyer_label, rows=rows,
        year=sale.year.name if sale.year_id else "",
        currency=sale.currency, total=sale.total, paid=paid,
        balance=sale.total - paid,
        note=("Document de vente extrascolaire distinct de la scolarité. "
              "Les sommes réglées sont des déclarations de caisse à rapprocher ; "
              "cette facture n'est pas une preuve de paiement."),
        filename=f"yem-facture-extra-{sale.pk}.pdf",
    )


@require_GET
@authorized
@previewable_pdf
def manual_receipt(request, school_id, sale_id, payment_id):
    school, denied = gate(request, school_id, "school.finance.receive")
    if denied is not None:
        return denied
    payment = ExtraPayment.objects.select_related("sale", "received_by").filter(
        school=school, sale_id=sale_id, pk=payment_id,
    ).first()
    if payment is None:
        return JsonResponse({"error": "Versement extrascolaire introuvable."}, status=404)
    sale = payment.sale
    paid = sale.manual_receipts.aggregate(value=Sum("amount"))["value"] or Decimal("0.00")
    return render_school_financial_pdf(
        school=school, title="Justificatif de versement extrascolaire déclaré",
        receipt=True, reference=f"EXR-{payment.pk.hex.upper()}",
        issued_on=payment.created_at, student_name="",
        payer=sale.buyer_label,
        rows=[(f"Versement déclaré pour {sale.reference}", payment.amount)],
        currency=payment.currency, total=payment.amount,
        balance=max(Decimal("0.00"), sale.total - paid),
        method=payment.method, external_reference=payment.reference,
        cashier=payment.received_by.get_username(),
        review_required=True,
        note=("Enregistrement interne de l'établissement, non certifié par une "
              "banque ni par SingPay. Aucun rapprochement indépendant attesté. "
              "Ce versement est strictement extrascolaire."),
        filename=f"yem-versement-extra-{payment.pk}.pdf",
    )
