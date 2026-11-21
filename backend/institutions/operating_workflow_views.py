"""B3b: submit/reject expense requests; no direct money movements or fee changes."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from accounts.views import authorized

from .operating_models import (
    OperatingExpense, OperatingExpenseDecision, ACTIVE_ACTIVITY_POLES,
)
from .operating_views import body, expense_data, fail, gate, open_year, result, txt, validation
from .views import log_event


def decision_data(row):
    return {
        "id": str(row.pk), "action": row.action, "actor": str(row.actor_id),
        "revision": row.revision, "reason": row.reason,
        "occurred_at": row.occurred_at.isoformat(),
    }


def record_decision(school, request, expense, action, reason=""):
    evidence = OperatingExpenseDecision(
        school=school, expense=expense, actor=request.user,
        action=action, revision=expense.revision, reason=reason,
    )
    evidence.full_clean()
    evidence.save()
    log_event(school, request, "operating_expense_" + action, expense.pk)
    return evidence


def validate_submission(row):
    if row.activity_pole not in ACTIVE_ACTIVITY_POLES:
        return "Classez cette demande par activité avant soumission."
    if not row.category_ref_id or not row.category_ref.active:
        return "Une catégorie active de dépense est obligatoire."
    if row.subcategory_ref_id and not row.subcategory_ref.active:
        return "La sous-catégorie est archivée."
    if not row.budget.approved_at or not open_year(row.year):
        return "Budget non approuvé ou exercice clôturé."
    if row.beneficiary_type == "supplier":
        if not row.supplier_id or not row.supplier.active:
            return "Fournisseur actif requis."
    elif not row.beneficiary_name.strip() or row.supplier_id:
        return "Bénéficiaire non commercial invalide."
    if not row.invoice_reference.strip():
        return "Une référence justificative est obligatoire."
    return None


@never_cache
@require_POST
@authorized
def submit_expense(request, school_id, expense_id):
    school, err = gate(request, school_id, "school.operating.manage")
    if err is not None:
        return err
    payload, err = body(request, {"revision"}, {"revision"})
    if err is not None:
        return err
    if type(payload["revision"]) is not int:
        return fail("Révision obligatoire.")
    with transaction.atomic():
        row = OperatingExpense.objects.select_for_update(of=("self",)).select_related(
            "year", "budget", "supplier", "category_ref", "subcategory_ref",
        ).filter(school=school, pk=expense_id).first()
        if not row:
            return fail("Demande introuvable.", 404)
        if row.revision != payload["revision"] or row.workflow_state != "draft" or row.approved_at:
            return fail("Demande obsolète ou non préparée pour une nouvelle soumission.", 409)
        issue = validate_submission(row)
        if issue:
            return fail(issue, 409)
        row.submitted_by = request.user
        row.submitted_at = timezone.now()
        row.workflow_state = "submitted"
        row.revision += 1
        try:
            row.full_clean()
        except ValidationError as exc:
            return validation(exc)
        row.save(update_fields=["submitted_by", "submitted_at", "workflow_state", "revision"])
        record_decision(school, request, row, "submitted")
    return result(expense_data(row))


@never_cache
@require_POST
@authorized
def reject_expense(request, school_id, expense_id):
    school, err = gate(request, school_id, "school.operating.approve")
    if err is not None:
        return err
    payload, err = body(request, {"revision", "reason"}, {"revision", "reason"})
    if err is not None:
        return err
    try:
        if type(payload["revision"]) is not int:
            raise ValueError("Révision obligatoire.")
        reason = txt(payload["reason"], 240, "Motif du refus")
        if len(reason) < 10:
            raise ValueError("Un motif de refus explicite (10 caractères minimum) est requis.")
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        row = OperatingExpense.objects.select_for_update(of=("self",)).select_related(
            "year", "budget", "supplier",
        ).filter(school=school, pk=expense_id).first()
        if not row:
            return fail("Demande introuvable.", 404)
        if (row.workflow_state != "submitted" or row.approved_at or
                row.revision != payload["revision"] or not open_year(row.year)):
            return fail("Demande non soumise, obsolète ou exercice clôturé.", 409)
        if request.user.pk in (row.prepared_by_id, row.submitted_by_id):
            return fail("Le contrôle exige un autre agent que le préparateur et le soumissionnaire.", 403)
        row.workflow_state = "rejected"
        row.revision += 1
        row.full_clean()
        row.save(update_fields=["workflow_state", "revision"])
        record_decision(school, request, row, "rejected", reason)
    return result(expense_data(row))
