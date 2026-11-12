"""Physical admission cash at the school counter, with a private parent PDF receipt.

Only school cashiers may record a real receipt. Synthetic test cash is explicitly
non-financial, requires school opt-in, and never reaches the real cashbook.
"""
from datetime import date
from html import escape
from io import BytesIO
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from accounts.views import authorized

from .admission_models import AdmissionEvent, AdmissionApplication
from .admission_scholarship_amounts import admission_due, admission_gross
from .admission_finance import current_scholarship, GovernmentScholarship
from .demo_payment_views import demo_amount
from .finance_cash_policy import cash_closed_for_recorder
from .models import School
from .parent_admission_models import ParentAdmissionRequest
from .parent_payment_models import AdmissionCashReceipt, AdmissionCashReceiptVoid
from .services import has_permission
from .views import access, log_event, parse_body, refuse


def fail(message, status=422):
    return JsonResponse({"error": message}, status=status)


def receipt_payload(receipt):
    voided = AdmissionCashReceiptVoid.objects.filter(receipt=receipt).exists()
    return {
        "id": str(receipt.pk), "request": str(receipt.request_id or receipt.application_id),
        "amount_xaf": receipt.amount_xaf, "currency": "XAF",
        "reference": receipt.reference, "received_on": receipt.received_on.isoformat(),
        "recorded_by": str(receipt.recorded_by_id),
        "is_demo": receipt.is_demo, "voided": voided,
        "status": "annule" if voided else "simule" if receipt.is_demo else "recu",
        "received_confirmed": not (receipt.is_demo or voided),
        "notice": "SIMULATION DE CAISSE — 0 FCFA reçu, sans valeur d'encaissement."
          if receipt.is_demo else "Paiement en espèces reçu et déclaré par la caisse de l'établissement.",
        "receipt_url": (f"/api/v1/parents/applications/{receipt.request_id}/cash-receipt" if receipt.request_id else
                        f"/api/v1/schools/{receipt.school_id}/admission-cash/{receipt.application_id}/receipt"),
    }


@never_cache
@require_GET
@authorized
def cashier_queue(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not any(has_permission(request.user, school, permission) for permission in (
        "school.finance.read", "school.finance.receive", "school.admissions.read",
    )):
        return refuse()
    key = request.GET.get("application")
    app_id = None
    if key is not None:
        try:
            app_id = UUID(key)
        except (TypeError, ValueError):
            return fail("Candidature invalide.")
    links = ParentAdmissionRequest.objects.select_related(
        "application__classroom", "application__year", "child", "owner",
    ).filter(application__school=school, payment_choice="cash")
    direct = AdmissionApplication.objects.select_related(
        "classroom", "year",
    ).filter(school=school, parent_request__isnull=True)
    if app_id is not None:
        links = links.filter(application_id=app_id)
        direct = direct.filter(pk=app_id)
    rows = []
    for link in links.order_by("-created_at")[:250]:
        app = link.application
        gross, due = admission_gross(app), admission_due(app)
        cash = AdmissionCashReceipt.objects.filter(request=link).first()
        award = current_scholarship(app)
        rows.append({
            "request": str(link.pk), "application": str(app.pk),
            "parent": link.owner.get_full_name() or link.owner.username,
            "child": f"{link.child.last_name} {link.child.first_name}",
            "classroom": app.classroom.name, "year": app.year.name,
            "amount_xaf": due, "gross_amount_xaf": gross,
            "scholarship_covered_xaf": gross - due, "scholarship_active": bool(award),
            "is_demo": link.is_demo_cash, "admission_status": app.status,
            "can_pay": bool(due >= 100 and not cash and app.status not in ("enrolled", "rejected")),
            "payment_status": (receipt_payload(cash)["status"] if cash else
                               "dispense_bourse" if award and due == 0 else
                               "inscription_deja_finalisee" if app.status == "enrolled" else
                               "a_regler_sur_place"),
            "receipt_url": f"/api/v1/schools/{school.pk}/admission-cash/{link.pk}/receipt" if cash else None,
        })
    # Guichet applications must NEVER require creating a false parent account.
    # The same cashier view and school admission tariff provide the handoff.
    for app in direct.order_by("-submitted_at")[:250]:
        gross, due = admission_gross(app), admission_due(app)
        cash = AdmissionCashReceipt.objects.filter(application=app).first()
        award = current_scholarship(app)
        rows.append({
            "request": str(app.pk), "application": str(app.pk),
            "parent": app.guardian_name, "child": f"{app.last_name} {app.first_name}",
            "classroom": app.classroom.name, "year": app.year.name,
            "amount_xaf": due, "gross_amount_xaf": gross,
            "scholarship_covered_xaf": gross - due, "scholarship_active": bool(award),
            "is_demo": False, "admission_status": app.status,
            "direct_cash": True,
            "can_pay": bool(due >= 100 and not cash and app.status not in ("enrolled", "rejected")),
            "payment_status": (receipt_payload(cash)["status"] if cash else
                               "dispense_bourse" if award and due == 0 else
                               "inscription_deja_finalisee" if app.status == "enrolled" else
                               "a_regler_sur_place"),
            "receipt_url": f"/api/v1/schools/{school.pk}/admission-cash/{app.pk}/receipt" if cash else None,
        })
    return JsonResponse({
        "payments": rows,
        "can_receive": has_permission(request.user, school, "school.finance.receive"),
    })

@never_cache
@require_POST
@authorized
def confirm_cash(request, school_id, application_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.finance.receive"):
        return refuse()
    body, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(body, dict) or set(body) != {"reference", "received_on", "received_cash", "acknowledge_demo"}:
        return fail("Référence, date et confirmation explicite requises.")
    if (type(body["received_cash"]) is not bool or type(body["acknowledge_demo"]) is not bool
        or not isinstance(body["reference"], str) or not 3 <= len(body["reference"].strip()) <= 100):
        return fail("Référence ou confirmation invalide.")
    try:
        paid_on = date.fromisoformat(body["received_on"])
    except (ValueError, TypeError):
        return fail("Date du paiement invalide.")
    if paid_on > timezone.localdate():
        return fail("La caisse ne peut pas encaisser à une date future.")
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            link = ParentAdmissionRequest.objects.select_for_update().select_related(
                "application__year", "application__classroom__level",
            ).filter(pk=application_id, application__school=school, payment_choice="cash").first()
            app = (link.application if link else
                   AdmissionApplication.objects.select_for_update(of=("self",)).select_related(
                       "year", "classroom__level",
                   ).filter(pk=application_id, school=school, parent_request__isnull=True).first())
            if app is None:
                return fail("Dossier de paiement introuvable.", 404)
            previous = AdmissionCashReceipt.objects.filter(application=app).first()
            if previous:
                same = (previous.received_on == paid_on and previous.reference == body["reference"].strip()
                    and previous.is_demo == body["acknowledge_demo"] and
                    body["received_cash"] == (not previous.is_demo))
                if same:
                    return JsonResponse(receipt_payload(previous), status=200)
                return fail("Le règlement de ce dossier est déjà enregistré.", 409)
            if app.status in ("rejected", "enrolled"):
                return fail("Candidature refusée ou déjà inscrite : aucun nouveau paiement admis.", 409)
            due = admission_due(app)
            if due == 0 and current_scholarship(app):
                return fail("Bourse gouvernementale couvrant tous les frais d'inscription : rien à encaisser.", 409)
            if due < 100:
                return fail("Aucun solde encaissable : configurez les frais ou ajustez la bourse.", 409)
            if not link and app.admission_fee_snapshot_xaf is None:
                # Old, non-parent dossiers receive an immutable quote on first cash collection.
                app.admission_fee_snapshot_xaf = admission_gross(app)
                app.save(update_fields=["admission_fee_snapshot_xaf"])
            if not app.year.start_date <= paid_on <= app.year.end_date:
                return fail("Date hors de l'année scolaire.")
            is_demo = bool(link and link.is_demo_cash)
            if is_demo:
                if body["received_cash"] or not body["acknowledge_demo"]:
                    return fail("Simulation : déclarez explicitement 0 FCFA reçu.", 409)
                if demo_amount(school, app.year_id, app.classroom.level_id, link.owner) is None:
                    return fail("La simulation n'est plus autorisée par l'établissement.", 403)
            else:
                if not body["received_cash"] or body["acknowledge_demo"]:
                    return fail("L'encaissement réel exige confirmation de remise d'espèces.", 409)
                if cash_closed_for_recorder(school=school, day=paid_on,
                        currency="XAF", user=request.user):
                    return fail("Caisse du jour déjà clôturée pour cet agent.", 409)
            row = AdmissionCashReceipt(
                request=link, application=app, school=school, amount_xaf=due,
                is_demo=is_demo, reference=body["reference"].strip(),
                received_on=paid_on, recorded_by=request.user,
            )
            row.full_clean()
            row.save()
            AdmissionEvent.objects.create(
                school=school, application=app,
                previous_status=app.status,
                new_status="cash_simulated" if row.is_demo else "cash_received",
                reason="Simulation sans mouvement de fonds." if row.is_demo
                       else "Espèces déclarées reçues par le caissier.",
                actor=request.user,
            )
            log_event(school, request, "admission_cash_recorded", str(row.pk),
                {"simulation": row.is_demo, "amount_xaf": row.amount_xaf})
    except ValidationError as exc:
        return fail(" ".join(exc.messages)[:500])
    except IntegrityError:
        return fail("Ce reçu existe déjà, actualisez le dossier.", 409)
    return JsonResponse(receipt_payload(row), status=201)

@never_cache
@require_POST
@authorized
def void_cash(request, school_id, application_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not has_permission(request.user, school, "school.finance.reverse"):
        return refuse()
    body, error = parse_body(request)
    if error is not None:
        return error
    if set(body) != {"reason"} or not isinstance(body["reason"], str) or not 10 <= len(body["reason"].strip()) <= 1000:
        return fail("Motif de l'annulation obligatoire (10 caractères minimum).")
    try:
        with transaction.atomic():
            School.objects.select_for_update().get(pk=school.pk)
            from django.db.models import Q
            cash = AdmissionCashReceipt.objects.select_for_update().filter(
                Q(request_id=application_id) | Q(application_id=application_id),
                school=school,
            ).first()
            if cash is None:
                return fail("Reçu introuvable.", 404)
            app = cash.application or cash.request.application
            if app.status == "enrolled":
                return fail("Inscription déjà définitive : une correction comptable indépendante est requise.", 409)
            if cash.recorded_by_id == request.user.pk:
                return fail("Un autre responsable doit annuler le reçu.", 403)
            if AdmissionCashReceiptVoid.objects.filter(receipt=cash).exists():
                return fail("Paiement déjà annulé.", 409)
            if not cash.is_demo and cash_closed_for_recorder(
                school=school, day=cash.received_on, currency="XAF", user=cash.recorded_by,
            ):
                return fail("La caisse est clôturée, opération de correction distincte requise.", 409)
            void = AdmissionCashReceiptVoid(
                receipt=cash, school=school, reason=body["reason"].strip(), voided_by=request.user,
            )
            void.full_clean()
            void.save()
            AdmissionEvent.objects.create(
                school=school, application=app,
                previous_status=app.status, new_status="cash_cancelled",
                reason="Reçu annulé par l'administration : " + void.reason[:250],
                actor=request.user,
            )
            log_event(school, request, "admission_cash_voided", str(cash.pk))
    except ValidationError as exc:
        return fail(" ".join(exc.messages)[:500])
    return JsonResponse(receipt_payload(cash), status=201)


def render_receipt(cash):
    app = cash.application or cash.request.application
    school = cash.school
    voided = AdmissionCashReceiptVoid.objects.filter(receipt=cash).exists()
    banner = ("DOCUMENT DE SIMULATION — AUCUN ARGENT REÇU — SANS VALEUR FINANCIÈRE"
              if cash.is_demo else "YEM — REÇU DE PAIEMENT EN ESPÈCES")
    lines = [
        banner,
        f"Établissement : {school.name}",
        f"Référence du reçu : {cash.pk}",
        f"Candidature : {app.pk}",
        f"Élève : {app.first_name} {app.last_name}",
        f"Classe demandée : {app.classroom.name}",
        f"Année : {app.year.name}",
        f"Montant : {cash.amount_xaf} FCFA" + (" (SIMULÉ, NON ENCAISSÉ)" if cash.is_demo else ""),
        f"Date : {cash.received_on.isoformat()}",
        f"Référence de caisse : {cash.reference}",
        f"Statut : {'ANNULÉ' if voided else 'SIMULÉ' if cash.is_demo else 'ESPÈCES REÇUES'}",
        "Le paiement d'admission ne vaut pas acceptation définitive ni matriculation.",
    ]
    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm)
    style = getSampleStyleSheet()
    story = [Paragraph(escape(line), style["Heading2"] if n == 0 else style["Normal"])
             for n, line in enumerate(lines)]
    story.insert(1, Spacer(1, 8*mm))
    doc.build(story)
    response = HttpResponse(out.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="yem-admission-cash-{cash.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@never_cache
@require_GET
@authorized
def parent_receipt(request, application_id):
    cash = AdmissionCashReceipt.objects.select_related(
        "school", "request__application__year", "request__application__classroom",
    ).filter(request_id=application_id, request__owner=request.user).first()
    if cash is None:
        return fail("Reçu introuvable.", 404)
    return render_receipt(cash)


@never_cache
@require_GET
@authorized
def staff_receipt(request, school_id, application_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not (has_permission(request.user, school, "school.finance.read")
            or has_permission(request.user, school, "school.admissions.read")):
        return refuse()
    from django.db.models import Q
    cash = AdmissionCashReceipt.objects.select_related(
        "school", "application__year", "application__classroom",
        "request__application__year", "request__application__classroom",
    ).filter(Q(request_id=application_id) | Q(application_id=application_id), school=school).first()
    if cash is None:
        return fail("Reçu introuvable.", 404)
    return render_receipt(cash)
