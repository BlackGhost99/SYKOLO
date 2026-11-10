"""School directory and safe family-initiated admissions.

Public listings are opt-in. Families may submit to the existing staff review
workflow but gain NO read permission to the school's student files as a result.
"""
from datetime import date
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.views import authorized
from .academic_models import AcademicClass
from .admission_models import AdmissionApplication, AdmissionEvent, AdmissionPolicy
from .admission_policy import ROUTES, effective_policy, required_for_route
from .parent_admission_models import FamilyChild, ParentAdmissionRequest, SchoolPublicListing
from .parent_payment_views import public_payment_availability
from .parent_payment_models import SchoolAdmissionFee, SchoolPaymentGateway
from .parent_payment_service import gateway_configured
from .demo_payment_views import demo_amount
from .services import has_permission
from .school_profiles import SCHOOL_PROFILES
from .student_models import Enrollment
from .views import access, log_event, parse_body, refuse


def error(message, status=422):
    return JsonResponse({"error": message}, status=status)


def clean_text(value, maximum, required=False):
    if not isinstance(value, str) or len(value.strip()) > maximum or (required and not value.strip()):
        raise ValueError("Champ texte invalide ou trop long.")
    return value.strip()


def date_value(value):
    if value in ("", None):
        return None
    if not isinstance(value, str):
        raise ValueError("Date de naissance invalide.")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date de naissance invalide.") from exc
    if result > date.today():
        raise ValueError("La date de naissance est dans le futur.")
    return result


def parse_uuid(value):
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def class_public_data(row, occupied, policy, fee, online_available, demo_amount_xaf=None):
    capacity = row.capacity
    return {
        "id": str(row.pk), "name": row.name,
        "year": row.year.name, "level": row.level.name,
        "cycle": row.level.cycle.name,
        "series": row.track.code.upper() if row.track_id else None,
        "series_label": row.track.name if row.track_id else None,
        "fee_amount_xaf": fee.amount_xaf if fee else None,
        "online_payment_available": bool(online_available and fee),
        "demo_payment_available": demo_amount_xaf is not None,
        "demo_fee_amount_xaf": demo_amount_xaf,
        "capacity": capacity,
        "remaining": max(0, capacity - occupied) if capacity is not None else None,
        "routes": list(policy.enabled_routes) if policy else list(ROUTES),
    }


@never_cache
@require_GET
def directory(request):
    """Only opted-in schools. Related data fetched per school, not per class."""
    query = request.GET.get("q", "").strip()[:80]
    city = request.GET.get("city", "").strip()[:80]
    rows = SchoolPublicListing.objects.select_related("school").filter(
        published=True, school__is_active=True,
    )
    if city:
        rows = rows.filter(city__icontains=city)
    if query:
        rows = rows.filter(school__name__icontains=query)
    result = []
    for listing in rows.order_by("school__name")[:100]:
        classes = list(AcademicClass.objects.select_related(
            "school", "year", "level__cycle", "track",
        ).filter(school=listing.school, active=True, year__active=True,
                 level__active=True, level__cycle__active=True
                 ).filter(Q(track__isnull=True) | Q(track__active=True)).order_by(
                     "year__start_date", "level__order", "name",
                 )[:150])
        class_ids = [row.pk for row in classes]
        occupied = {
            r["classroom_id"]: r["total"]
            for r in Enrollment.objects.filter(
                school=listing.school, classroom_id__in=class_ids, active=True,
            ).values("classroom_id").annotate(total=Count("pk"))
        }
        fees = {
            (row.year_id, row.level_id): row
            for row in SchoolAdmissionFee.objects.filter(
                school=listing.school, active=True,
                year_id__in={c.year_id for c in classes},
                level_id__in={c.level_id for c in classes},
            )
        }
        policies = {
            (row.year_id, row.level_id): row
            for row in AdmissionPolicy.objects.filter(
                school=listing.school, year_id__in={c.year_id for c in classes},
            )
        }
        gateway = SchoolPaymentGateway.objects.filter(school=listing.school).first()
        online = gateway_configured(gateway) and settings.AUTH_PUBLIC_BASE_URL.startswith("https://")
        class_views = [
            class_public_data(
                room, occupied.get(room.pk, 0),
                policies.get((room.year_id, room.level_id)) or policies.get((room.year_id, None)),
                fees.get((room.year_id, room.level_id)), online,
                demo_amount(listing.school, room.year_id, room.level_id, request.user),
            ) for room in classes
        ]
        result.append({
            "id": str(listing.school_id),
            "name": listing.school.name,
            "school_type": listing.school.school_type,
            "school_type_label": SCHOOL_PROFILES.get(listing.school.school_type, {}).get("label", "À classifier"),
            "education_cycles": listing.school.education_cycles,
            "city": listing.city, "district": listing.district,
            "description": listing.description, "phone": listing.contact_phone,
            "cash_at_school": listing.cash_at_school,
            "online_payment_available": any(room["online_payment_available"] for room in class_views),
            "classes": class_views,
        })
    return JsonResponse({"schools": result})

@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def listing_settings(request, school_id):
    school, failure = access(request, school_id)
    if failure is not None:
        return failure
    if not has_permission(request.user, school, "school.admissions.manage"):
        return refuse()
    if request.method == "GET":
        row = SchoolPublicListing.objects.filter(school=school).first()
        return JsonResponse({
            "published": row.published if row else False,
            "city": row.city if row else "",
            "district": row.district if row else "",
            "description": row.description if row else "",
            "contact_phone": row.contact_phone if row else "",
            "cash_at_school": row.cash_at_school if row else True,
            "revision": row.revision if row else 0,
        })
    data, failure = parse_body(request)
    if failure is not None:
        return failure
    if set(data) != {"revision", "published", "city", "district", "description", "contact_phone", "cash_at_school"}:
        return error("Configuration du catalogue incorrecte.")
    if (type(data["revision"]) is not int or data["revision"] < 0
            or type(data["published"]) is not bool
            or type(data["cash_at_school"]) is not bool):
        return error("Révision ou options invalides.")
    if data["published"] and (school.school_type == "non_classe" or not school.education_cycles):
        return error("Classez l’établissement et configurez ses cycles avant publication.", 409)
    try:
        cleaned = {key: clean_text(data[key], length) for key, length in (
            ("city", 100), ("district", 100), ("description", 600),
            ("contact_phone", 45),
        )}
    except ValueError as exc:
        return error(str(exc))
    with transaction.atomic():
        row = SchoolPublicListing.objects.select_for_update().filter(school=school).first()
        if (row.revision if row else 0) != data["revision"]:
            return error("Conflit de version. Rechargez la configuration.", 409)
        created = row is None
        if created:
            row = SchoolPublicListing(school=school)
        for key, value in cleaned.items():
            setattr(row, key, value)
        row.published = data["published"]
        row.cash_at_school = data["cash_at_school"]
        row.revision = 1 if created else row.revision + 1
        row.full_clean()
        row.save()
        log_event(school, request, "school_listing_updated", school.pk)
    return JsonResponse({"revision": row.revision, "published": row.published})


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def family_children(request):
    if request.method == "GET":
        rows = FamilyChild.objects.filter(owner=request.user, active=True).order_by("created_at")
        return JsonResponse({"children": [{
            "id": str(c.pk), "first_name": c.first_name, "last_name": c.last_name,
            "date_of_birth": c.date_of_birth.isoformat() if c.date_of_birth else None,
        } for c in rows[:100]]})
    data, failure = parse_body(request)
    if failure is not None:
        return failure
    if set(data) != {"first_name", "last_name", "date_of_birth"}:
        return error("Identité de l'enfant incomplète.")
    try:
        first = clean_text(data["first_name"], 120, required=True)
        last = clean_text(data["last_name"], 120, required=True)
        birth = date_value(data["date_of_birth"])
    except ValueError as exc:
        return error(str(exc))
    child = FamilyChild(owner=request.user, first_name=first, last_name=last, date_of_birth=birth)
    child.full_clean()
    child.save()
    return JsonResponse({"id": str(child.pk), "first_name": first, "last_name": last}, status=201)


def parent_application_output(link):
    app = link.application
    latest = link.payment_attempts.order_by("-created_at").first() if link.payment_choice in ("online", "demo") else None
    return {
        "id": str(link.pk), "child": str(link.child_id),
        "school": str(app.school_id), "school_name": app.school.name,
        "classroom": str(app.classroom_id), "classroom_name": app.classroom.name,
        "year": app.year.name, "route": app.route,
        "status": app.status, "payment_choice": link.payment_choice,
        "fee_amount_xaf": link.fee_amount_xaf,
        "submitted_at": app.submitted_at.isoformat(),
        "payment_status": latest.state if latest else ("non_initie" if link.payment_choice in ("online", "demo") else "a_regler_sur_place"),
        "payment_mode": latest.provider_mode if latest else None,
        "paid_confirmed": bool(latest and latest.state == "success" and latest.provider_mode == "live"),
        "notice": "Une demande ne réserve aucune place ; le paiement n’implique pas l’admission.",
    }


@never_cache
@require_http_methods(["GET", "POST"])
@authorized
def family_applications(request):
    if request.method == "GET":
        links = ParentAdmissionRequest.objects.select_related(
            "application__school", "application__year", "application__classroom", "child",
        ).filter(owner=request.user).order_by("-created_at")
        return JsonResponse({"applications": [parent_application_output(link) for link in links[:100]]})
    data, failure = parse_body(request)
    if failure is not None:
        return failure
    required = {"child", "classroom", "route", "payment_choice", "guardian_relationship", "guardian_phone"}
    optional = {"origin_school", "route_reference"}
    if not required <= set(data) or set(data) - (required | optional):
        return error("Champs de candidature invalides.")
    try:
        child_id = parse_uuid(data["child"])
        class_id = parse_uuid(data["classroom"])
        if not child_id or not class_id:
            raise ValueError("Enfant ou classe invalide.")
        route = data["route"]
        if route not in ROUTES:
            raise ValueError("Voie d'admission inconnue.")
        payment_choice = data["payment_choice"]
        if payment_choice not in ("cash", "online", "demo"):
            raise ValueError("Mode de règlement invalide.")
        relation = clean_text(data["guardian_relationship"], 80, required=True)
        phone = clean_text(data["guardian_phone"], 45, required=True)
        origin = clean_text(data.get("origin_school", ""), 180)
        reference = clean_text(data.get("route_reference", ""), 140)
        child = FamilyChild.objects.filter(owner=request.user, active=True, pk=child_id).first()
        if child is None:
            return error("Enfant introuvable.", 404)
        with transaction.atomic():
            # PostgreSQL interdit FOR UPDATE sur la partie nullable (filière facultative).
            # Verrouiller uniquement la classe, pas les jointures de lecture.
            classroom = AcademicClass.objects.select_for_update(of=("self",)).select_related(
                "school", "year", "level",
            ).filter(pk=class_id, active=True, school__is_active=True,
                     year__active=True, level__active=True, level__cycle__active=True,
                     school__public_listing__published=True).filter(
                         Q(track__isnull=True) | Q(track__active=True)).first()
            if classroom is None:
                return error("Classe non publiée ou indisponible.", 404)
            listing = SchoolPublicListing.objects.get(school=classroom.school)
            fee, online_available = public_payment_availability(classroom.school, classroom.year, classroom.level)
            if payment_choice == "cash" and not listing.cash_at_school:
                return error("L'établissement n'accepte pas le règlement sur place.", 409)
            if payment_choice == "online" and not online_available:
                return error("Paiement en ligne indisponible pour cette classe.", 409)
            demo_price = demo_amount(classroom.school, classroom.year_id, classroom.level_id, request.user)
            if payment_choice == "demo" and demo_price is None:
                return error("Simulation non autorisée pour ce parent et cette classe.", 403)
            policy = effective_policy(classroom.school, classroom.year, classroom.level)
            if route not in (policy.enabled_routes if policy else ROUTES):
                return error("Cette voie d'admission est fermée.", 409)
            if classroom.capacity is not None:
                occupied = Enrollment.objects.filter(
                    school=classroom.school, classroom=classroom, active=True,
                ).count()
                if occupied >= classroom.capacity:
                    return error("Aucune place disponible pour cette classe.", 409)
            if ParentAdmissionRequest.objects.filter(
                owner=request.user, child=child, application__school=classroom.school,
                application__year=classroom.year,
            ).exclude(application__status="rejected").exists():
                return error("Une candidature existe déjà pour cet enfant et cette école cette année.", 409)
            guardian_name = (request.user.get_full_name() or request.user.get_username())[:180]
            app = AdmissionApplication(
                school=classroom.school, year=classroom.year, classroom=classroom,
                first_name=child.first_name, last_name=child.last_name,
                date_of_birth=child.date_of_birth, guardian_name=guardian_name,
                guardian_relationship=relation, guardian_phone=phone,
                guardian_email=request.user.email or "", source="parent_mobile",
                submitted_by=request.user, route=route, origin_school=origin,
                route_reference=reference if route != "direct" else "",
                required_documents=required_for_route(route, policy),
            )
            app.full_clean()
            app.save()
            link = ParentAdmissionRequest(owner=request.user, child=child,
                                          application=app, payment_choice=payment_choice,
                                          fee_amount_xaf=demo_price if payment_choice == "demo" else fee.amount_xaf if fee else None)
            link.full_clean()
            link.save()
            AdmissionEvent.objects.create(school=classroom.school, application=app,
                                          previous_status="", new_status="submitted",
                                          actor=request.user)
            log_event(classroom.school, request, "parent_admission_submitted", app.pk)
    except (ValueError, ValidationError) as exc:
        return error(str(exc)[:500])
    except IntegrityError:
        return error("Candidature déjà enregistrée.", 409)
    return JsonResponse(parent_application_output(link), status=201)
