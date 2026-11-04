"""Configurable school admission routes and manual evidence verification."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from accounts.views import authorized

from .academic_models import AcademicYear, AcademicLevel
from .admission_models import AdmissionApplication, AdmissionDocument, AdmissionEvent, AdmissionPolicy
from .admission_policy import (DOCUMENT_CODE, ROUTES, effective_policy, policy_key,
                               policy_view, validate_policy)
from .admission_views import gate, fail, name, positive_revision, model_error, uid, render
from .views import log_event, parse_body


def documents_response(application):
    return {
        "revision": application.revision,
        "required_documents": application.required_documents,
        "documents": [{
            "id": str(doc.pk), "code": doc.code, "reference": doc.reference,
            "status": doc.status, "review_reason": doc.review_reason,
            "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
            "created_at": doc.created_at.isoformat(),
        } for doc in application.documents.order_by("created_at", "pk")],
    }


def locate_scope(school, body):
    year_id = uid(body.get("year"))
    level_id = uid(body.get("level")) if body.get("level") else None
    if not year_id or (body.get("level") and not level_id):
        raise ValueError("Année scolaire ou niveau invalide.")
    year = AcademicYear.objects.filter(school=school, pk=year_id).first()
    if not year:
        raise ValueError("Année scolaire introuvable dans cet établissement.")
    level = None
    if level_id:
        level = AcademicLevel.objects.filter(school=school, pk=level_id).first()
        if not level:
            raise ValueError("Niveau étranger à l'établissement.")
    return year, level


@require_http_methods(["GET", "POST"])
@authorized
def policy(request, school_id):
    school, error = gate(
        request, school_id,
        "school.admissions.read" if request.method == "GET" else "school.admissions.decide"
    )
    if error is not None:
        return error
    if request.method == "GET":
        args = {"year": request.GET.get("year"), "level": request.GET.get("level")}
        try:
            year, level = locate_scope(school, args)
        except ValueError as exc:
            return fail(str(exc))
        selected = effective_policy(school, year, level)
        scoped = AdmissionPolicy.objects.filter(school=school,
            scope_key=policy_key(year.pk, level.pk if level else None)).first()
        return JsonResponse({**policy_view(school, year, level, selected),
                             "scope_revision": scoped.revision if scoped else 0})
    data, error = parse_body(request)
    if error is not None:
        return error
    if (not isinstance(data, dict) or set(data) != {
        "year", "level", "revision", "enabled_routes", "required_documents"
    }):
        return fail("Configuration incomplète ou champs inconnus.")
    try:
        year, level = locate_scope(school, data)
        revision = data["revision"]
        if type(revision) is not int or revision < 0:
            raise ValueError("Révision de configuration invalide.")
        routes, docs = validate_policy(data)
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        from .models import School
        School.objects.select_for_update().get(pk=school.pk)
        key = policy_key(year.pk, level.pk if level else None)
        row = AdmissionPolicy.objects.select_for_update().filter(school=school, scope_key=key).first()
        if (row.revision if row else 0) != revision:
            return fail("La configuration a changé. Rechargez-la.", 409)
        if row is None:
            row = AdmissionPolicy(school=school, year=year, level=level, scope_key=key)
        row.enabled_routes = routes
        row.required_documents = docs
        row.revision = (revision + 1)
        row.full_clean()
        row.save()
        log_event(school, request, "admission_policy_updated", row.pk)
    return JsonResponse({**policy_view(school, year, level, row), "scope_revision": row.revision})


@require_http_methods(["GET", "POST"])
@authorized
def evidence(request, school_id, application_id):
    school, error = gate(request, school_id,
                         "school.admissions.read" if request.method == "GET"
                         else "school.admissions.manage")
    if error is not None:
        return error
    application = AdmissionApplication.objects.filter(school=school, pk=application_id).first()
    if application is None:
        return fail("Candidature introuvable.", 404)
    if request.method == "GET":
        return JsonResponse(documents_response(application))
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {"revision", "code", "reference"}:
        return fail("Code, référence et révision obligatoires.")
    try:
        revision = positive_revision(data["revision"])
        code = data["code"]
        if not isinstance(code, str) or not DOCUMENT_CODE.fullmatch(code):
            raise ValueError("Code de justificatif invalide.")
        reference = name(data["reference"], 180, mandatory=True)
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        application = AdmissionApplication.objects.select_for_update().get(school=school, pk=application_id)
        if application.revision != revision:
            return fail("La candidature a changé. Rechargez le dossier.", 409)
        if application.status not in ("submitted", "review"):
            return fail("Le dossier ne peut plus être modifié après décision.", 409)
        if AdmissionDocument.objects.filter(application=application, code=code).exists():
            return fail("Ce justificatif existe déjà pour cette candidature.", 409)
        document = AdmissionDocument(
            school=school, application=application, code=code, reference=reference)
        document.full_clean()
        document.save()
        application.revision += 1
        application.save(update_fields=["revision"])
        AdmissionEvent.objects.create(
            school=school, application=application,
            previous_status=application.status, new_status=application.status,
            reason="Référence de justificatif enregistrée : " + code, actor=request.user)
        log_event(school, request, "admission_document_added", document.pk)
    return JsonResponse(documents_response(application), status=201)


@require_POST
@authorized
def review_evidence(request, school_id, application_id, document_id):
    school, error = gate(request, school_id, "school.admissions.decide")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    if not isinstance(data, dict) or set(data) != {"revision", "status", "reason"}:
        return fail("Révision, résultat de contrôle et motif requis.")
    try:
        revision = positive_revision(data["revision"])
        status = data["status"]
        if status not in ("verified", "rejected"):
            raise ValueError("Résultat de vérification inconnu.")
        reason = name(data["reason"], 280, mandatory=True)
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        app = AdmissionApplication.objects.select_for_update().filter(school=school, pk=application_id).first()
        if not app:
            return fail("Candidature introuvable.", 404)
        if app.revision != revision:
            return fail("La candidature a changé. Rechargez le dossier.", 409)
        if app.status not in ("submitted", "review"):
            return fail("La décision est déjà prise : contrôle documentaire clôturé.", 409)
        doc = AdmissionDocument.objects.select_for_update().filter(
            school=school, application=app, pk=document_id).first()
        if not doc:
            return fail("Justificatif introuvable.", 404)
        doc.status = status
        doc.review_reason = reason
        doc.reviewed_by = request.user
        doc.reviewed_at = timezone.now()
        doc.save(update_fields=["status", "review_reason", "reviewed_by", "reviewed_at"])
        app.revision += 1
        app.save(update_fields=["revision"])
        AdmissionEvent.objects.create(
            school=school, application=app,
            previous_status=app.status, new_status=app.status,
            reason=f"Justificatif {doc.code} : {status} — {reason}", actor=request.user)
        log_event(school, request, "admission_document_reviewed", doc.pk)
    return JsonResponse(documents_response(app))


@require_POST
@authorized
def eligibility(request, school_id, application_id):
    school, error = gate(request, school_id, "school.admissions.manage")
    if error is not None:
        return error
    data, error = parse_body(request)
    if error is not None:
        return error
    expected = {"revision", "result", "route_reference", "orientation_authority", "reason"}
    if not isinstance(data, dict) or set(data) != expected:
        return fail("Révision, résultat, référence, autorité et motif requis.")
    try:
        revision = positive_revision(data["revision"])
        result = data["result"]
        if result not in ("pending", "eligible", "ineligible"):
            raise ValueError("Résultat de concours ou orientation invalide.")
        reference = name(data["route_reference"], 140, mandatory=(result == "eligible"))
        authority = name(data["orientation_authority"], 120)
        reason = name(data["reason"], 280, mandatory=True)
    except ValueError as exc:
        return fail(str(exc))
    with transaction.atomic():
        app = AdmissionApplication.objects.select_for_update().filter(school=school, pk=application_id).first()
        if app is None:
            return fail("Candidature introuvable.", 404)
        if app.route not in ("concours", "orientation"):
            return fail("Ce parcours ne nécessite pas de résultat externe.", 409)
        if app.status not in ("submitted", "review"):
            return fail("Le résultat ne peut plus être modifié après décision.", 409)
        if app.revision != revision:
            return fail("La candidature a changé. Rechargez le dossier.", 409)
        if app.route == "orientation" and result == "eligible" and not authority:
            return fail("L'autorité d'orientation est obligatoire.", 422)
        if app.route == "concours" and authority:
            return fail("Aucune autorité d'orientation ne doit être fournie pour un concours.", 422)
        app.external_result = result
        app.route_reference = reference
        app.orientation_authority = authority
        app.revision += 1
        app.full_clean()
        app.save()
        AdmissionEvent.objects.create(
            school=school, application=app,
            previous_status=app.status, new_status=app.status,
            reason=f"Résultat {app.route} : {result} — {reason}", actor=request.user)
        log_event(school, request, "admission_eligibility_recorded", app.pk)
    return JsonResponse(render(app))
