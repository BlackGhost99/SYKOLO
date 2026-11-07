"""Parcours transactionnel de création du personnel, sans contourner les contrôles existants."""
import re
from datetime import date
from uuid import UUID, uuid4

from accounts.views import authorized
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .academic_models import AcademicClass, AcademicYear, AcademicCycle
from .cycle_scope import scoped_cycle_ids, validate_cycle_scope, profile_cycle_keys
from .models import School, SchoolAppointment, SchoolLogin, SchoolMember, SchoolRole
from .school_functions import (
    account_functions, positions_for_school, validate_account_functions, validate_position,
)
from .services import effective_permissions, has_permission, owns_organization, quota_reached
from .staff_models import StaffAssignment, StaffRecord
from .staff_views import parse_staff, staff_repr
from .views import access, financial_grant_allowed, log_event, parse_body, refuse, string


def _validation_message(exc):
    if hasattr(exc, "message_dict"):
        values = [str(item) for group in exc.message_dict.values() for item in group]
    elif hasattr(exc, "messages"):
        values = [str(item) for item in exc.messages]
    else:
        values = [str(exc)]
    return " ".join(values)[:500]


def _date(value):
    if value in ("", None):
        return None
    if not isinstance(value, str):
        raise ValueError("Date de nomination invalide.")
    try:
        result = date.fromisoformat(value)
    except ValueError:
        raise ValueError("Date de nomination invalide.") from None
    if result.isoformat() != value:
        raise ValueError("Date de nomination invalide.")
    return result


def _appointments(school, data):
    if not isinstance(data, list) or len(data) > 20:
        raise ValueError("Nombre de fonctions invalide (maximum 20).")
    clean, seen = [], set()
    for item in data:
        if not isinstance(item, dict) or set(item) - {
            "function_code", "cycle_code", "starts_on", "ends_on"
        }:
            raise ValueError("Nomination invalide.")
        code, cycle = item.get("function_code"), item.get("cycle_code", "")
        if not isinstance(code, str) or not isinstance(cycle, str):
            raise ValueError("Fonction ou cycle invalide.")
        validate_position(school, code, cycle)
        key = (code, cycle)
        if key in seen:
            raise ValueError("Cette fonction est sélectionnée deux fois pour le même cycle.")
        seen.add(key)
        begins, ends = _date(item.get("starts_on")), _date(item.get("ends_on"))
        if begins and ends and begins > ends:
            raise ValueError("La fin de fonction précède son début.")
        clean.append((code, cycle, begins, ends))
    return clean


def _class_assignments(school, data):
    if not isinstance(data, list) or len(data) > 30:
        raise ValueError("Nombre d'affectations de classes invalide (maximum 30).")
    clean, seen = [], set()
    for item in data:
        if not isinstance(item, dict) or set(item) != {"year", "classroom", "duty"}:
            raise ValueError("Affectation de classe invalide.")
        try:
            year_id, class_id = UUID(str(item["year"])), UUID(str(item["classroom"]))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("Année ou classe invalide.") from None
        duty = item["duty"]
        if not isinstance(duty, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,49}", duty):
            raise ValueError("Responsabilité de classe invalide.")
        key = (year_id, class_id, duty)
        if key in seen:
            raise ValueError("Affectation de classe sélectionnée deux fois.")
        seen.add(key)
        year = AcademicYear.objects.filter(pk=year_id, school=school, active=True).first()
        classroom = AcademicClass.objects.filter(
            pk=class_id, school=school, year=year, active=True
        ).first() if year else None
        if not year or not classroom:
            raise ValueError("Année ou classe inactive / étrangère à cet établissement.")
        clean.append((year, classroom, duty))
    return clean


def _account(school, actor, owner, data, appointments):
    if data is None:
        return None
    required = {"username", "email", "password", "role", "additional_roles"}
    if not isinstance(data, dict) or not required <= set(data) or set(data) - required - {"access_cycle_ids"}:
        raise ValueError("Compte utilisateur incomplet.")
    username, email, password = data["username"], data["email"], data["password"]
    if not (string(username, 150) and string(email, 254) and "@" in email
            and isinstance(password, str) and string(data["role"], 48)):
        raise ValueError("Identifiants de connexion invalides.")
    if not owner and not has_permission(actor, school, "school.members.write"):
        raise PermissionError("Création de compte non autorisée.")
    roles = data["additional_roles"]
    if (not isinstance(roles, list) or len(roles) > 20
            or any(not isinstance(c, str) for c in roles) or len(roles) != len(set(roles))
            or data["role"] in roles):
        raise ValueError("Rôles supplémentaires invalides.")
    if data["role"] in {"parent", "eleve", "proprietaire"} or any(
        code in {"parent", "eleve", "proprietaire"} for code in roles
    ):
        raise ValueError("Rôle non destiné au personnel scolaire.")
    primary = SchoolRole.objects.filter(school=school, code=data["role"]).first()
    extra = list(SchoolRole.objects.filter(school=school, code__in=roles))
    if not primary or len(extra) != len(roles):
        raise ValueError("Rôle inconnu dans cet établissement.")
    granted = set().union(*(set(r.permissions) for r in [primary, *extra]))
    if not owner and not granted <= effective_permissions(actor, school):
        raise PermissionError("Vous ne pouvez pas transmettre ces autorisations.")
    if not owner and any(p.startswith("school.finance.") and p.split(".")[-1] in {
        "manage", "receive", "reverse", "approve", "deposit"
    } for p in granted):
        raise PermissionError("Les droits financiers sensibles sont réservés au propriétaire.")
    validate_account_functions(school, [row[0] for row in appointments])
    scope = validate_cycle_scope(school, data.get("access_cycle_ids"))
    actor_scope = scoped_cycle_ids(actor, school)
    if actor_scope is not None and (scope is None or not set(scope) <= actor_scope):
        raise PermissionError("Le compte créé doit rester dans les cycles autorisés du responsable.")
    candidate = get_user_model()(
        username=username.strip(), email=email.strip()
    )
    validate_password(password, user=candidate)
    return (username.strip(), email.strip(), password, primary, extra, granted, scope)


@require_http_methods(["GET", "POST"])
@authorized
def onboard_staff(request, school_id):
    school, error = access(request, school_id)
    if error is not None:
        return error
    owner = owns_organization(request.user, school.organization)
    can_staff = owner or has_permission(request.user, school, "school.staff.manage")
    if not can_staff:
        return refuse()
    can_account = owner or has_permission(request.user, school, "school.members.write")
    can_appoint = owner or has_permission(request.user, school, "school.organization.manage")
    actor_scope = scoped_cycle_ids(request.user, school)

    if request.method == "GET":
        allowed = effective_permissions(request.user, school)
        roles = SchoolRole.objects.filter(school=school).order_by("label")
        roles = [r for r in roles if r.code not in {"parent", "eleve", "proprietaire"} and (owner or (
            can_account and set(r.permissions) <= allowed
            and not any(p in r.permissions for p in (
                "school.finance.manage", "school.finance.receive", "school.finance.reverse",
                "school.finance.approve", "school.finance.deposit"
            ))
        ))]
        years = AcademicYear.objects.filter(school=school, active=True).order_by("-start_date")
        classes = AcademicClass.objects.filter(school=school, active=True, year__active=True).order_by("name")
        academic_cycles = AcademicCycle.objects.filter(school=school,active=True).order_by("order","name")
        positions = account_functions(school) if can_appoint else []
        if actor_scope is not None:
            classes = classes.filter(level__cycle_id__in=actor_scope)
            years = years.filter(pk__in=classes.values("year_id"))
            academic_cycles = academic_cycles.filter(pk__in=actor_scope)
            keys = profile_cycle_keys(school, actor_scope)
            positions = [{**p, "allowed_cycles": sorted(set(p["allowed_cycles"]) & keys)} for p in positions if p["scope"]=="cycle" and set(p["allowed_cycles"]) & keys]
        existing = []
        if owner:
            members = SchoolMember.objects.select_related("user").filter(
                school=school, active=True, user__is_active=True
            ).order_by("user__last_name","user__first_name")[:200]
            for member in members:
                if owns_organization(member.user, school.organization):
                    continue
                alias = SchoolLogin.objects.filter(school=school,user=member.user).values_list("username",flat=True).first()
                existing.append({"member_id":str(member.pk), "username":alias or member.user.username,
                                 "name":f"{member.user.first_name} {member.user.last_name}".strip(),
                                 "access_cycle_ids":member.access_cycle_ids})
        return JsonResponse({
            "can_manage_cycle_access": owner,
            "existing_accounts":existing,
            "school_name": school.name,
            "school_type": school.school_type,
            "education_cycles": school.education_cycles,
            "can_create_account": can_account,
            "can_appoint": can_appoint,
            "roles": [{"code": r.code, "label": r.label, "permissions": r.permissions} for r in roles] if can_account else [],
            "positions": positions,
            "academic_cycles": [{"id": str(c.id), "code": c.code, "name": c.name} for c in academic_cycles],
            "actor_access_cycle_ids": sorted(actor_scope) if actor_scope is not None else None,
            "years": [{"id": str(y.id), "name": y.name} for y in years],
            "classes": [{"id": str(c.id), "name": c.name, "year": str(c.year_id)} for c in classes],
            "notice": "Les rôles applicatifs accordent des droits à tout l'établissement, pas seulement au cycle nommé.",
        })

    body, error = parse_body(request)
    if error is not None:
        return error
    if set(body) != {
        "staff", "account", "appointments", "class_assignments", "ack_school_wide_permissions"
    }:
        return JsonResponse({"error": "Dossier du personnel incomplet ou invalide."}, status=422)
    if not isinstance(body["staff"], dict) or body["account"] is not None and not can_account:
        return refuse()
    if body["appointments"] and not can_appoint:
        return refuse()
    if type(body["ack_school_wide_permissions"]) is not bool:
        return JsonResponse({"error": "Confirmation des droits invalide."}, status=422)
    if body["account"] is not None and len(school.education_cycles or []) > 1 and not body["ack_school_wide_permissions"]:
        return JsonResponse({"error": "Confirmez que les rôles donnent actuellement accès à tout le complexe."}, status=422)

    try:
        staff_fields = parse_staff(body["staff"])
        if "username" in staff_fields or "active" in staff_fields:
            raise ValueError("Utilisez le formulaire de compte pour la connexion.")
        appointments = _appointments(school, body["appointments"])
        assignments = _class_assignments(school, body["class_assignments"])
        account_info = _account(school, request.user, owner, body["account"], appointments)
        if actor_scope is not None:
            keys = profile_cycle_keys(school, actor_scope)
            if not appointments and not assignments:
                raise PermissionError("Sélectionnez une fonction ou une classe du cycle autorisé.")
            if any(cycle not in keys for _, cycle, _, _ in appointments):
                raise PermissionError("Nomination hors du cycle autorisé.")
            if any(str(classroom.level.cycle_id) not in actor_scope for _, classroom, _ in assignments):
                raise PermissionError("Classe hors du cycle autorisé.")
    except PermissionError as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except ValidationError as exc:
        return JsonResponse({"error": _validation_message(exc)}, status=422)

    try:
        with transaction.atomic():
            # Même verrou que le reste de l'administration : quotas et matricules cohérents.
            school = School.objects.select_for_update().get(pk=school.pk)
            owner = owns_organization(request.user, school.organization)
            if not (owner or has_permission(request.user, school, "school.staff.manage")):
                return refuse()
            if body["account"] is not None and not (owner or has_permission(request.user, school, "school.members.write")):
                return refuse()
            if body["appointments"] and not (owner or has_permission(request.user, school, "school.organization.manage")):
                return refuse()
            if body["account"] is not None and len(school.education_cycles or []) > 1 and not body["ack_school_wide_permissions"]:
                raise ValueError("Confirmez les droits applicatifs à tout le complexe.")
            appointments = _appointments(school, body["appointments"])
            assignments = _class_assignments(school, body["class_assignments"])
            account_info = _account(school, request.user, owner, body["account"], appointments)
            actor_scope = scoped_cycle_ids(request.user, school)
            if actor_scope is not None:
                keys = profile_cycle_keys(school, actor_scope)
                if not appointments and not assignments:
                    raise PermissionError("Sélectionnez une fonction ou une classe du cycle autorisé.")
                if any(cycle not in keys for _, cycle, _, _ in appointments):
                    raise PermissionError("Nomination hors du cycle autorisé.")
                if any(str(classroom.level.cycle_id) not in actor_scope for _, classroom, _ in assignments):
                    raise PermissionError("Classe hors du cycle autorisé.")
            if account_info and quota_reached(school, "users"):
                return JsonResponse({"error": "Plafond de comptes atteint pour cette école."}, status=409)
            if StaffRecord.objects.filter(school=school, staff_code=staff_fields["staff_code"]).exists():
                return JsonResponse({"error": "Ce matricule existe déjà dans l'établissement."}, status=409)
            user = None
            if account_info:
                username, email, password, primary, extra, granted, scope = account_info
                if SchoolLogin.objects.filter(school=school, username=username).exists():
                    return JsonResponse({"error": "Identifiant de connexion déjà utilisé dans cette école."}, status=409)
                User = get_user_model()
                internal = username if not User.objects.filter(username=username).exists() else "school-" + uuid4().hex
                user = User.objects.create_user(
                    username=internal, first_name=staff_fields["first_name"],
                    last_name=staff_fields["last_name"], email=email, password=password,
                )
                member = SchoolMember.objects.create(
                    school=school, user=user, role=primary,
                    function_codes=validate_account_functions(school, [row[0] for row in appointments]),
                    access_cycle_ids=scope,
                )
                member.additional_roles.set(extra)
                SchoolLogin.objects.create(school=school, user=user, username=username)
                if not financial_grant_allowed(request.user, school, user, granted):
                    raise PermissionError("Attribution financière non autorisée.")

            staff_record = StaffRecord(school=school, account=user, **staff_fields)
            staff_record.full_clean()
            staff_record.save()
            for code, cycle, begins, ends in appointments:
                obj = SchoolAppointment(
                    school=school, staff=staff_record, function_code=code, cycle_code=cycle,
                    starts_on=begins, ends_on=ends, appointed_by=request.user,
                )
                obj.full_clean()
                obj.save()
            for year, classroom, duty in assignments:
                obj = StaffAssignment(
                    school=school, staff=staff_record, year=year, classroom=classroom, duty=duty,
                )
                obj.full_clean()
                obj.save()
            log_event(school, request, "staff_onboarded", str(staff_record.id), {
                "account_created": bool(user),
                "access_cycle_ids": account_info[6] if account_info else None,
                "roles": [account_info[3].code, *[r.code for r in account_info[4]]] if account_info else [],
                "appointments": [{"function": code, "cycle": cycle} for code, cycle, _, _ in appointments],
                "assignments_count": len(assignments),
            })
    except PermissionError as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except ValidationError as exc:
        return JsonResponse({"error": _validation_message(exc)}, status=422)
    except IntegrityError:
        return JsonResponse({"error": "Matricule, compte ou nomination déjà utilisé(e)."}, status=409)

    return JsonResponse({
        "staff": staff_repr(staff_record),
        "account_created": bool(user),
        "username": account_info[0] if account_info else None,
        "appointments_count": len(appointments),
        "assignments_count": len(assignments),
    }, status=201)
