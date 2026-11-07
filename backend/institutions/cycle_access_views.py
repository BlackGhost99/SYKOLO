"""Gestion explicite et auditée de la portée par cycle des comptes existants."""
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from accounts.views import authorized

from .academic_models import AcademicCycle
from .cycle_scope import validate_cycle_scope
from .models import SchoolMember, School
from .services import owns_organization
from .views import access, log_event, parse_body, refuse


@require_http_methods(["GET", "PATCH"])
@authorized
def member_cycle_access(request, school_id, member_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    if not owns_organization(request.user, school.organization):
        return refuse()
    target = SchoolMember.objects.select_related("user").filter(
        school=school, pk=member_id, active=True, user__is_active=True
    ).first()
    if target is None:
        return JsonResponse({"error": "Collaborateur introuvable dans cette école."}, status=404)
    if owns_organization(target.user, school.organization):
        return JsonResponse({
            "error": "Le compte propriétaire conserve une autorité distincte ; cette restriction ne s'y applique pas."
        }, status=422)
    if request.method == "GET":
        cycles = AcademicCycle.objects.filter(school=school, active=True).order_by("order", "name")
        return JsonResponse({
            "member_id": str(target.pk), "username": target.user.username,
            "access_cycle_ids": target.access_cycle_ids,
            "cycles": [{"id": str(c.pk), "code": c.code, "name": c.name} for c in cycles],
            "note": "null = accès global, liste d'UUID = accès limité aux cycles sélectionnés.",
        })
    data, error = parse_body(request)
    if error is not None:
        return error
    if set(data) != {"access_cycle_ids", "reason"}:
        return JsonResponse({"error": "Cycle et motif obligatoires."}, status=422)
    reason = data.get("reason")
    if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 240:
        return JsonResponse({"error": "Motif de 8 à 240 caractères requis."}, status=422)
    try:
        allowed = validate_cycle_scope(school, data["access_cycle_ids"])
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    with transaction.atomic():
        School.objects.select_for_update().get(pk=school.pk)
        target = SchoolMember.objects.select_for_update().get(pk=target.pk, school=school)
        if not target.active or owns_organization(target.user, school.organization):
            return refuse()
        allowed = validate_cycle_scope(school, data["access_cycle_ids"])
        before = target.access_cycle_ids
        target.access_cycle_ids = allowed
        target.save(update_fields=["access_cycle_ids"])
        log_event(school, request, "member_cycle_scope_changed", str(target.pk), {
            "before": before, "after": allowed, "reason": reason.strip(),
        })
    return JsonResponse({"member_id": str(target.pk), "access_cycle_ids": allowed})
