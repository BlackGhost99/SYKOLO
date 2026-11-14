"""Read-only payment notices and traceable cancellation documents.

Never invent an invoice balance, acknowledge a refund, or merge currencies.
"""
import re
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from accounts.views import authorized

from .finance_document_pdf import render_school_financial_pdf, school_guardian
from .finance_models import FeeCharge, FeePaymentVoid
from .finance_views import gate, cleared_total
from .parent_views import permitted_child
from .student_models import Enrollment


ZERO = Decimal("0.00")


def notice_for_enrollment(school, enrollment, currency):
    if not re.fullmatch(r"[A-Z]{3}", currency or ""):
        return JsonResponse({"error": "Devise du document requise."}, status=422)
    charges = list(FeeCharge.objects.filter(
        school=school, enrollment=enrollment, currency=currency,
    ).order_by("due_date", "created_at", "pk"))
    if not charges:
        return JsonResponse({"error": "Aucun frais enregistré dans cette devise."}, status=404)
    rows, amount, paid, due_dates = [], ZERO, ZERO, []
    for charge in charges:
        net = charge.amount - charge.scholarship_discount
        paid_charge = cleared_total(charge)
        remaining = net - paid_charge
        amount += net
        paid += paid_charge
        if charge.due_date and remaining > ZERO:
            due_dates.append(charge.due_date)
        label = charge.label + (
            " — échéance " + charge.due_date.strftime("%d/%m/%Y") if charge.due_date else ""
        )
        rows.append((label, net))
    student = enrollment.student
    today = timezone.localdate()
    return render_school_financial_pdf(
        school=school, title="Avis de paiement", receipt=False,
        reference="AVP-" + today.strftime("%Y%m%d") + "-" + enrollment.pk.hex.upper() + "-" + currency,
        issued_on=today,
        student_name=f"{student.first_name} {student.last_name}".strip(),
        matricule=student.student_code,
        classroom=enrollment.classroom.name,
        year=enrollment.year.name, payer=school_guardian(student),
        rows=rows, currency=currency, total=amount, paid=paid,
        balance=amount-paid, due_on=min(due_dates) if due_dates else None,
        note="Situation calculée au " + today.strftime("%d/%m/%Y") +
        " à partir du registre de l'établissement. Ce document n'atteste pas un paiement.",
        filename=f"yem-avis-{enrollment.pk}-{currency}.pdf",
    )


@never_cache
@require_GET
@authorized
def staff_notice(request, school_id, enrollment_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    enrollment = Enrollment.objects.select_related(
        "student", "year", "classroom",
    ).filter(school=school, pk=enrollment_id).first()
    if enrollment is None:
        return JsonResponse({"error": "Inscription introuvable."}, status=404)
    return notice_for_enrollment(school, enrollment, request.GET.get("currency", ""))


@never_cache
@require_GET
@authorized
def parent_notice(request, student_id, enrollment_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    enrollment = Enrollment.objects.select_related(
        "student", "year", "classroom",
    ).filter(school_id=student.school_id, student=student, pk=enrollment_id).first()
    if enrollment is None:
        return JsonResponse({"error": "Inscription introuvable."}, status=404)
    return notice_for_enrollment(student.school, enrollment, request.GET.get("currency", ""))


def void_document(void):
    payment = void.payment
    charge = payment.charge
    enrollment = charge.enrollment
    student = enrollment.student
    return render_school_financial_pdf(
        school=void.school, title="Avis d'annulation de paiement",
        reference="ANN-" + void.created_at.strftime("%Y") + "-" + void.pk.hex.upper(),
        issued_on=void.created_at,
        student_name=f"{student.first_name} {student.last_name}".strip(),
        matricule=student.student_code, classroom=enrollment.classroom.name,
        year=enrollment.year.name, payer=school_guardian(student),
        rows=[("Annulation du reçu " + str(payment.pk), payment.amount)],
        currency=payment.currency, total=payment.amount,
        correction=True, cancelled=True,
        note="Motif : " + void.reason +
        " • Approuvé par : " + (void.approved_by.get_username() if void.approved_by else "Compte désactivé") +
        ". Ce document constate une contre-écriture ; il ne prouve aucun remboursement bancaire.",
        filename=f"yem-annulation-{void.pk}.pdf",
    )


@never_cache
@require_GET
@authorized
def staff_void_document(request, school_id, payment_id):
    school, error = gate(request, school_id, "school.finance.read")
    if error is not None:
        return error
    void = FeePaymentVoid.objects.select_related(
        "payment__charge__enrollment__student",
        "payment__charge__enrollment__year",
        "payment__charge__enrollment__classroom", "approved_by",
    ).filter(school=school, payment_id=payment_id).first()
    if void is None:
        return JsonResponse({"error": "Annulation introuvable."}, status=404)
    return void_document(void)


@never_cache
@require_GET
@authorized
def parent_void_document(request, student_id, payment_id):
    student, error = permitted_child(request.user, student_id)
    if error is not None:
        return error
    void = FeePaymentVoid.objects.select_related(
        "payment__charge__enrollment__student",
        "payment__charge__enrollment__year",
        "payment__charge__enrollment__classroom", "approved_by",
    ).filter(
        school_id=student.school_id, payment_id=payment_id,
        payment__charge__enrollment__student=student,
    ).first()
    if void is None:
        return JsonResponse({"error": "Annulation introuvable."}, status=404)
    return void_document(void)
