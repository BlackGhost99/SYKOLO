"""Parent-only PDFs: every lookup requires a verified guardian/student relationship.

These are not public URLs and no document lookup uses a self-asserted school ID.
"""
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from accounts.views import authorized

from .finance_document_pdf import render_school_financial_pdf, school_guardian
from .finance_models import FeeCharge, FeePayment, FeePaymentBatch, FeePaymentVoid
from .finance_views import cleared_total
from .parent_views import permitted_child


@never_cache
@require_GET
@authorized
def list_documents(request, student_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    root = f"/api/v1/parents/children/{student.pk}/finance/documents"
    charges = FeeCharge.objects.filter(
        school_id=student.school_id, enrollment__student_id=student.pk,
    ).order_by("-created_at")[:200]
    payments = FeePayment.objects.filter(
        school_id=student.school_id, charge__enrollment__student_id=student.pk,
        batch__isnull=True,
    ).order_by("-created_at")[:200]
    batches = FeePaymentBatch.objects.filter(
        school_id=student.school_id, enrollment__student_id=student.pk,
    ).order_by("-created_at")[:200]
    return JsonResponse({
        "student": str(student.pk),
        "invoices": [{"id": str(x.pk), "label": x.label, "currency": x.currency,
                      "url": f"{root}/invoice/{x.pk}/pdf"} for x in charges],
        "receipts": [{"id": str(x.pk), "amount": str(x.amount), "currency": x.currency,
                      "voided": FeePaymentVoid.objects.filter(payment=x).exists(),
                      "url": f"{root}/receipt/{x.pk}/pdf"} for x in payments],
        "grouped_receipts": [{"id": str(x.pk), "amount": str(x.total), "currency": x.currency,
                             "url": f"{root}/batch/{x.pk}/pdf"} for x in batches],
    })


@never_cache
@require_GET
@authorized
def document_pdf(request, student_id, kind, document_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    school = student.school
    common = {
        "school": school,
        "student_name": f"{student.first_name} {student.last_name}".strip(),
        "matricule": student.student_code,
        "payer": school_guardian(student),
    }
    if kind == "invoice":
        charge = FeeCharge.objects.select_related(
            "enrollment__year", "enrollment__classroom"
        ).filter(
            school=school, pk=document_id, enrollment__student=student,
        ).first()
        if charge is None:
            return JsonResponse({"error": "Document introuvable."}, status=404)
        paid = cleared_total(charge)
        net = charge.amount - charge.scholarship_discount
        return render_school_financial_pdf(
            **common, title="Facture scolaire",
            reference="FAC-" + charge.created_at.strftime("%Y") + "-" + charge.pk.hex.upper(),
            issued_on=charge.created_at,
            year=charge.enrollment.year.name, classroom=charge.enrollment.classroom.name,
            rows=[(charge.label, charge.amount)], currency=charge.currency,
            total=net, paid=paid, balance=net-paid, discount=charge.scholarship_discount,
            due_on=charge.due_date, filename=f"yem-facture-{charge.pk}.pdf",
        )
    if kind == "receipt":
        payment = FeePayment.objects.select_related(
            "charge__enrollment__year", "charge__enrollment__classroom", "recorded_by",
        ).filter(
            school=school, pk=document_id, charge__enrollment__student=student,
        ).first()
        if payment is None:
            return JsonResponse({"error": "Document introuvable."}, status=404)
        charge = payment.charge
        cancelled = FeePaymentVoid.objects.filter(payment=payment).exists()
        return render_school_financial_pdf(
            **common, title="Reçu de paiement", receipt=True,
            reference="REC-" + payment.paid_on.strftime("%Y") + "-" + payment.pk.hex.upper(),
            issued_on=payment.created_at, year=charge.enrollment.year.name,
            classroom=charge.enrollment.classroom.name,
            rows=[(charge.label, payment.amount)], currency=payment.currency,
            total=payment.amount,
            balance=charge.amount - charge.scholarship_discount - cleared_total(charge),
            method=payment.method, external_reference=payment.reference,
            cashier=payment.recorded_by.get_username() if payment.recorded_by else "",
            cancelled=cancelled, filename=f"yem-recu-{payment.pk}.pdf",
        )
    if kind == "batch":
        batch = FeePaymentBatch.objects.select_related(
            "enrollment__year", "enrollment__classroom", "recorded_by",
        ).filter(
            school=school, pk=document_id, enrollment__student=student,
        ).first()
        if batch is None:
            return JsonResponse({"error": "Document introuvable."}, status=404)
        payments = list(batch.lines.select_related("charge", "void").order_by("charge__label", "pk"))
        cancelled = any(hasattr(p, "void") for p in payments)
        remaining = sum(
            (p.charge.amount - p.charge.scholarship_discount - cleared_total(p.charge)
             for p in payments), Decimal("0.00")
        )
        return render_school_financial_pdf(
            **common, title="Reçu groupé de paiement", receipt=True,
            reference="REG-" + batch.paid_on.strftime("%Y") + "-" + batch.pk.hex.upper(),
            issued_on=batch.created_at, year=batch.enrollment.year.name,
            classroom=batch.enrollment.classroom.name,
            rows=[(p.charge.label + (" — ANNULÉ" if hasattr(p, "void") else ""), p.amount)
                  for p in payments],
            currency=batch.currency, total=batch.total, balance=remaining,
            method=batch.method, external_reference=batch.reference,
            cashier=batch.recorded_by.get_username() if batch.recorded_by else "",
            cancelled=cancelled, filename=f"yem-recu-groupe-{batch.pk}.pdf",
        )
    return JsonResponse({"error": "Type de document inconnu."}, status=404)
